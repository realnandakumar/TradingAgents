"""Volatility-based trade levels: entry, stoploss, and target.

For each pick we derive an objective stoploss and target from the stock's own
volatility (ATR), so the risk and reward scale with how much the stock actually
moves. This gives the buy list the explicit "Target & Stoploss" the strategy
calls for, computed deterministically rather than guessed by an LLM.

  stoploss = entry - stop_atr_mult * ATR
  risk     = entry - stoploss
  target   = entry + target_rr * risk        (reward-to-risk = target_rr)

ATR uses Wilder's smoothing over ``atr_period`` days.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


def average_true_range(df: pd.DataFrame, period: int = 14) -> Optional[float]:
    """Latest ATR (Wilder) from an OHLC frame, or None if insufficient data."""
    if not {"High", "Low", "Close"}.issubset(df.columns) or len(df) < period + 1:
        return None
    high, low, close = df["High"], df["Low"], df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    atr = tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    val = float(atr.iloc[-1])
    return val if np.isfinite(val) and val > 0 else None


def compute_levels(
    df: pd.DataFrame,
    entry: Optional[float] = None,
    stop_atr_mult: float = 2.0,
    target_rr: float = 2.0,
    atr_period: int = 14,
) -> Optional[dict]:
    """Return entry/stoploss/target levels for the latest bar.

    Returns None when ATR can't be computed. ``entry`` defaults to the latest
    close. Percentages are relative to entry for quick reading.
    """
    atr = average_true_range(df, period=atr_period)
    if atr is None:
        return None
    if entry is None:
        entry = float(df["Close"].iloc[-1])
    if entry <= 0:
        return None

    stoploss = entry - stop_atr_mult * atr
    risk = entry - stoploss
    target = entry + target_rr * risk
    return {
        "entry": round(entry, 2),
        "atr": round(atr, 2),
        "stoploss": round(stoploss, 2),
        "target": round(target, 2),
        "stop_pct": round(-100 * risk / entry, 2),       # negative: downside to stop
        "target_pct": round(100 * (target - entry) / entry, 2),
        "rr": round(target_rr, 2),
    }
