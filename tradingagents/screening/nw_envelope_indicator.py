"""LuxAlgo Nadaraya-Watson Envelope (non-repainting endpoint).

Faithful port of PyIndicators / LuxAlgo:
    w(i) = exp(-i² / (2 * h²)) for i = 0..lookback-1
    smoothed[t] = sum(src[t-i]*w(i)) / sum(w(i))  (causal, most recent first)
    mae[t] = mean(|src - smoothed|) over available window
    upper = smoothed + mult * mae
    lower = smoothed - mult * mae

Defaults: bandwidth=8.0, mult=3.0, lookback=500, source=Close.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd


def _gauss(i: float, h: float) -> float:
    return math.exp(-(i * i) / (h * h * 2))


def nadaraya_watson_envelope(
    src: pd.Series,
    bandwidth: float = 8.0,
    mult: float = 3.0,
    lookback: int = 500,
) -> pd.DataFrame:
    """Return upper, middle, lower envelope series aligned to ``src``'s index."""
    if bandwidth <= 0:
        raise ValueError("bandwidth must be > 0")
    if mult < 0:
        raise ValueError("mult must be non-negative")
    if lookback < 1:
        raise ValueError("lookback must be >= 1")
    if len(src) == 0:
        idx = src.index
        return pd.DataFrame(
            {"nwe_upper": pd.Series(dtype=float, index=idx),
             "nwe_middle": pd.Series(dtype=float, index=idx),
             "nwe_lower": pd.Series(dtype=float, index=idx)},
        )

    values = src.astype(float).to_numpy()
    n = len(values)
    max_k = min(lookback, n)
    weights = np.array([_gauss(i, bandwidth) for i in range(max_k)])

    smoothed = np.full(n, np.nan)
    for t in range(n):
        available = min(t + 1, max_k)
        w = weights[:available]
        s = values[t - available + 1: t + 1][::-1]
        smoothed[t] = np.nansum(s * w) / np.nansum(w)

    abs_err = np.abs(values - smoothed)
    mae = np.full(n, np.nan)
    for t in range(n):
        window = min(t + 1, max_k)
        mae[t] = np.nanmean(abs_err[t - window + 1: t + 1])

    upper = smoothed + mult * mae
    lower = smoothed - mult * mae

    return pd.DataFrame(
        {
            "nwe_upper": upper,
            "nwe_middle": smoothed,
            "nwe_lower": lower,
        },
        index=src.index,
    )


def nw_envelope_from_ohlc(
    df: pd.DataFrame,
    bandwidth: float = 8.0,
    mult: float = 3.0,
    lookback: int = 500,
    src_col: str = "Close",
) -> pd.DataFrame:
    """Convenience: compute NWE from an OHLC DataFrame."""
    if src_col not in df.columns:
        raise KeyError(f"DataFrame needs {src_col}")
    effective_lookback = min(lookback, len(df))
    return nadaraya_watson_envelope(
        df[src_col].astype(float),
        bandwidth=bandwidth,
        mult=mult,
        lookback=effective_lookback,
    )
