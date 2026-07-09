"""Dynamic NWE trailing stop for NW Envelope book."""

from __future__ import annotations

from typing import Optional, Tuple

import pandas as pd

from tradingagents.screening.nw_envelope_indicator import nw_envelope_from_ohlc
from tradingagents.swing.trailing import ratchet_stop


def latest_nwe_bands(
    df: pd.DataFrame,
    bandwidth: float = 8.0,
    mult: float = 3.0,
    lookback: int = 500,
) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Return (middle, lower, upper) for the latest bar, or (None, None, None)."""
    if df is None or len(df) < 2:
        return None, None, None
    bands = nw_envelope_from_ohlc(
        df, bandwidth=bandwidth, mult=mult, lookback=lookback, src_col="Close"
    )
    mid = float(bands["nwe_middle"].iloc[-1])
    low = float(bands["nwe_lower"].iloc[-1])
    up = float(bands["nwe_upper"].iloc[-1])
    if not all(pd.notna(x) for x in (mid, low, up)):
        return None, None, None
    return mid, low, up


__all__ = ["latest_nwe_bands", "ratchet_stop"]
