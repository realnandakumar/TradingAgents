"""Objective technical-pattern detectors for screening.

Each detector takes a daily OHLCV DataFrame and returns a :class:`Signal`
(fired? + a short human explanation). They are deliberately heuristic and
tunable. Reliability varies by pattern -- see ``WEIGHTS`` and the module
docstring notes -- which is exactly why the paper-trading layer records which
signals fired on each pick, so we can later learn which actually predict
winners.

Detectors:
- ``rsi_breakout``        momentum crossing up through a threshold      (reliable)
- ``breakout_soon``       range contraction ("squeeze") near highs      (reliable)
- ``ascending_triangle``  flat resistance + rising lows                 (approximate)
- ``cup_and_handle``      rounded base, recovery, shallow handle        (best-effort)
- ``pullback_in_uptrend`` Elliott-ish dip-and-resume inside an uptrend  (approximate)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

import numpy as np
import pandas as pd

# Higher weight = more trusted signal. Tunable.
WEIGHTS: Dict[str, float] = {
    "rsi_breakout": 1.0,
    "breakout_soon": 1.0,
    "ascending_triangle": 0.8,
    "cup_and_handle": 0.8,
    "pullback_in_uptrend": 0.6,
}


@dataclass
class Signal:
    name: str
    fired: bool
    detail: str = ""


@dataclass
class PatternScore:
    symbol: str
    score: float                       # weighted sum of fired signals
    fired: List[str] = field(default_factory=list)
    signals: Dict[str, Signal] = field(default_factory=dict)

    def summary(self) -> str:
        return ", ".join(self.fired) if self.fired else "none"


# --------------------------------------------------------------------------
# Indicator helpers
# --------------------------------------------------------------------------

def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Wilder's RSI."""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100 - (100 / (1 + rs))
    return out.fillna(100.0)  # all-gains window -> RSI 100


def _swing_points(series: pd.Series, order: int = 5):
    """Indices of local maxima and minima (a point higher/lower than ``order``
    bars on each side). Lightweight ZigZag substitute, no SciPy dependency."""
    vals = series.values
    highs, lows = [], []
    n = len(vals)
    for i in range(order, n - order):
        window = vals[i - order : i + order + 1]
        if vals[i] == window.max() and (window.argmax() == order):
            highs.append(i)
        if vals[i] == window.min() and (window.argmin() == order):
            lows.append(i)
    return highs, lows


# --------------------------------------------------------------------------
# Detectors
# --------------------------------------------------------------------------

def rsi_breakout(df: pd.DataFrame, period: int = 14, level: float = 60.0,
                 lookback: int = 4) -> Signal:
    """Fired when RSI crosses up through ``level`` within the last ``lookback``
    bars and is not yet exhausted (<80)."""
    close = df["Close"]
    if len(close) < period + lookback + 1:
        return Signal("rsi_breakout", False)
    r = rsi(close, period)
    recent = r.iloc[-(lookback + 1):]
    crossed = (recent.shift(1) < level) & (recent >= level)
    now = float(r.iloc[-1])
    fired = bool(crossed.any()) and now < 80.0
    detail = f"RSI={now:.0f} crossed up through {level:.0f}" if fired else ""
    return Signal("rsi_breakout", fired, detail)


def breakout_soon(df: pd.DataFrame, near_pct: float = 0.04,
                  squeeze_ratio: float = 0.75) -> Signal:
    """Price coiling just under resistance: within ``near_pct`` of the 60-day
    high while recent 20-day volatility is compressed vs the 100-day (a
    "squeeze") -- a classic about-to-break-out setup."""
    close = df["Close"]
    high = df["High"] if "High" in df else close
    if len(close) < 100:
        return Signal("breakout_soon", False)
    recent_high = float(high.iloc[-60:].max())
    last = float(close.iloc[-1])
    near = last >= recent_high * (1 - near_pct)

    rng = (df["High"] - df["Low"]) if "High" in df and "Low" in df else close.diff().abs()
    vol_short = float(rng.iloc[-20:].mean())
    vol_long = float(rng.iloc[-100:].mean())
    squeeze = vol_long > 0 and (vol_short / vol_long) <= squeeze_ratio

    fired = near and squeeze
    detail = (
        f"within {(1 - last / recent_high) * 100:.1f}% of 60d high, volatility compressed"
        if fired else ""
    )
    return Signal("breakout_soon", fired, detail)


