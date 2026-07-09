"""LuxAlgo Trend Regularity Adaptive Moving Average (TRAMA).

Faithful port of the open-source TradingView Pine script:

    hh = max(sign(change(highest(length))), 0)
    ll = max(sign(change(lowest(length)) * -1), 0)
    tc = pow(sma(hh or ll ? 1 : 0, length), 2)
    ama := nz(ama[1] + tc * (src - ama[1]), src)

Defaults match LuxAlgo: length=100, src=close.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def trama(
    high: pd.Series,
    low: pd.Series,
    src: pd.Series,
    length: int = 100,
) -> pd.Series:
    """Return the TRAMA series aligned to ``src``'s index.

    Args:
        high: High prices (for rolling highest).
        low: Low prices (for rolling lowest).
        src: Source series (LuxAlgo default = close).
        length: Lookback period (LuxAlgo default = 100).
    """
    if length < 1:
        raise ValueError("TRAMA length must be >= 1")
    if len(src) == 0:
        return pd.Series(dtype=float, index=src.index)

    high = high.astype(float)
    low = low.astype(float)
    src = src.astype(float)

    # Rolling highest / lowest over ``length`` bars (inclusive), then
    # detect when a *new* extreme is made vs the prior bar.
    hh_roll = high.rolling(length, min_periods=length).max()
    ll_roll = low.rolling(length, min_periods=length).min()

    hh_change = hh_roll.diff()
    ll_change = ll_roll.diff()

    # Pine: max(sign(change(...)), 0) → 1.0 on new high/low, else 0.0
    # (NaN for early bars → treated as 0 so SMA is well-defined once warm.)
    hh = np.where(hh_change > 0, 1.0, 0.0)
    ll = np.where(ll_change < 0, 1.0, 0.0)  # sign(change * -1) > 0 ⇔ change < 0
    regularity = np.where((hh == 1.0) | (ll == 1.0), 1.0, 0.0)

    # Warm-up bars (insufficient rolling window) contribute 0, matching Pine's
    # na→0 behaviour for sign/change on incomplete highest/lowest.
    regularity = pd.Series(regularity, index=src.index, dtype=float)
    tc = regularity.rolling(length, min_periods=1).mean() ** 2

    ama = np.empty(len(src), dtype=float)
    ama[:] = np.nan
    src_vals = src.to_numpy(dtype=float)
    tc_vals = tc.to_numpy(dtype=float)

    # First value: Pine nz(ama[1] + ..., src) → seed with src when no prior.
    ama[0] = src_vals[0]
    for i in range(1, len(src)):
        prev = ama[i - 1]
        factor = tc_vals[i]
        if not np.isfinite(factor):
            factor = 0.0
        if not np.isfinite(prev):
            ama[i] = src_vals[i]
        else:
            ama[i] = prev + factor * (src_vals[i] - prev)

    return pd.Series(ama, index=src.index, name="trama")


def trama_from_ohlc(df: pd.DataFrame, length: int = 100, src_col: str = "Close") -> pd.Series:
    """Convenience: compute TRAMA from an OHLC DataFrame."""
    if not {"High", "Low", src_col}.issubset(df.columns):
        raise KeyError(f"DataFrame needs High, Low, and {src_col}")
    return trama(df["High"], df["Low"], df[src_col], length=length)
