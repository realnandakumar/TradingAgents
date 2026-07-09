"""Technical indicators for the momentum continuation screener."""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
import pandas as pd

from tradingagents.screening.swing_indicators import ema


def macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Return (macd line, signal line, histogram)."""
    fast_ema = ema(close, fast)
    slow_ema = ema(close, slow)
    line = fast_ema - slow_ema
    sig = ema(line, signal)
    hist = line - sig
    return line, sig, hist


def avg_volume(volume: pd.Series, lookback: int) -> Optional[float]:
    if len(volume) < lookback:
        return None
    return float(volume.iloc[-lookback:].mean())


def volume_short_above_long(
    volume: pd.Series,
    short: int = 5,
    long: int = 20,
    min_ratio: float = 1.0,
) -> Optional[float]:
    """Return short/long volume ratio when short avg >= long avg * min_ratio."""
    short_avg = avg_volume(volume, short)
    long_avg = avg_volume(volume, long)
    if short_avg is None or long_avg is None or long_avg <= 0:
        return None
    ratio = short_avg / long_avg
    if ratio < min_ratio:
        return None
    return ratio


def supertrend_buy_age(trend: pd.Series) -> int:
    """Consecutive sessions in Buy state ending on the latest bar."""
    if len(trend) == 0 or int(trend.iloc[-1]) != 1:
        return 0
    age = 0
    for i in range(len(trend) - 1, -1, -1):
        if int(trend.iloc[i]) == 1:
            age += 1
        else:
            break
    return age


def pct_above_ema(close: float, ema_val: float) -> float:
    if ema_val <= 0:
        return 0.0
    return 100.0 * (close - ema_val) / ema_val


def adx_rising(adx_series: pd.Series, sessions: int = 3) -> bool:
    if len(adx_series) < sessions + 1:
        return False
    latest = float(adx_series.iloc[-1])
    prior = float(adx_series.iloc[-1 - sessions])
    if not np.isfinite(latest) or not np.isfinite(prior):
        return False
    return latest > prior


def higher_high_after_pullback(
    df: pd.DataFrame,
    ema50: pd.Series,
    pullback_sessions: int = 10,
    hh_lookback: int = 20,
    ema_tolerance: float = 1.02,
) -> bool:
    """Pullback touched EMA50 zone recently, then close breaks prior HH window."""
    if len(df) < max(pullback_sessions, hh_lookback) + 2:
        return False

    close = df["Close"]
    high = df["High"]
    latest_close = float(close.iloc[-1])

    # Prior window high (excluding today)
    prior_high = float(high.iloc[-(hh_lookback + 1) : -1].max())
    if latest_close <= prior_high:
        return False

    # Pullback: close near/below EMA50 in recent sessions
    recent_close = close.iloc[-pullback_sessions:]
    recent_ema = ema50.iloc[-pullback_sessions:]
    touched = any(
        float(c) <= float(e) * ema_tolerance
        for c, e in zip(recent_close, recent_ema)
        if np.isfinite(c) and np.isfinite(e)
    )
    return touched
