"""Exit rules for Pattern Forecast 5-day paper desk (v1)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List

import pandas as pd

from tradingagents.swing.exits import trading_days_between


class ExitReason(str, Enum):
    STOP = "stop_loss"
    TARGET = "target_max_high"
    TIME = "time_exit"
    FORECLOSURE = "foreclosure"


@dataclass
class ExitAction:
    ticker: str
    reason: ExitReason
    exit_price: float
    exit_date: str
    exit_pct: float
    partial: bool = False


def evaluate_bar_exits(
    position: dict,
    bar: pd.Series,
    bar_date: str,
    holding_days: int,
    history: pd.DataFrame,
    stop_on_close_only: bool = False,
    breakeven_trigger_pct: float = 0.0,
) -> List[ExitAction]:
    """Breakeven ratchet, close-only stop, target, then 5d time exit."""
    actions: List[ExitAction] = []
    remaining = float(position.get("remaining_pct", 100.0))
    if remaining <= 0:
        return actions

    entry = float(position.get("entry_price") or 0)
    stop = float(position.get("trailing_stop") or position.get("stop_loss") or 0)
    target = float(position.get("target_max") or 0)
    low = float(bar["Low"])
    high = float(bar["High"])
    close = float(bar["Close"])
    entry_date = position["screen_date"]

    if breakeven_trigger_pct > 0 and entry > 0 and high >= entry * (1.0 + breakeven_trigger_pct / 100.0):
        stop = max(stop, entry)
        position["trailing_stop"] = round(stop, 2)
        position["phase"] = "breakeven"

    stopped = (close <= stop) if stop_on_close_only else (low <= stop)
    if stop > 0 and stopped:
        actions.append(
            ExitAction(
                ticker=position["ticker"],
                reason=ExitReason.STOP,
                exit_price=round(stop, 2),
                exit_date=bar_date,
                exit_pct=remaining,
            )
        )
        return actions

    if target > 0 and high >= target:
        actions.append(
            ExitAction(
                ticker=position["ticker"],
                reason=ExitReason.TARGET,
                exit_price=round(target, 2),
                exit_date=bar_date,
                exit_pct=remaining,
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
            )
        )

    return actions
