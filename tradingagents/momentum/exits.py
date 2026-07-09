"""Exit evaluation for momentum_trade_positional (daily 1D bars).

Same stop / T2 partial / trail rules as swing, but time exit at max hold (90 days).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List

import pandas as pd

from tradingagents.swing.exits import ExitAction, ExitReason, trading_days_between


def evaluate_momentum_bar_exits(
    position: dict,
    bar: pd.Series,
    bar_date: str,
    max_holding_days: int,
    history: pd.DataFrame,
    t2_exit_pct: float = 75.0,
) -> List[ExitAction]:
    """Stop and T2 anytime; time exit only at max_holding_days."""
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

    days_held = trading_days_between(entry_date, bar_date, history)
    if days_held >= max_holding_days:
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
