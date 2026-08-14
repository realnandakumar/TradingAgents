"""Exit evaluation for swing_trade_positional (daily 1D bars).

Rules:
- Dynamic trailing stop = Supertrend buy line, ratcheted up daily only
- Stop hit → exit remaining position
- Target 1 → exit 100% of the position
- Same-bar stop+T1 → close-aware with conservative default (stop)
- 20 trading days → close whatever remains
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import List, Optional

import pandas as pd

from tradingagents.dataflows.nse_calendar import is_nse_trading_day
from tradingagents.paper.json_store import bar_ohlc_finite


class ExitReason(str, Enum):
    STOP = "stop_loss"
    TARGET_1 = "target_1"
    TARGET_2_PARTIAL = "target_2_partial"
    TRAIL_STOP = "trail_stop"
    TIME = "time_exit"
    FORECLOSURE = "foreclosure"
    LEGACY_RUNNER = "legacy_runner_close"
    SIGNAL_SELL = "signal_sell"


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


def resolve_same_bar_stop_t1(
    *,
    stop_hit: bool,
    t1_hit: bool,
    close: float,
    stop: float,
    target_1: float,
) -> Optional[str]:
    """When stop and T1 both print on one daily bar, use close as path proxy.

    - Close at/through T1 → credit target (finished in profit zone)
    - Close at/through stop → credit stop
    - Otherwise → stop (conservative when path is ambiguous)
    """
    if stop_hit and t1_hit:
        if target_1 > 0 and close >= target_1:
            return "t1"
        if stop > 0 and close <= stop:
            return "stop"
        return "stop"
    if stop_hit:
        return "stop"
    if t1_hit:
        return "t1"
    return None


def evaluate_bar_exits(
    position: dict,
    bar: pd.Series,
    bar_date: str,
    holding_days: int,
    history: pd.DataFrame,
) -> List[ExitAction]:
    """Return zero or more exit actions for today's bar."""
    actions: List[ExitAction] = []
    remaining = float(position.get("remaining_pct", 100.0))
    if remaining <= 0:
        return actions

    ohlc = bar_ohlc_finite(bar)
    if ohlc is None:
        return actions
    low, high, close = ohlc

    stop = float(position.get("trailing_stop") or position.get("stop_loss") or 0)
    target_1 = float(position.get("target_1") or 0)
    entry_date = position["screen_date"]

    stop_hit = stop > 0 and low <= stop
    t1_hit = target_1 > 0 and high >= target_1
    winner = resolve_same_bar_stop_t1(
        stop_hit=stop_hit,
        t1_hit=t1_hit,
        close=close,
        stop=stop,
        target_1=target_1,
    )

    if winner == "stop":
        actions.append(
            ExitAction(
                ticker=position["ticker"],
                reason=ExitReason.STOP,
                exit_price=round(stop, 2),
                exit_date=bar_date,
                exit_pct=remaining,
                partial=False,
            )
        )
        return actions

    if winner == "t1":
        actions.append(
            ExitAction(
                ticker=position["ticker"],
                reason=ExitReason.TARGET_1,
                exit_price=round(target_1, 2),
                exit_date=bar_date,
                exit_pct=remaining,
                partial=False,
            )
        )
        return actions

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


def risk_pct(entry: float, stop: float) -> Optional[float]:
    if entry <= 0 or stop <= 0 or stop >= entry:
        return None
    return round(100.0 * (entry - stop) / entry, 2)


__all__ = [
    "ExitReason",
    "ExitAction",
    "trading_days_between",
    "resolve_same_bar_stop_t1",
    "evaluate_bar_exits",
    "is_nse_trading_day",
    "risk_pct",
]
