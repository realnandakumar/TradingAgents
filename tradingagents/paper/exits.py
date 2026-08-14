"""Exit rules for the RS paper desk: stop → target → time."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

import pandas as pd

from tradingagents.paper.json_store import bar_ohlc_finite
from tradingagents.swing.exits import resolve_same_bar_stop_t1, trading_days_between


class ExitReason(str, Enum):
    STOP = "stop_loss"
    TARGET = "target"
    TIME = "time_exit"


@dataclass
class ExitAction:
    reason: ExitReason
    exit_price: float
    exit_date: str


def evaluate_bar_exits(
    position: dict,
    bar: pd.Series,
    bar_date: str,
    holding_days: int,
    history: pd.DataFrame,
) -> Optional[ExitAction]:
    """Stop on low, target on high, then time exit at holding_days.

    Same-bar stop+target uses close as path proxy (see resolve_same_bar_stop_t1).
    """
    ohlc = bar_ohlc_finite(bar)
    if ohlc is None:
        return None
    low, high, close = ohlc
    entry_date = position["entry_date"]
    stop = float(position.get("stoploss") or position.get("stop_loss") or 0)
    target = float(position.get("target") or 0)

    stop_hit = stop > 0 and low <= stop
    t1_hit = target > 0 and high >= target
    winner = resolve_same_bar_stop_t1(
        stop_hit=stop_hit,
        t1_hit=t1_hit,
        close=close,
        stop=stop,
        target_1=target,
    )

    if winner == "stop":
        return ExitAction(ExitReason.STOP, round(stop, 2), bar_date)

    if winner == "t1":
        return ExitAction(ExitReason.TARGET, round(target, 2), bar_date)

    days_held = trading_days_between(entry_date, bar_date, history)
    if days_held >= holding_days:
        return ExitAction(ExitReason.TIME, round(close, 2), bar_date)

    return None
