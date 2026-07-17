"""Exit evaluation for momentum_trade_positional (daily 1D bars).

Same as swing: stop → T1 full exit → time exit at max hold.
"""

from __future__ import annotations

from typing import List

import pandas as pd

from tradingagents.swing.exits import ExitAction, evaluate_bar_exits


def evaluate_momentum_bar_exits(
    position: dict,
    bar: pd.Series,
    bar_date: str,
    max_holding_days: int,
    history: pd.DataFrame,
    t2_exit_pct: float = 75.0,  # legacy kwarg; ignored (T1 full exit)
) -> List[ExitAction]:
    _ = t2_exit_pct
    return evaluate_bar_exits(position, bar, bar_date, max_holding_days, history)
