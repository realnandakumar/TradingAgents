"""v1.7 regime, volatility, volume, and level filters for Pattern Forecast."""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
import pandas as pd

from tradingagents.screening.levels import average_true_range


def stock_regime_ok(
    df: pd.DataFrame,
    ma_period: int = 20,
    min_return_20d_pct: float = 0.0,
) -> Tuple[bool, str]:
    """Stock above MA and optional positive 20d return."""
    if df is None or df.empty or "Close" not in df.columns:
        return False, "no price data"
    close = df["Close"].astype(float)
    if len(close) < ma_period:
        return False, f"need >= {ma_period} bars"
    last = float(close.iloc[-1])
    ma = float(close.rolling(ma_period).mean().iloc[-1])
    if last <= ma:
        return False, f"close {last:.2f} below MA{ma_period} {ma:.2f}"
    if len(close) >= 21:
        ret_20 = 100.0 * (last - float(close.iloc[-21])) / float(close.iloc[-21])
        if ret_20 < min_return_20d_pct:
            return False, f"20d return {ret_20:.1f}% below min {min_return_20d_pct:.1f}%"
        return True, f"above MA{ma_period}, 20d {ret_20:+.1f}%"
    return True, f"above MA{ma_period}"


def weekly_regime_ok(df: pd.DataFrame, ma_period: int = 10) -> Tuple[bool, str]:
    """Weekly close above N-week moving average."""
    if df is None or df.empty or "Close" not in df.columns:
        return True, "no weekly data"
    close = df["Close"].astype(float)
    if not isinstance(close.index, pd.DatetimeIndex):
        return True, "weekly skipped (no datetime index)"
    weekly = close.resample("W").last().dropna()
    if len(weekly) < ma_period:
        return True, f"insufficient weekly bars ({len(weekly)})"
    last = float(weekly.iloc[-1])
    ma = float(weekly.rolling(ma_period).mean().iloc[-1])
    if last > ma:
        return True, f"weekly {last:.2f} > MA{ma_period} {ma:.2f}"
    return False, f"weekly {last:.2f} below MA{ma_period} {ma:.2f}"


def atr_pct_at(df: pd.DataFrame, end_idx: int, period: int = 14) -> Optional[float]:
    """ATR as % of close at a historical bar index."""
    if end_idx < period:
        return None
    slice_df = df.iloc[: end_idx + 1]
    atr = average_true_range(slice_df, period=period)
    if atr is None:
        return None
    close = float(slice_df["Close"].iloc[-1])
    if close <= 0:
        return None
    return 100.0 * atr / close


def atr_regime_match(
    df: pd.DataFrame,
    hist_end_idx: int,
    tolerance_pct: float = 30.0,
    atr_period: int = 14,
) -> Tuple[bool, str]:
    """Analogue-window ATR% within tolerance of today's ATR%."""
    cur = atr_pct_at(df, len(df) - 1, atr_period)
    hist = atr_pct_at(df, hist_end_idx, atr_period)
    if cur is None or hist is None:
        return True, "ATR regime skipped (insufficient data)"
    if cur <= 0:
        return True, "ATR regime skipped"
    diff_pct = abs(hist - cur) / cur * 100.0
    if diff_pct <= tolerance_pct:
        return True, f"ATR% match hist={hist:.2f} cur={cur:.2f} (diff {diff_pct:.0f}%)"
    return False, f"ATR% mismatch hist={hist:.2f} cur={cur:.2f} (diff {diff_pct:.0f}% > {tolerance_pct:.0f}%)"


def volume_fwd_confirmed(
    df: pd.DataFrame,
    fwd_start: int,
    fwd_end: int,
    min_ratio: float = 0.8,
    lookback: int = 20,
) -> Tuple[bool, str]:
    """Forward segment avg volume vs trailing average."""
    if "Volume" not in df.columns:
        return True, "no volume column"
    vol = df["Volume"].astype(float)
    if fwd_end > len(vol) or fwd_start < lookback:
        return True, "volume check skipped"
    fwd_avg = float(vol.iloc[fwd_start:fwd_end].mean())
    trail_avg = float(vol.iloc[fwd_start - lookback : fwd_start].mean())
    if trail_avg <= 0:
        return True, "volume baseline zero"
    ratio = fwd_avg / trail_avg
    if ratio >= min_ratio:
        return True, f"fwd vol ratio {ratio:.2f} (min {min_ratio:.2f})"
    return False, f"fwd vol ratio {ratio:.2f} below {min_ratio:.2f}"


def compute_stop_v17(
    entry: float,
    df: pd.DataFrame,
    analogue_min: float,
    pattern_window: int,
    config: dict,
) -> Optional[float]:
    """ATR + structural low + analogue min; room between 1.2-1.5 ATR, max % cap."""
    atr_period = int(config.get("pattern_forecast_atr_period", 14))
    atr_mult = float(config.get("pattern_forecast_atr_stop_mult", 1.5))
    floor_mult = float(config.get("pattern_forecast_atr_stop_floor_mult", 1.2))
    max_stop_pct = float(config.get("pattern_forecast_max_stop_pct", 7.0))

    atr = average_true_range(df, period=atr_period)
    if atr is None or entry <= 0:
        return None

    atr_stop = entry - atr_mult * atr
    min_distance_stop = entry - floor_mult * atr
    structural = float(df["Low"].astype(float).iloc[-pattern_window:].min())
    candidates = [atr_stop, structural, analogue_min]
    raw = min(candidates)
    widest = entry * (1.0 - max_stop_pct / 100.0)
    if raw < widest:
        raw = widest
    if raw > min_distance_stop:
        raw = min_distance_stop
    if raw <= 0 or raw >= entry:
        return None
    return round(raw, 2)


def cap_target_with_atr(
    entry: float,
    projected_max: float,
    df: pd.DataFrame,
    config: dict,
) -> float:
    """Cap optimistic analogue max-high with ATR-based target."""
    if not bool(config.get("pattern_forecast_use_atr_target_cap", True)):
        return projected_max
    atr_period = int(config.get("pattern_forecast_atr_period", 14))
    target_mult = float(config.get("pattern_forecast_target_atr_mult", 1.5))
    atr = average_true_range(df, period=atr_period)
    if atr is None:
        return projected_max
    atr_target = entry + target_mult * atr
    return round(min(projected_max, atr_target), 2)


def consensus_dispersion_ok(
    pool: list,
    max_dispersion_pct: float,
    current_close: float,
) -> Tuple[bool, str]:
    """Reject when top analogue projections disagree too much."""
    if not pool or current_close <= 0:
        return True, "no pool"
    closes = [c.projected_close for c in pool]
    med = float(np.median(closes))
    if med <= 0:
        return True, "median zero"
    spread = 100.0 * (max(closes) - min(closes)) / med
    if spread <= max_dispersion_pct:
        return True, f"dispersion {spread:.1f}% (max {max_dispersion_pct:.1f}%)"
    return False, f"dispersion {spread:.1f}% exceeds {max_dispersion_pct:.1f}%"
