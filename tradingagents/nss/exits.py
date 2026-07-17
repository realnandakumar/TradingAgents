"""Exit evaluation for nanda_swing_scanner (daily 1D bars).

Same as swing/momentum: stop → T1 full exit → time exit at max hold.
"""

from tradingagents.momentum.exits import evaluate_momentum_bar_exits

__all__ = ["evaluate_momentum_bar_exits"]