def ascending_triangle(df: pd.DataFrame, order: int = 5,
                       flat_tol: float = 0.025) -> Signal:
    """Flat resistance (recent swing highs roughly equal) over rising swing
    lows (higher lows). Approximate -- swing detection is heuristic."""
    close = df["Close"]
    if len(close) < 40:
        return Signal("ascending_triangle", False)
    window = close.iloc[-90:]
    highs, lows = _swing_points(window, order=order)
    if len(highs) < 2 or len(lows) < 2:
        return Signal("ascending_triangle", False)

    high_vals = [float(window.iloc[i]) for i in highs[-3:]]
    low_vals = [float(window.iloc[i]) for i in lows[-3:]]
    # Flat top: highs within tolerance band of each other.
    flat = (max(high_vals) - min(high_vals)) / max(high_vals) <= flat_tol
    # Rising bottom: each later swing low above the previous.
    rising = all(b > a for a, b in zip(low_vals, low_vals[1:]))

    fired = flat and rising
    detail = "flat resistance with higher lows" if fired else ""
    return Signal("ascending_triangle", fired, detail)


def cup_and_handle(df: pd.DataFrame, min_bars: int = 50, max_depth: float = 0.5,
                   min_depth: float = 0.12, handle_max: float = 0.15) -> Signal:
    """Best-effort cup-and-handle: a left rim, a rounded decline to a trough
    (cup of ``min_depth``..``max_depth`` deep), a recovery back near the rim,
    then a shallow recent pullback (the handle) with price near the rim.

    Noisy by nature -- treat as a hint, validated downstream by paper P&L.
    """
    close = df["Close"]
    if len(close) < min_bars:
        return Signal("cup_and_handle", False)

    window = close.iloc[-130:] if len(close) >= 130 else close
    vals = window.values
    n = len(vals)
    trough_i = int(np.argmin(vals))
    # Cup needs room on both sides for the rims.
    if trough_i < n * 0.2 or trough_i > n * 0.8:
        return Signal("cup_and_handle", False)

    left_rim = float(vals[:trough_i].max())
    trough = float(vals[trough_i])
    right_section = vals[trough_i:]
    right_rim = float(right_section.max())
    last = float(vals[-1])

    depth = (left_rim - trough) / left_rim if left_rim > 0 else 0.0
    recovered = right_rim >= left_rim * 0.95          # came back to the rim
    handle = (right_rim - last) / right_rim if right_rim > 0 else 0.0
    near_rim = last >= left_rim * 0.9

    fired = (
        min_depth <= depth <= max_depth
        and recovered
        and 0 < handle <= handle_max
        and near_rim
    )
    detail = f"cup depth {depth * 100:.0f}%, handle {handle * 100:.0f}%" if fired else ""
    return Signal("cup_and_handle", fired, detail)


def pullback_in_uptrend(df: pd.DataFrame, dip_min: float = 0.04,
                        dip_max: float = 0.18) -> Signal:
    """Elliott-ish: established uptrend (price>50SMA>200SMA) that recently
    dipped from a local high and is now turning back up -- i.e. resuming the
    trend after a corrective pullback."""
    close = df["Close"]
    if len(close) < 60:
        return Signal("pullback_in_uptrend", False)
    sma50 = close.rolling(50).mean()
    sma200 = close.rolling(200).mean() if len(close) >= 200 else sma50
    last = float(close.iloc[-1])

    uptrend = last > float(sma50.iloc[-1]) and float(sma50.iloc[-1]) >= float(sma200.iloc[-1])
    recent_high = float(close.iloc[-30:].max())
    dip = (recent_high - close.iloc[-10:].min()) / recent_high if recent_high > 0 else 0.0
    pulled_back = dip_min <= float(dip) <= dip_max
    turning_up = last > float(close.iloc[-4:-1].min())  # bouncing off the dip

    fired = uptrend and pulled_back and turning_up
    detail = f"uptrend, {dip * 100:.0f}% pullback resuming" if fired else ""
    return Signal("pullback_in_uptrend", fired, detail)


_DETECTORS: List[Callable[[pd.DataFrame], Signal]] = [
    rsi_breakout,
    breakout_soon,
    ascending_triangle,
    cup_and_handle,
    pullback_in_uptrend,
]


def score_patterns(symbol: str, df: pd.DataFrame) -> PatternScore:
    """Run all detectors on ``df`` and return a weighted composite score."""
    signals: Dict[str, Signal] = {}
    fired: List[str] = []
    score = 0.0
    for det in _DETECTORS:
        try:
            sig = det(df)
        except Exception:  # noqa: BLE001 - a bad detector never sinks the screen
            sig = Signal(det.__name__, False)
        signals[sig.name] = sig
        if sig.fired:
            fired.append(sig.name)
            score += WEIGHTS.get(sig.name, 0.5)
    return PatternScore(symbol=symbol, score=score, fired=fired, signals=signals)
