"""Dynamic Supertrend trailing stop (daily 1D)."""

from __future__ import annotations

from typing import Optional, Tuple

import pandas as pd

from tradingagents.screening.swing_indicators import supertrend


def latest_supertrend_buy_line(
    df: pd.DataFrame,
    period: int = 10,
    multiplier: float = 3.0,
) -> Tuple[Optional[float], int]:
    """Return (supertrend line, trend) for the latest bar. trend: 1=Buy, -1=Sell."""
    if df is None or len(df) < period + 2:
        return None, 0
    st_line, trend = supertrend(df, period=period, multiplier=multiplier)
    if st_line.empty or not pd.notna(st_line.iloc[-1]):
        return None, int(trend.iloc[-1])
    return float(st_line.iloc[-1]), int(trend.iloc[-1])


def ratchet_stop(current: float, new_stop: Optional[float]) -> float:
    """Never lower the stop — only ratchet upward."""
    if new_stop is None or new_stop <= 0:
        return current
    return max(current, new_stop)
