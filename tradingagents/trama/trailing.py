"""Dynamic TRAMA trailing stop for TRAMA crossover book."""

from __future__ import annotations

from typing import Optional

import pandas as pd

from tradingagents.screening.trama_indicator import trama_from_ohlc
from tradingagents.swing.trailing import ratchet_stop


def latest_trama_line(df: pd.DataFrame, length: int = 100) -> Optional[float]:
    """Latest TRAMA value from OHLC history, or None if insufficient data."""
    if df is None or len(df) < length:
        return None
    line = trama_from_ohlc(df, length=length)
    val = float(line.iloc[-1])
    return val if pd.notna(val) else None


__all__ = ["latest_trama_line", "ratchet_stop"]
