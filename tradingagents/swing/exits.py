"""Exit evaluation for swing_trade_positional (daily 1D bars).

Rules:
- Dynamic trailing stop = Supertrend buy line, ratcheted up daily only
- Stop hit → exit remaining position (full if pre-T2, runner if post-T2 partial)
- Target 2 → sell configured % (default 75%), trail remainder on Supertrend
- Target 1 ignored
- 20 trading days → close whatever remains
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional

import pandas as pd


class ExitReason(str, Enum):
    STOP = "stop_loss"
    TARGET_2_PARTIAL = "target_2_partial"
    TRAIL_STOP = "trail_stop"
    TIME = "time_exit"
    FORECLOSURE = "foreclosure"


@dataclass
class ExitAction:
    ticker: str
    reason: ExitReason
    exit_price: float
    exit_date: str
    exit_pct: float  # % of original position closed this action
    partial: bool


def trading_days_between(start: str, end: str, history: pd.DataFrame) -> int:
    if history is None or history.empty:
        return 0
    idx = history.index
    if not isinstance(idx, pd.DatetimeIndex):
        return 0
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    mask = (idx >= start_ts) & (idx <= end_ts)
    return int(mask.sum())


def evaluate_bar_exits(
    position: dict,
    bar: pd.Series,
    bar_date: str,
    holding_days: int,
    history: pd.DataFrame,
    t2_exit_pct: float = 75.0,
) -> List[ExitAction]:
    """Return zero or more exit actions for today's bar (stop before T2 on same bar)."""
    actions: List[ExitAction] = []
    remaining = float(position.get("remaining_pct", 100.0))
    if remaining <= 0:
        return actions

    phase = position.get("phase", "initial")
    stop = float(position.get("trailing_stop") or position.get("stop_loss") or 0)
    target_2 = float(position.get("target_2") or 0)
    low = float(bar["Low"])
    high = float(bar["High"])
    close = float(bar["Close"])
    entry_date = position["screen_date"]

    # 1) Trailing / initial stop on remaining size
    if stop > 0 and low <= stop:
        reason = ExitReason.TRAIL_STOP if phase == "runner" else ExitReason.STOP
        actions.append(
            ExitAction(
                ticker=position["ticker"],
                reason=reason,
                exit_price=round(stop, 2),
                exit_date=bar_date,
                exit_pct=remaining,
                partial=False,
            )
        )
        return actions

    # 2) T2 partial (initial phase only, once)
    if phase == "initial" and not position.get("t2_partial_done") and target_2 > 0 and high >= target_2:
        sell_pct = min(t2_exit_pct, remaining)
        actions.append(
            ExitAction(
                ticker=position["ticker"],
                reason=ExitReason.TARGET_2_PARTIAL,
                exit_price=round(target_2, 2),
                exit_date=bar_date,
                exit_pct=sell_pct,
                partial=True,
            )
        )
        return actions

    # 3) Time exit on whatever remains
    days_held = trading_days_between(entry_date, bar_date, history)
    if days_held >= holding_days:
        actions.append(
            ExitAction(
                ticker=position["ticker"],
                reason=ExitReason.TIME,
                exit_price=round(close, 2),
                exit_date=bar_date,
                exit_pct=remaining,
                partial=False,
            )
        )

    return actions


def is_nse_trading_day(dt: Optional[datetime] = None) -> bool:
    dt = dt or datetime.now()
    return dt.weekday() < 5


def risk_pct(entry: float, stop: float) -> Optional[float]:
    if entry <= 0 or stop <= 0 or stop >= entry:
        return None
    return round(100.0 * (entry - stop) / entry, 2)
