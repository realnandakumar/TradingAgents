"""Technical indicators for the Indian equities swing screener."""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
import pandas as pd

from tradingagents.screening.patterns import rsi


def ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _true_range(df: pd.DataFrame) -> pd.Series:
    high, low, close = df["High"], df["Low"], df["Close"]
    prev_close = close.shift(1)
    return pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)


def _wilder_smooth(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()


def average_true_range_series(df: pd.DataFrame, period: int = 14) -> pd.Series:
    return _wilder_smooth(_true_range(df), period)


def supertrend(
    df: pd.DataFrame,
    period: int = 10,
    multiplier: float = 3.0,
) -> Tuple[pd.Series, pd.Series]:
    """Return (supertrend line, trend direction) where trend is 1=Buy, -1=Sell."""
    if len(df) < period + 2:
        empty = pd.Series(dtype=float, index=df.index)
        return empty, pd.Series(dtype=int, index=df.index)

    atr = average_true_range_series(df, period)
    hl2 = (df["High"] + df["Low"]) / 2
    basic_ub = (hl2 + multiplier * atr).to_numpy(dtype=float)
    basic_lb = (hl2 - multiplier * atr).to_numpy(dtype=float)
    close = df["Close"].to_numpy(dtype=float)
    n = len(df)
    start = period

    if not np.isfinite(basic_ub[start]) or not np.isfinite(basic_lb[start]):
        empty = pd.Series(dtype=float, index=df.index)
        return empty, pd.Series(dtype=int, index=df.index)

    final_ub = np.full(n, np.nan)
    final_lb = np.full(n, np.nan)
    final_ub[start] = basic_ub[start]
    final_lb[start] = basic_lb[start]

    for i in range(start + 1, n):
        if not np.isfinite(basic_ub[i]):
            final_ub[i] = final_ub[i - 1]
            final_lb[i] = final_lb[i - 1]
            continue
        if basic_ub[i] < final_ub[i - 1] or close[i - 1] > final_ub[i - 1]:
            final_ub[i] = basic_ub[i]
        else:
            final_ub[i] = final_ub[i - 1]

        if basic_lb[i] > final_lb[i - 1] or close[i - 1] < final_lb[i - 1]:
            final_lb[i] = basic_lb[i]
        else:
            final_lb[i] = final_lb[i - 1]

    st = np.full(n, np.nan)
    trend = np.zeros(n, dtype=int)

    if close[start] <= final_ub[start]:
        st[start] = final_ub[start]
        trend[start] = -1
    else:
        st[start] = final_lb[start]
        trend[start] = 1

    for i in range(start + 1, n):
        if not np.isfinite(final_ub[i]) or not np.isfinite(final_lb[i]):
            st[i] = st[i - 1]
            trend[i] = trend[i - 1]
            continue
        if trend[i - 1] == 1:
            if close[i] <= final_lb[i]:
                st[i] = final_ub[i]
                trend[i] = -1
            else:
                st[i] = final_lb[i]
                trend[i] = 1
        elif close[i] >= final_ub[i]:
            st[i] = final_lb[i]
            trend[i] = 1
        else:
            st[i] = final_ub[i]
            trend[i] = -1

    return (
        pd.Series(st, index=df.index, dtype=float),
        pd.Series(trend, index=df.index, dtype=int),
    )


def adx(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Wilder ADX."""
    if len(df) < period * 2:
        return pd.Series(dtype=float, index=df.index)

    high, low = df["High"], df["Low"]
    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0), up_move, 0.0),
        index=df.index,
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0),
        index=df.index,
    )

    tr = _true_range(df)
    atr = _wilder_smooth(tr, period)
    plus_di = 100 * _wilder_smooth(plus_dm, period) / atr.replace(0, np.nan)
    minus_di = 100 * _wilder_smooth(minus_dm, period) / atr.replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return _wilder_smooth(dx, period)


def relative_volume(volume: pd.Series, lookback: int = 20) -> Optional[float]:
    """Latest bar volume divided by the lookback average."""
    if len(volume) < lookback + 1:
        return None
    avg = float(volume.iloc[-(lookback + 1) : -1].mean())
    if avg <= 0:
        return None
    return float(volume.iloc[-1] / avg)


def volume_spike_pct(volume: pd.Series, lookback: int = 20) -> Optional[float]:
    rel = relative_volume(volume, lookback)
    if rel is None:
        return None
    return round((rel - 1.0) * 100.0, 2)


def supertrend_flip_to_buy_within(trend: pd.Series, sessions: int = 3) -> bool:
    """True when Supertrend is Buy now and flipped Sell→Buy within ``sessions`` bars."""
    if len(trend) < sessions + 1 or int(trend.iloc[-1]) != 1:
        return False
    for i in range(-sessions, 0):
        if int(trend.iloc[i - 1]) == -1 and int(trend.iloc[i]) == 1:
            return True
    return False


def rsi_crossed_above(close: pd.Series, threshold: float = 50.0, period: int = 14) -> bool:
    """True when RSI crossed above threshold on the latest bar."""
    series = rsi(close, period)
    if len(series) < 2 or not np.isfinite(series.iloc[-1]) or not np.isfinite(series.iloc[-2]):
        return False
    return float(series.iloc[-2]) <= threshold < float(series.iloc[-1])


def is_at_new_52_week_low(close: pd.Series, lookback: int = 252, tolerance: float = 0.001) -> bool:
    """True when the latest close is at (or essentially at) the 52-week low."""
    if len(close) < lookback:
        lookback = len(close)
    if lookback < 2:
        return False
    window = close.iloc[-lookback:]
    low = float(window.min())
    latest = float(close.iloc[-1])
    return latest <= low * (1.0 + tolerance)


def compute_trade_levels(
    entry: float,
    stop_loss: float,
    target_1_rr: float = 1.5,
    target_2_rr: float = 2.5,
) -> Optional[dict]:
    """Derive targets and risk-reward from entry and stop."""
    if entry <= 0 or stop_loss <= 0 or stop_loss >= entry:
        return None
    risk = entry - stop_loss
    target_1 = entry + target_1_rr * risk
    target_2 = entry + target_2_rr * risk
    stop_pct = -100.0 * risk / entry
    target_1_pct = 100.0 * (target_1 - entry) / entry
    target_2_pct = 100.0 * (target_2 - entry) / entry
    return {
        "entry": round(entry, 2),
        "stop_loss": round(stop_loss, 2),
        "target_1": round(target_1, 2),
        "target_2": round(target_2, 2),
        "stop_loss_pct": round(stop_pct, 2),
        "target_1_pct": round(target_1_pct, 2),
        "target_2_pct": round(target_2_pct, 2),
        "risk_reward_ratio": round(target_1_rr, 2),
        "risk_reward_ratio_2": round(target_2_rr, 2),
    }
