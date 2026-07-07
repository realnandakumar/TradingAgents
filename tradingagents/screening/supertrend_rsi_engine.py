"""SuperTrend + RSI signal engine (v1.0).

Strategy ID: supertrend_rsi
Independent of swing / momentum / NSS.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from tradingagents.screening.patterns import rsi
from tradingagents.screening.swing_indicators import average_true_range_series, ema, supertrend

STRATEGY_ID = "supertrend_rsi"
STRATEGY_NAME = "SuperTrend + RSI"
STRATEGY_VERSION = "1.0"
MAX_RAW_SCORE = 170.0


@dataclass
class ScoreComponents:
    supertrend_freshness: float = 0.0
    rsi_cross: float = 0.0
    rsi_strength: float = 0.0
    rsi_momentum: float = 0.0
    rsi_ma_cross: float = 0.0
    st_distance: float = 0.0
    candle_strength: float = 0.0
    volume: float = 0.0
    ema_trend: float = 0.0

    @property
    def raw_total(self) -> float:
        return (
            self.supertrend_freshness
            + self.rsi_cross
            + self.rsi_strength
            + self.rsi_momentum
            + self.rsi_ma_cross
            + self.st_distance
            + self.candle_strength
            + self.volume
            + self.ema_trend
        )

    def to_dict(self) -> Dict[str, float]:
        return {
            "supertrend_freshness": self.supertrend_freshness,
            "rsi_cross": self.rsi_cross,
            "rsi_strength": self.rsi_strength,
            "rsi_momentum": self.rsi_momentum,
            "rsi_ma_cross": self.rsi_ma_cross,
            "st_distance": self.st_distance,
            "candle_strength": self.candle_strength,
            "volume": self.volume,
            "ema_trend": self.ema_trend,
            "raw_total": self.raw_total,
        }


@dataclass
class SuperTrendRSISignal:
    symbol: str
    direction: str  # BUY | SELL | NONE
    score: int
    grade: str
    grade_stars: str
    reasons: List[str] = field(default_factory=list)
    components: ScoreComponents = field(default_factory=ScoreComponents)
    rejected: bool = False
    reject_reason: str = ""
    mandatory_pass: bool = False
    rsi: float = 0.0
    supertrend_value: float = 0.0
    close: float = 0.0
    flip_age: int = 0
    stock_name: str = ""
    sector: str = ""

    def to_dict(self) -> dict:
        return {
            "strategy_id": STRATEGY_ID,
            "strategy_name": STRATEGY_NAME,
            "version": STRATEGY_VERSION,
            "symbol": self.symbol,
            "direction": self.direction,
            "score": self.score,
            "grade": self.grade,
            "grade_stars": self.grade_stars,
            "reasons": self.reasons,
            "components": self.components.to_dict(),
            "rejected": self.rejected,
            "reject_reason": self.reject_reason,
            "mandatory_pass": self.mandatory_pass,
            "rsi": self.rsi,
            "supertrend_value": self.supertrend_value,
            "close": self.close,
            "flip_age": self.flip_age,
        }


def _grade(score: int) -> Tuple[str, str]:
    if score >= 95:
        return "Elite", "★★★★★"
    if score >= 90:
        return "Excellent", "★★★★☆"
    if score >= 80:
        return "Strong", "★★★★"
    if score >= 70:
        return "Good", "★★★"
    if score >= 60:
        return "Average", "★★"
    return "Ignore", "★"


def _normalize_score(raw: float) -> int:
    return int(round((raw / MAX_RAW_SCORE) * 100.0))


def _last_flip_index(trend: pd.Series, to_buy: bool) -> Optional[int]:
    """Index of most recent flip; to_buy=True finds Sell->Buy."""
    if len(trend) < 2:
        return None
    target = 1 if to_buy else -1
    prior = -1 if to_buy else 1
    for i in range(len(trend) - 1, 0, -1):
        if int(trend.iloc[i - 1]) == prior and int(trend.iloc[i]) == target:
            return i
    return None


def _flip_age(latest_idx: int, flip_idx: int) -> int:
    """1 = crossover bar, 2 = next bar, etc."""
    return latest_idx - flip_idx + 1


def _freshness_points(age: int) -> float:
    table = {1: 40.0, 2: 35.0, 3: 30.0, 4: 20.0, 5: 10.0}
    return table.get(age, 0.0)


def _rsi_cross_points(rsi_series: pd.Series, direction: str, flip_idx: int) -> float:
    latest = float(rsi_series.iloc[-1])
    if not np.isfinite(latest):
        return 0.0

    crossed_this = False
    if len(rsi_series) >= 2 and flip_idx >= 1:
        prev = float(rsi_series.iloc[flip_idx - 1])
        cur = float(rsi_series.iloc[flip_idx])
        if np.isfinite(prev) and np.isfinite(cur):
            if direction == "BUY" and prev <= 50 < cur:
                crossed_this = True
            if direction == "SELL" and prev >= 50 > cur:
                crossed_this = True
    if not crossed_this and len(rsi_series) >= 2:
        prev = float(rsi_series.iloc[-2])
        cur = float(rsi_series.iloc[-1])
        if np.isfinite(prev) and np.isfinite(cur):
            if direction == "BUY" and prev <= 50 < cur:
                crossed_this = True
            if direction == "SELL" and prev >= 50 > cur:
                crossed_this = True

    if crossed_this:
        return 25.0

    above = latest > 50 if direction == "BUY" else latest < 50
    if not above and direction == "BUY":
        return 0.0
    if not above and direction == "SELL":
        return 0.0

    candles_above = 0
    for i in range(len(rsi_series) - 1, -1, -1):
        v = float(rsi_series.iloc[i])
        if not np.isfinite(v):
            break
        if direction == "BUY" and v > 50:
            candles_above += 1
        elif direction == "SELL" and v < 50:
            candles_above += 1
        else:
            break

    if 1 <= candles_above <= 3:
        return 15.0
    if candles_above > 3:
        return 5.0
    return 0.0


def _rsi_strength_points(rsi_val: float, direction: str) -> float:
    if not np.isfinite(rsi_val):
        return 0.0
    if direction == "BUY":
        bands = [(50, 55, 10), (55, 60, 15), (60, 65, 20), (65, 70, 25), (70, 75, 20), (75, 80, 10), (80, 101, 5)]
        for lo, hi, pts in bands:
            if lo <= rsi_val < hi:
                return float(pts)
        return 0.0
    bands = [(45, 50, 10), (40, 45, 15), (35, 40, 20), (30, 35, 25), (25, 30, 20), (20, 25, 10), (-1, 20, 5)]
    for lo, hi, pts in bands:
        if lo < rsi_val <= hi:
            return float(pts)
    return 0.0


def _rsi_momentum_points(rsi_series: pd.Series, direction: str) -> float:
    if len(rsi_series) < 2:
        return 0.0
    delta = float(rsi_series.iloc[-1]) - float(rsi_series.iloc[-2])
    if not np.isfinite(delta):
        return 0.0
    if direction == "BUY":
        if delta > 5:
            return 15.0
        if delta >= 3:
            return 10.0
        if delta >= 1:
            return 5.0
        return 0.0
    if delta < -5:
        return 15.0
    if delta <= -3:
        return 10.0
    if delta <= -1:
        return 5.0
    return 0.0


def _rsi_ma_cross_points(rsi_series: pd.Series, direction: str, sma_len: int) -> float:
    if len(rsi_series) < sma_len + 2:
        return 0.0
    rsi_ma = rsi_series.rolling(sma_len).mean()
    prev_r, cur_r = float(rsi_series.iloc[-2]), float(rsi_series.iloc[-1])
    prev_m, cur_m = float(rsi_ma.iloc[-2]), float(rsi_ma.iloc[-1])
    if not all(np.isfinite(x) for x in (prev_r, cur_r, prev_m, cur_m)):
        return 0.0
    if direction == "BUY" and prev_r <= prev_m and cur_r > cur_m:
        return 15.0
    if direction == "SELL" and prev_r >= prev_m and cur_r < cur_m:
        return 15.0
    return 0.0


def _st_distance_points(close: float, st_val: float, atr_val: float) -> float:
    if atr_val <= 0 or not np.isfinite(atr_val):
        return 0.0
    dist = abs(close - st_val) / atr_val
    if dist <= 0.5:
        return 15.0
    if dist <= 1.0:
        return 10.0
    return 0.0


def _candle_strength_points(open_: float, high: float, low: float, close: float) -> float:
    rng = high - low
    if rng <= 0:
        return 0.0
    body_pct = abs(close - open_) / rng * 100.0
    if body_pct >= 70:
        return 15.0
    if body_pct >= 50:
        return 10.0
    if body_pct >= 30:
        return 5.0
    return 0.0


def _volume_points(volume: float, vol_ema: float) -> float:
    if vol_ema <= 0 or not np.isfinite(vol_ema):
        return 0.0
    return 10.0 if volume > vol_ema else 0.0


def _ema_trend_points(close: float, ema20: float, direction: str) -> float:
    if not np.isfinite(ema20):
        return 0.0
    if direction == "BUY" and close > ema20:
        return 10.0
    if direction == "SELL" and close < ema20:
        return 10.0
    return 0.0


def _check_mandatory_buy(
    close: pd.Series,
    st_line: pd.Series,
    trend: pd.Series,
    rsi_series: pd.Series,
    config: Optional[dict] = None,
) -> Tuple[bool, str, Optional[int]]:
    flip_idx = _last_flip_index(trend, to_buy=True)
    if flip_idx is None:
        return False, "no SuperTrend Sell->Buy flip", None
    if flip_idx < 1 or flip_idx >= len(close) - 1:
        return False, "flip too recent — no confirmation candle yet", flip_idx

    cfg = config or {}
    max_age = int(cfg.get("strsi_mandatory_flip_max_age", 0))
    if max_age > 0:
        age = _flip_age(len(close) - 1, flip_idx)
        if age > max_age:
            return False, f"flip too old ({age} bars, max {max_age})", flip_idx

    if float(close.iloc[flip_idx - 1]) >= float(st_line.iloc[flip_idx - 1]):
        return False, "pre-crossover candle did not close below SuperTrend", flip_idx
    if float(close.iloc[flip_idx]) <= float(st_line.iloc[flip_idx]):
        return False, "crossover candle did not close above SuperTrend", flip_idx

    confirm_idx = flip_idx + 1
    if float(close.iloc[confirm_idx]) <= float(st_line.iloc[confirm_idx]):
        return False, "confirmation candle did not close above SuperTrend", flip_idx
    if float(close.iloc[-1]) <= float(st_line.iloc[-1]):
        return False, "latest close not above SuperTrend", flip_idx

    if float(rsi_series.iloc[-1]) <= 50:
        return False, "RSI not above 50", flip_idx

    if int(trend.iloc[-1]) != 1:
        return False, "SuperTrend not GREEN", flip_idx

    return True, "", flip_idx


def _check_mandatory_sell(
    close: pd.Series,
    st_line: pd.Series,
    trend: pd.Series,
    rsi_series: pd.Series,
    config: Optional[dict] = None,
) -> Tuple[bool, str, Optional[int]]:
    flip_idx = _last_flip_index(trend, to_buy=False)
    if flip_idx is None:
        return False, "no SuperTrend Buy->Sell flip", None
    if flip_idx < 1 or flip_idx >= len(close) - 1:
        return False, "flip too recent — no confirmation candle yet", flip_idx

    cfg = config or {}
    max_age = int(cfg.get("strsi_mandatory_flip_max_age", 0))
    if max_age > 0:
        age = _flip_age(len(close) - 1, flip_idx)
        if age > max_age:
            return False, f"flip too old ({age} bars, max {max_age})", flip_idx

    if float(close.iloc[flip_idx - 1]) <= float(st_line.iloc[flip_idx - 1]):
        return False, "pre-crossover candle did not close above SuperTrend", flip_idx
    if float(close.iloc[flip_idx]) >= float(st_line.iloc[flip_idx]):
        return False, "crossover candle did not close below SuperTrend", flip_idx

    confirm_idx = flip_idx + 1
    if float(close.iloc[confirm_idx]) >= float(st_line.iloc[confirm_idx]):
        return False, "confirmation candle did not close below SuperTrend", flip_idx
    if float(close.iloc[-1]) >= float(st_line.iloc[-1]):
        return False, "latest close not below SuperTrend", flip_idx

    if float(rsi_series.iloc[-1]) >= 50:
        return False, "RSI not below 50", flip_idx

    if int(trend.iloc[-1]) != -1:
        return False, "SuperTrend not RED", flip_idx

    return True, "", flip_idx


def _apply_filters(
    df: pd.DataFrame,
    direction: str,
    trend: pd.Series,
    st_line: pd.Series,
    config: dict,
) -> Tuple[bool, str]:
    close = df["Close"]
    open_ = df["Open"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]

    lookback = int(config.get("strsi_opposite_flip_lookback", 3))
    for i in range(-lookback, 0):
        if i - 1 >= -len(trend):
            prev_t, cur_t = int(trend.iloc[i - 1]), int(trend.iloc[i])
            if direction == "BUY" and prev_t == 1 and cur_t == -1:
                return True, "opposite Sell flip within last 3 candles"
            if direction == "SELL" and prev_t == -1 and cur_t == 1:
                return True, "opposite Buy flip within last 3 candles"

    atr14 = float(average_true_range_series(df, 14).iloc[-1])
    min_atr = float(config.get("strsi_min_atr", 0.0))
    if min_atr > 0 and (not np.isfinite(atr14) or atr14 < min_atr):
        return True, f"ATR {atr14:.2f} below minimum volatility"

    o, h, l, c = float(open_.iloc[-1]), float(high.iloc[-1]), float(low.iloc[-1]), float(close.iloc[-1])
    rng = h - l
    if rng > 0 and abs(c - o) / rng < float(config.get("strsi_min_body_pct", 0.15)):
        pct = int(float(config.get("strsi_min_body_pct", 0.15)) * 100)
        return True, f"candle body below {pct}% of range"

    max_dist = float(config.get("strsi_max_st_distance_atr", 3.0))
    st_val = float(st_line.iloc[-1])
    if atr14 > 0 and abs(c - st_val) / atr14 > max_dist:
        return True, f"price more than {max_dist:g} ATR from SuperTrend"

    vol_ratio = float(config.get("strsi_min_volume_ratio", 0.60))
    vol_avg = float(volume.iloc[-20:].mean()) if len(volume) >= 20 else float(volume.mean())
    if vol_avg > 0 and float(volume.iloc[-1]) < vol_avg * vol_ratio:
        pct = int(vol_ratio * 100)
        return True, f"volume below {pct}% of 20-period average"

    return False, ""


def _build_reasons(direction: str, components: ScoreComponents, ctx: dict) -> List[str]:
    reasons: List[str] = []
    if direction == "BUY":
        reasons.append("Confirmed SuperTrend Buy")
    else:
        reasons.append("Confirmed SuperTrend Sell")

    if components.rsi_cross >= 25:
        reasons.append(f"RSI crossed {'above' if direction == 'BUY' else 'below'} 50")
    elif components.rsi_cross > 0:
        reasons.append(f"RSI {'above' if direction == 'BUY' else 'below'} 50")

    if ctx.get("rsi") is not None:
        reasons.append(f"RSI = {ctx['rsi']:.1f}")

    if components.rsi_ma_cross >= 15:
        reasons.append(f"RSI crossed {'above' if direction == 'BUY' else 'below'} SMA9")

    if components.candle_strength >= 10:
        reasons.append("Strong bullish candle" if direction == "BUY" else "Strong bearish candle")
    elif components.candle_strength >= 5:
        reasons.append("Moderate candle strength")

    if components.volume >= 10:
        reasons.append("Volume above average")

    if components.ema_trend >= 10:
        reasons.append(f"{'Above' if direction == 'BUY' else 'Below'} EMA20")

    if components.st_distance >= 10:
        reasons.append("Price near SuperTrend")

    if components.supertrend_freshness >= 35:
        reasons.append("Fresh SuperTrend crossover")

    if components.rsi_momentum >= 10:
        reasons.append("RSI momentum accelerating")

    return reasons


def _score_direction(
    df: pd.DataFrame,
    direction: str,
    config: dict,
    flip_idx: int,
) -> Tuple[ScoreComponents, dict]:
    close = df["Close"]
    open_ = df["Open"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]

    st_period = int(config.get("strsi_supertrend_period", 10))
    st_mult = float(config.get("strsi_supertrend_multiplier", 3.0))
    rsi_len = int(config.get("strsi_rsi_period", 14))
    rsi_ma_len = int(config.get("strsi_rsi_ma_period", 9))

    st_line, trend = supertrend(df, period=st_period, multiplier=st_mult)
    rsi_series = rsi(close, rsi_len)
    atr14 = float(average_true_range_series(df, 14).iloc[-1])
    ema20 = float(ema(close, 20).iloc[-1])
    vol_ema20 = float(ema(volume, 20).iloc[-1])

    latest_idx = len(df) - 1
    age = _flip_age(latest_idx, flip_idx)

    c = ScoreComponents(
        supertrend_freshness=_freshness_points(age),
        rsi_cross=_rsi_cross_points(rsi_series, direction, flip_idx),
        rsi_strength=_rsi_strength_points(float(rsi_series.iloc[-1]), direction),
        rsi_momentum=_rsi_momentum_points(rsi_series, direction),
        rsi_ma_cross=_rsi_ma_cross_points(rsi_series, direction, rsi_ma_len),
        st_distance=_st_distance_points(float(close.iloc[-1]), float(st_line.iloc[-1]), atr14),
        candle_strength=_candle_strength_points(
            float(open_.iloc[-1]), float(high.iloc[-1]), float(low.iloc[-1]), float(close.iloc[-1])
        ),
        volume=_volume_points(float(volume.iloc[-1]), vol_ema20),
        ema_trend=_ema_trend_points(float(close.iloc[-1]), ema20, direction),
    )

    ctx = {
        "rsi": float(rsi_series.iloc[-1]),
        "flip_age": age,
    }
    return c, ctx


def evaluate_supertrend_rsi(
    df: pd.DataFrame,
    config: dict,
    *,
    symbol: str = "",
) -> SuperTrendRSISignal:
    """Evaluate latest bar for BUY/SELL SuperTrend+RSI signal."""
    min_bars = int(config.get("strsi_min_bars", 60))
    empty = SuperTrendRSISignal(symbol=symbol, direction="NONE", score=0, grade="Ignore", grade_stars="★")

    if df is None or len(df) < min_bars:
        empty.reject_reason = "insufficient history"
        empty.rejected = True
        return empty

    st_period = int(config.get("strsi_supertrend_period", 10))
    st_mult = float(config.get("strsi_supertrend_multiplier", 3.0))
    rsi_len = int(config.get("strsi_rsi_period", 14))

    close = df["Close"]
    st_line, trend = supertrend(df, period=st_period, multiplier=st_mult)
    rsi_series = rsi(close, rsi_len)

    buy_ok, buy_reason, buy_flip = _check_mandatory_buy(close, st_line, trend, rsi_series, config)
    sell_ok, sell_reason, sell_flip = _check_mandatory_sell(close, st_line, trend, rsi_series, config)

    direction = "NONE"
    flip_idx: Optional[int] = None
    fail_reason = ""

    if buy_ok and not sell_ok:
        direction = "BUY"
        flip_idx = buy_flip
    elif sell_ok and not buy_ok:
        direction = "SELL"
        flip_idx = sell_flip
    elif buy_ok and sell_ok:
        # Prefer fresher flip
        buy_age = _flip_age(len(df) - 1, buy_flip) if buy_flip is not None else 99
        sell_age = _flip_age(len(df) - 1, sell_flip) if sell_flip is not None else 99
        if buy_age <= sell_age:
            direction, flip_idx = "BUY", buy_flip
        else:
            direction, flip_idx = "SELL", sell_flip
    else:
        empty.reject_reason = buy_reason or sell_reason or "no mandatory signal"
        empty.rejected = True
        return empty

    assert flip_idx is not None
    rejected, reject_reason = _apply_filters(df, direction, trend, st_line, config)
    components, ctx = _score_direction(df, direction, config, flip_idx)
    raw = components.raw_total
    score = _normalize_score(raw)
    grade, stars = _grade(score)
    reasons = _build_reasons(direction, components, ctx)

    sig = SuperTrendRSISignal(
        symbol=symbol,
        direction=direction,
        score=score,
        grade=grade,
        grade_stars=stars,
        reasons=reasons,
        components=components,
        rejected=rejected,
        reject_reason=reject_reason,
        mandatory_pass=True,
        rsi=float(rsi_series.iloc[-1]),
        supertrend_value=float(st_line.iloc[-1]),
        close=float(close.iloc[-1]),
        flip_age=ctx["flip_age"],
    )

    if rejected:
        reasons.insert(0, f"Filtered: {reject_reason}")
        sig.reasons = reasons

    return sig
