"""Exit rules for Tech Desk paper positions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List

import pandas as pd

from tradingagents.swing.exits import trading_days_between


class ExitReason(str, Enum):
    STOP = "stop_loss"
    TARGET_1 = "target_1"
    TARGET_2 = "target_2"  # Legacy closed-trade reason; no longer emitted.
    TIME = "time_exit"
    FORECLOSURE = "foreclosure"
    REVIEW_CLOSE = "review_close"


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
) -> List[ExitAction]:
    """Stop, primary target, then time exit."""
    actions: List[ExitAction] = []
    remaining = float(position.get("remaining_pct", 100.0))
    if remaining <= 0:
        return actions

    entry = float(position.get("entry_price") or 0)
    stop = float(position.get("trailing_stop") or position.get("stop_loss") or 0)
    target_1 = float(position.get("target_1") or 0)
    low = float(bar["Low"])
    high = float(bar["High"])
    close = float(bar["Close"])
    entry_date = position["screen_date"]

    if stop > 0 and low <= stop:
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

    if target_1 > 0 and high >= target_1:
        actions.append(
            ExitAction(
                ticker=position["ticker"],
                reason=ExitReason.TARGET_1,
                exit_price=round(target_1, 2),
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


def zone_fill_price(bar: pd.Series, zone_low: float, zone_high: float) -> float | None:
    """Return fill price if the bar overlaps the pullback zone, else None."""
    low = float(bar["Low"])
    high = float(bar["High"])
    close = float(bar["Close"])
    if low > zone_high or high < zone_low:
        return None
    if zone_low <= close <= zone_high:
        return round(close, 2)
    if close < zone_low:
        return round(zone_low, 2)
    return round(zone_high, 2)
