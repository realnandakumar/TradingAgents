"""Classic chart pattern detectors for a pure universe screener."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

from tradingagents.screening.patterns import _swing_points

STRATEGY_ID = "chart_patterns"
STRATEGY_NAME = "Chart Patterns"
STRATEGY_VERSION = "1.3"

PATTERN_CATALOG: Dict[str, dict] = {
    "head_shoulders": {
        "label": "Head & Shoulders",
        "stars": 5,
        "ease": 3,
        "bias": "BEARISH",
    },
    "inverse_head_shoulders": {
        "label": "Inverse Head & Shoulders",
        "stars": 5,
        "ease": 3,
        "bias": "BULLISH",
    },
    "double_top": {
        "label": "Double Top",
        "stars": 5,
        "ease": 5,
        "bias": "BEARISH",
    },
    "double_bottom": {
        "label": "Double Bottom",
        "stars": 5,
        "ease": 5,
        "bias": "BULLISH",
    },
    "ascending_triangle": {
        "label": "Ascending Triangle",
        "stars": 4,
        "ease": 3,
        "bias": "BULLISH",
    },
    "descending_triangle": {
        "label": "Descending Triangle",
        "stars": 4,
        "ease": 3,
        "bias": "BEARISH",
    },
    "rising_wedge": {
        "label": "Rising Wedge",
        "stars": 4,
        "ease": 3,
        "bias": "BEARISH",
    },
    "falling_wedge": {
        "label": "Falling Wedge",
        "stars": 4,
        "ease": 3,
        "bias": "BULLISH",
    },
    "cup_and_handle": {
        "label": "Cup & Handle",
        "stars": 4,
        "ease": 2,
        "bias": "BULLISH",
    },
    "bull_flag": {
        "label": "Bull Flag",
        "stars": 3,
        "ease": 3,
        "bias": "BULLISH",
    },
    "bear_flag": {
        "label": "Bear Flag",
        "stars": 3,
        "ease": 3,
        "bias": "BEARISH",
    },
    "pennant": {
        "label": "Pennant",
        "stars": 3,
        "ease": 3,
        "bias": "NEUTRAL",
    },
    "rectangle": {
        "label": "Rectangle",
        "stars": 3,
        "ease": 5,
        "bias": "NEUTRAL",
    },
}

ALL_PATTERN_IDS = ",".join(PATTERN_CATALOG)
_SWING_ORDER_PATTERNS = frozenset({
    "ascending_triangle",
    "descending_triangle",
    "head_shoulders",
    "inverse_head_shoulders",
    "double_top",
    "double_bottom",
    "rising_wedge",
    "falling_wedge",
    "rectangle",
})


_NEAR_BREAKOUT_STATUSES = frozenset({"APPROACHING", "AT_TRIGGER", "NEAR_TOP", "NEAR_BOTTOM"})


def _compute_trade_levels(
    bias: str,
    setup_status: str,
    trigger: float,
    support: float,
    resistance: float,
) -> Optional[dict]:
    if setup_status not in _NEAR_BREAKOUT_STATUSES:
        return None
    height = resistance - support if resistance > support else 0.0
    entry = stop = t1 = 0.0
    if bias == "BULLISH":
        entry, stop, t1 = trigger, support, trigger + height
    elif bias == "BEARISH":
        entry, stop, t1 = trigger, resistance, trigger - height
    elif setup_status == "NEAR_TOP":
        entry, stop, t1 = resistance, support, resistance + height
    elif setup_status == "NEAR_BOTTOM":
        entry, stop, t1 = support, resistance, support - height
    else:
        return None
    if entry <= 0 or stop <= 0:
        return None
    risk = abs(entry - stop)
    if risk <= 0:
        return None
    reward = abs(t1 - entry)
    return {"stop": stop, "t1": t1, "risk_reward": reward / risk}


@dataclass
class ChartPatternSignal:
    symbol: str
    pattern_id: str
    pattern_name: str
    bias: str
    reliability: int
    ease: int
    confidence: float = 0.0
    close: float = 0.0
    pattern_age: int = 0
    support_level: float = 0.0
    resistance_level: float = 0.0
    trigger_level: float = 0.0
    setup_status: str = ""
    distance_to_trigger_pct: float = 0.0
    pattern_position_pct: float = 0.0
    actionability_score: float = 0.0
    remark: str = ""
    detail: str = ""
    rejected: bool = False
    reject_reason: str = ""
    stock_name: str = ""
    sector: str = ""
    reasons: List[str] = field(default_factory=list)

    @property
    def stars_label(self) -> str:
        return "*" * self.reliability

    def to_dict(self) -> dict:
        out = {
            "strategy_id": STRATEGY_ID,
            "strategy_name": STRATEGY_NAME,
            "version": STRATEGY_VERSION,
            "symbol": self.symbol,
            "pattern_id": self.pattern_id,
            "pattern_name": self.pattern_name,
            "bias": self.bias,
            "reliability": self.reliability,
            "ease": self.ease,
            "confidence": self.confidence,
            "close": self.close,
            "pattern_age": self.pattern_age,
            "support_level": self.support_level,
            "resistance_level": self.resistance_level,
            "trigger_level": self.trigger_level,
            "setup_status": self.setup_status,
            "distance_to_trigger_pct": self.distance_to_trigger_pct,
            "pattern_position_pct": self.pattern_position_pct,
            "actionability_score": self.actionability_score,
            "remark": self.remark,
            "detail": self.detail,
            "rejected": self.rejected,
            "reject_reason": self.reject_reason,
            "stock_name": self.stock_name,
            "sector": self.sector,
            "reasons": self.reasons,
        }
        levels = _compute_trade_levels(
            self.bias,
            self.setup_status,
            self.trigger_level,
            self.support_level,
            self.resistance_level,
        )
        if levels:
            out["stop_loss"] = levels["stop"]
            out["target_1"] = levels["t1"]
            out["risk_reward_ratio"] = round(levels["risk_reward"], 2)
        return out


@dataclass
class PatternMatch:
    confidence: float
    detail: str
    end_idx: int
    support: Optional[float] = None
    resistance: Optional[float] = None


def _completed_df(df: pd.DataFrame, exclude_today: bool) -> pd.DataFrame:
    if exclude_today and len(df) > 1:
        return df.iloc[:-1].copy()
    return df


def _window_offset(df: pd.DataFrame, window: pd.DataFrame) -> int:
    return len(df) - len(window)


@dataclass
class SetupAssessment:
    ok: bool
    reject_reason: str = ""
    status: str = ""
    distance_pct: float = 0.0
    position_pct: float = 0.0
    score: float = 0.0


def _range_position(last: float, support: float, resistance: float) -> float:
    span = resistance - support
    if span <= 0:
        return 0.5
    return float(np.clip((last - support) / span, 0.0, 1.0))


def _assess_setup(
    match: PatternMatch,
    df: pd.DataFrame,
    bias: str,
    config: dict,
) -> SetupAssessment:
    max_age = int(config.get("chart_pattern_max_age_days", 14))
    max_breakout = float(config.get("chart_pattern_max_breakout_pct", 3.0)) / 100.0
    max_inval = float(config.get("chart_pattern_max_invalidation_pct", 5.0)) / 100.0
    max_dist = float(config.get("chart_pattern_max_distance_to_trigger_pct", 5.0))
    min_pos_bull = float(config.get("chart_pattern_min_position_pct", 0.40))
    max_pos_bear = float(config.get("chart_pattern_max_position_pct", 0.60))
    require_actionable = bool(config.get("chart_pattern_require_actionable", True))

    bars_since = len(df) - 1 - match.end_idx
    if bars_since >= max_age:
        return SetupAssessment(False, f"pattern {bars_since}d old (need <{max_age}d)")

    if not require_actionable:
        return SetupAssessment(True, status="OPEN", score=50.0)

    last = float(df["Close"].iloc[-1])
    support = match.support or 0.0
    resistance = match.resistance or 0.0
    has_range = support > 0 and resistance > support

    if bias == "BULLISH":
        trigger = resistance
        if trigger <= 0:
            return SetupAssessment(False, "missing trigger level")
        distance_pct = max(0.0, (trigger - last) / trigger * 100.0)
        position_pct = _range_position(last, support, resistance) if has_range else 0.5

        if support and last < support * (1 - max_inval):
            return SetupAssessment(False, "invalidated below support")
        if last > trigger * (1 + max_breakout):
            return SetupAssessment(False, f"breakout +{(last / trigger - 1) * 100:.1f}% past trigger")
        if has_range and last < support * 0.99:
            return SetupAssessment(False, "price below pattern support")
        if distance_pct > max_dist:
            return SetupAssessment(False, f"{distance_pct:.1f}% from trigger (max {max_dist:.0f}%)")
        if has_range and position_pct < min_pos_bull:
            return SetupAssessment(False, "still at bottom of pattern, not coiling for breakout")

        status = "AT_TRIGGER" if distance_pct <= 1.5 else "APPROACHING"
        pos_quality = min(1.0, (position_pct - min_pos_bull) / max(1e-9, 1.0 - min_pos_bull))

    elif bias == "BEARISH":
        trigger = support
        if trigger <= 0:
            return SetupAssessment(False, "missing trigger level")
        distance_pct = max(0.0, (last - trigger) / trigger * 100.0)
        position_pct = _range_position(last, support, resistance) if has_range else 0.5

        if resistance and last > resistance * (1 + max_inval):
            return SetupAssessment(False, "invalidated above resistance")
        if last < trigger * (1 - max_breakout):
            return SetupAssessment(False, f"breakdown -{(1 - last / trigger) * 100:.1f}% past trigger")
        if has_range and last > resistance * 1.01:
            return SetupAssessment(False, "price above pattern resistance")
        if distance_pct > max_dist:
            return SetupAssessment(False, f"{distance_pct:.1f}% from trigger (max {max_dist:.0f}%)")
        if has_range and position_pct > max_pos_bear:
            return SetupAssessment(False, "still at top of pattern, not coiling for breakdown")

        status = "AT_TRIGGER" if distance_pct <= 1.5 else "APPROACHING"
        pos_quality = min(1.0, (max_pos_bear - position_pct) / max(1e-9, max_pos_bear))

    else:
        if not has_range:
            return SetupAssessment(False, "missing pattern range")
        dist_top = max(0.0, (resistance - last) / resistance * 100.0)
        dist_bot = max(0.0, (last - support) / support * 100.0)
        distance_pct = min(dist_top, dist_bot)
        position_pct = _range_position(last, support, resistance)

        if last > resistance * (1 + max_breakout):
            return SetupAssessment(False, "broke above range")
        if last < support * (1 - max_breakout):
            return SetupAssessment(False, "broke below range")
        if distance_pct > max_dist:
            return SetupAssessment(False, f"{distance_pct:.1f}% from boundary (max {max_dist:.0f}%)")

        status = "NEAR_TOP" if dist_top <= dist_bot else "NEAR_BOTTOM"
        pos_quality = 1.0 - abs(position_pct - 0.5) * 2.0

    proximity = max(0.0, 1.0 - distance_pct / max(max_dist, 1e-9))
    recency = max(0.0, 1.0 - bars_since / max(max_age, 1))
    score = round(40.0 * proximity + 30.0 * recency + 30.0 * pos_quality, 1)

    return SetupAssessment(
        ok=True,
        status=status,
        distance_pct=round(distance_pct, 2),
        position_pct=round(position_pct * 100.0, 1),
        score=score,
    )


def _window(df: pd.DataFrame, bars: int) -> pd.DataFrame:
    return df.iloc[-bars:] if len(df) > bars else df


def _pct_diff(a: float, b: float) -> float:
    base = max(abs(a), abs(b), 1e-9)
    return abs(a - b) / base


def _line_slope(indices: List[int], values: List[float]) -> float:
    if len(indices) < 2:
        return 0.0
    x = np.array(indices, dtype=float)
    y = np.array(values, dtype=float)
    if np.allclose(x, x[0]):
        return 0.0
    slope, _ = np.polyfit(x, y, 1)
    return float(slope)


def _hit(
    pattern_id: str,
    symbol: str,
    close: float,
    match: PatternMatch,
    df: pd.DataFrame,
    config: dict,
) -> Optional[ChartPatternSignal]:
    meta = PATTERN_CATALOG[pattern_id]
    assessment = _assess_setup(match, df, meta["bias"], config)
    if not assessment.ok:
        return None

    age = len(df) - 1 - match.end_idx
    trigger = match.resistance if meta["bias"] == "BULLISH" else match.support
    if meta["bias"] == "NEUTRAL" and match.resistance:
        trigger = match.resistance if assessment.status == "NEAR_TOP" else match.support
    detail = (
        f"{match.detail} | {assessment.status} | "
        f"{assessment.distance_pct:.1f}% to trigger | age {age}d"
    )
    remark = f"{meta['label']} ({meta['bias']}) — {detail}"
    reasons = [
        f"Pattern: {meta['label']}",
        f"Reliability: {meta['stars']}/5 · Detection ease: {meta['ease']}/5",
        f"Bias: {meta['bias']}",
        f"Setup: {assessment.status} · actionability {assessment.score:.0f}/100",
        f"Distance to trigger: {assessment.distance_pct:.1f}%",
        f"Position in pattern: {assessment.position_pct:.0f}% (support to resistance)",
        f"Pattern age: {age} trading days (must be <{config.get('chart_pattern_max_age_days', 14)})",
        f"Trigger: {trigger:.2f}" if trigger else "Trigger: n/a",
    ]
    if bool(config.get("chart_pattern_exclude_today", True)):
        reasons.append("Evaluated on completed sessions only; today's bar excluded")
    reasons.append(match.detail)
    return ChartPatternSignal(
        symbol=symbol,
        pattern_id=pattern_id,
        pattern_name=meta["label"],
        bias=meta["bias"],
        reliability=meta["stars"],
        ease=meta["ease"],
        confidence=round(match.confidence, 1),
        close=round(close, 2),
        pattern_age=age,
        support_level=round(match.support or 0.0, 2),
        resistance_level=round(match.resistance or 0.0, 2),
        trigger_level=round(trigger or 0.0, 2),
        setup_status=assessment.status,
        distance_to_trigger_pct=assessment.distance_pct,
        pattern_position_pct=assessment.position_pct,
        actionability_score=assessment.score,
        remark=remark,
        detail=detail,
        reasons=reasons,
    )


def detect_double_top(df: pd.DataFrame, order: int = 5, flat_tol: float = 0.025) -> Optional[PatternMatch]:
    window = _window(df, 120)
    close = window["Close"]
    highs, _ = _swing_points(close, order=order)
    if len(highs) < 2:
        return None
    h_idx = highs[-2:]
    h_vals = [float(close.iloc[i]) for i in h_idx]
    if _pct_diff(h_vals[0], h_vals[1]) > flat_tol:
        return None
    level = (h_vals[0] + h_vals[1]) / 2.0
    last = float(close.iloc[-1])
    if last > level * 1.03:
        return None
    neckline = float(close.iloc[h_idx[0]: h_idx[1] + 1].min())
    conf = 70.0 + 30.0 * (1.0 - _pct_diff(h_vals[0], h_vals[1]) / flat_tol)
    offset = _window_offset(df, window)
    return PatternMatch(
        confidence=conf,
        detail=f"twin peaks near {level:.2f}, price at {last:.2f}",
        end_idx=offset + h_idx[-1],
        support=neckline,
        resistance=level,
    )


def detect_double_bottom(df: pd.DataFrame, order: int = 5, flat_tol: float = 0.025) -> Optional[PatternMatch]:
    window = _window(df, 120)
    close = window["Close"]
    _, lows = _swing_points(close, order=order)
    if len(lows) < 2:
        return None
    l_idx = lows[-2:]
    l_vals = [float(close.iloc[i]) for i in l_idx]
    if _pct_diff(l_vals[0], l_vals[1]) > flat_tol:
        return None
    level = (l_vals[0] + l_vals[1]) / 2.0
    last = float(close.iloc[-1])
    if last < level * 0.97:
        return None
    neckline = float(close.iloc[l_idx[0]: l_idx[1] + 1].max())
    conf = 70.0 + 30.0 * (1.0 - _pct_diff(l_vals[0], l_vals[1]) / flat_tol)
    offset = _window_offset(df, window)
    return PatternMatch(
        confidence=conf,
        detail=f"twin troughs near {level:.2f}, price at {last:.2f}",
        end_idx=offset + l_idx[-1],
        support=level,
        resistance=neckline,
    )


def detect_head_shoulders(df: pd.DataFrame, order: int = 5, shoulder_tol: float = 0.04) -> Optional[PatternMatch]:
    window = _window(df, 140)
    close = window["Close"]
    highs, _ = _swing_points(close, order=order)
    if len(highs) < 3:
        return None
    idx = highs[-3:]
    vals = [float(close.iloc[i]) for i in idx]
    left, head, right = vals
    if not (head > left * 1.03 and head > right * 1.03):
        return None
    if _pct_diff(left, right) > shoulder_tol:
        return None
    neckline = min(float(close.iloc[idx[0]: idx[2] + 1].min()), left, right)
    last = float(close.iloc[-1])
    conf = 65.0 + 35.0 * (1.0 - _pct_diff(left, right) / shoulder_tol)
    offset = _window_offset(df, window)
    return PatternMatch(
        confidence=conf,
        detail=f"head {head:.2f} above shoulders {left:.2f}/{right:.2f}, close {last:.2f}",
        end_idx=offset + idx[-1],
        support=neckline,
        resistance=head,
    )


def detect_inverse_head_shoulders(df: pd.DataFrame, order: int = 5, shoulder_tol: float = 0.04) -> Optional[PatternMatch]:
    window = _window(df, 140)
    close = window["Close"]
    _, lows = _swing_points(close, order=order)
    if len(lows) < 3:
        return None
    idx = lows[-3:]
    vals = [float(close.iloc[i]) for i in idx]
    left, head, right = vals
    if not (head < left * 0.97 and head < right * 0.97):
        return None
    if _pct_diff(left, right) > shoulder_tol:
        return None
    neckline = max(float(close.iloc[idx[0]: idx[2] + 1].max()), left, right)
    last = float(close.iloc[-1])
    conf = 65.0 + 35.0 * (1.0 - _pct_diff(left, right) / shoulder_tol)
    offset = _window_offset(df, window)
    return PatternMatch(
        confidence=conf,
        detail=f"inverse head {head:.2f} below shoulders {left:.2f}/{right:.2f}, close {last:.2f}",
        end_idx=offset + idx[-1],
        support=head,
        resistance=neckline,
    )


def detect_descending_triangle(df: pd.DataFrame, order: int = 5, flat_tol: float = 0.025) -> Optional[PatternMatch]:
    window = _window(df, 90)
    close = window["Close"]
    highs, lows = _swing_points(close, order=order)
    if len(highs) < 2 or len(lows) < 2:
        return None
    low_vals = [float(close.iloc[i]) for i in lows[-3:]]
    high_vals = [float(close.iloc[i]) for i in highs[-3:]]
    flat = (max(low_vals) - min(low_vals)) / max(low_vals) <= flat_tol
    falling = all(b < a for a, b in zip(high_vals, high_vals[1:]))
    if not (flat and falling):
        return None
    offset = _window_offset(df, window)
    return PatternMatch(
        confidence=72.0,
        detail="flat support with lower highs",
        end_idx=offset + max(highs[-1], lows[-1]),
        support=min(low_vals),
        resistance=max(high_vals),
    )


def detect_rising_wedge(df: pd.DataFrame, order: int = 5) -> Optional[PatternMatch]:
    window = _window(df, 90)
    close = window["Close"]
    highs, lows = _swing_points(close, order=order)
    if len(highs) < 3 or len(lows) < 3:
        return None
    h_idx, h_vals = highs[-3:], [float(close.iloc[i]) for i in highs[-3:]]
    l_idx, l_vals = lows[-3:], [float(close.iloc[i]) for i in lows[-3:]]
    hs, ls = _line_slope(h_idx, h_vals), _line_slope(l_idx, l_vals)
    if hs <= 0 or ls <= 0 or hs >= ls:
        return None
    span_start = float(close.iloc[h_idx[0]] - close.iloc[l_idx[0]])
    span_end = float(close.iloc[h_idx[-1]] - close.iloc[l_idx[-1]])
    if span_end >= span_start * 0.85:
        return None
    offset = _window_offset(df, window)
    return PatternMatch(
        confidence=68.0,
        detail="rising converging highs/lows (bearish wedge)",
        end_idx=offset + max(h_idx[-1], l_idx[-1]),
        support=l_vals[-1],
        resistance=h_vals[-1],
    )


def detect_falling_wedge(df: pd.DataFrame, order: int = 5) -> Optional[PatternMatch]:
    window = _window(df, 90)
    close = window["Close"]
    highs, lows = _swing_points(close, order=order)
    if len(highs) < 3 or len(lows) < 3:
        return None
    h_idx, h_vals = highs[-3:], [float(close.iloc[i]) for i in highs[-3:]]
    l_idx, l_vals = lows[-3:], [float(close.iloc[i]) for i in lows[-3:]]
    hs, ls = _line_slope(h_idx, h_vals), _line_slope(l_idx, l_vals)
    if hs >= 0 or ls >= 0 or abs(ls) >= abs(hs):
        return None
    span_start = float(close.iloc[h_idx[0]] - close.iloc[l_idx[0]])
    span_end = float(close.iloc[h_idx[-1]] - close.iloc[l_idx[-1]])
    if span_end >= span_start * 0.85:
        return None
    offset = _window_offset(df, window)
    return PatternMatch(
        confidence=68.0,
        detail="falling converging highs/lows (bullish wedge)",
        end_idx=offset + max(h_idx[-1], l_idx[-1]),
        support=l_vals[-1],
        resistance=h_vals[-1],
    )


def detect_bull_flag(df: pd.DataFrame, pole_bars: int = 15, flag_bars: int = 12) -> Optional[PatternMatch]:
    close = df["Close"]
    if len(close) < pole_bars + flag_bars + 5:
        return None
    pole_start = float(close.iloc[-(pole_bars + flag_bars)])
    pole_end = float(close.iloc[-flag_bars])
    pole_ret = (pole_end - pole_start) / pole_start
    if pole_ret < 0.08:
        return None
    flag = close.iloc[-flag_bars:]
    flag_high, flag_low = float(flag.max()), float(flag.min())
    flag_range = (flag_high - flag_low) / pole_end
    if flag_range > 0.08 or float(flag.iloc[-1]) < float(flag.iloc[0]) * 0.97:
        return None
    return PatternMatch(
        confidence=62.0,
        detail=f"pole +{pole_ret * 100:.0f}% then tight flag ({flag_range * 100:.1f}% range)",
        end_idx=len(df) - 1,
        support=flag_low,
        resistance=flag_high,
    )


def detect_bear_flag(df: pd.DataFrame, pole_bars: int = 15, flag_bars: int = 12) -> Optional[PatternMatch]:
    close = df["Close"]
    if len(close) < pole_bars + flag_bars + 5:
        return None
    pole_start = float(close.iloc[-(pole_bars + flag_bars)])
    pole_end = float(close.iloc[-flag_bars])
    pole_ret = (pole_end - pole_start) / pole_start
    if pole_ret > -0.08:
        return None
    flag = close.iloc[-flag_bars:]
    flag_high, flag_low = float(flag.max()), float(flag.min())
    flag_range = (flag_high - flag_low) / abs(pole_end)
    if flag_range > 0.08 or float(flag.iloc[-1]) > float(flag.iloc[0]) * 1.03:
        return None
    return PatternMatch(
        confidence=62.0,
        detail=f"pole {pole_ret * 100:.0f}% then tight flag ({flag_range * 100:.1f}% range)",
        end_idx=len(df) - 1,
        support=flag_low,
        resistance=flag_high,
    )


def detect_pennant(df: pd.DataFrame, pole_bars: int = 15, pennant_bars: int = 12) -> Optional[PatternMatch]:
    close = df["Close"]
    if len(close) < pole_bars + pennant_bars + 5:
        return None
    pole_start = float(close.iloc[-(pole_bars + pennant_bars)])
    pole_end = float(close.iloc[-pennant_bars])
    pole_ret = abs((pole_end - pole_start) / pole_start)
    if pole_ret < 0.08:
        return None
    seg = close.iloc[-pennant_bars:]
    highs, lows = _swing_points(seg, order=3)
    if len(highs) < 2 or len(lows) < 2:
        return None
    h_slope = _line_slope(highs[-2:], [float(seg.iloc[i]) for i in highs[-2:]])
    l_slope = _line_slope(lows[-2:], [float(seg.iloc[i]) for i in lows[-2:]])
    if h_slope >= 0 or l_slope <= 0:
        return None
    pennant_high, pennant_low = float(seg.max()), float(seg.min())
    return PatternMatch(
        confidence=60.0,
        detail=f"sharp move then converging pennant after {pole_ret * 100:.0f}% pole",
        end_idx=len(df) - 1,
        support=pennant_low,
        resistance=pennant_high,
    )


def detect_rectangle(df: pd.DataFrame, order: int = 5, flat_tol: float = 0.03) -> Optional[PatternMatch]:
    window = _window(df, 100)
    close = window["Close"]
    highs, lows = _swing_points(close, order=order)
    if len(highs) < 2 or len(lows) < 2:
        return None
    h_vals = [float(close.iloc[i]) for i in highs[-3:]]
    l_vals = [float(close.iloc[i]) for i in lows[-3:]]
    flat_top = (max(h_vals) - min(h_vals)) / max(h_vals) <= flat_tol
    flat_bot = (max(l_vals) - min(l_vals)) / max(l_vals) <= flat_tol
    if not (flat_top and flat_bot):
        return None
    top, bottom = max(h_vals), min(l_vals)
    last = float(close.iloc[-1])
    if not (bottom * 1.01 < last < top * 0.99):
        return None
    offset = _window_offset(df, window)
    return PatternMatch(
        confidence=58.0,
        detail=f"range {bottom:.2f}-{top:.2f}, price mid-range {last:.2f}",
        end_idx=offset + max(highs[-1], lows[-1]),
        support=bottom,
        resistance=top,
    )


def _detect_ascending_triangle(df: pd.DataFrame, order: int = 5) -> Optional[PatternMatch]:
    close = df["Close"]
    if len(close) < 40:
        return None
    window = close.iloc[-90:]
    highs, lows = _swing_points(window, order=order)
    if len(highs) < 2 or len(lows) < 2:
        return None
    high_vals = [float(window.iloc[i]) for i in highs[-3:]]
    low_vals = [float(window.iloc[i]) for i in lows[-3:]]
    flat_tol = 0.025
    flat = (max(high_vals) - min(high_vals)) / max(high_vals) <= flat_tol
    rising = all(b > a for a, b in zip(low_vals, low_vals[1:]))
    if not (flat and rising):
        return None
    offset = len(df) - len(window)
    return PatternMatch(
        confidence=75.0,
        detail="flat resistance with higher lows",
        end_idx=offset + max(highs[-1], lows[-1]),
        support=min(low_vals),
        resistance=max(high_vals),
    )


def _detect_cup_and_handle(df: pd.DataFrame) -> Optional[PatternMatch]:
    close = df["Close"]
    if len(close) < 50:
        return None
    window = close.iloc[-130:] if len(close) >= 130 else close
    vals = window.values
    n = len(vals)
    trough_i = int(np.argmin(vals))
    if trough_i < n * 0.2 or trough_i > n * 0.8:
        return None
    left_rim = float(vals[:trough_i].max())
    trough = float(vals[trough_i])
    right_section = vals[trough_i:]
    right_rim = float(right_section.max())
    last = float(vals[-1])
    depth = (left_rim - trough) / left_rim if left_rim > 0 else 0.0
    recovered = right_rim >= left_rim * 0.95
    handle = (right_rim - last) / right_rim if right_rim > 0 else 0.0
    near_rim = last >= left_rim * 0.9
    if not (0.12 <= depth <= 0.5 and recovered and 0 < handle <= 0.15 and near_rim):
        return None
    conf = min(90.0, 55.0 + depth * 50.0)
    detail = f"cup depth {depth * 100:.0f}%, handle {handle * 100:.0f}%"
    return PatternMatch(
        confidence=conf,
        detail=detail,
        end_idx=len(df) - 1,
        support=trough,
        resistance=max(left_rim, right_rim),
    )


_DETECTORS = {
    "head_shoulders": detect_head_shoulders,
    "inverse_head_shoulders": detect_inverse_head_shoulders,
    "double_top": detect_double_top,
    "double_bottom": detect_double_bottom,
    "ascending_triangle": _detect_ascending_triangle,
    "descending_triangle": detect_descending_triangle,
    "rising_wedge": detect_rising_wedge,
    "falling_wedge": detect_falling_wedge,
    "cup_and_handle": _detect_cup_and_handle,
    "bull_flag": detect_bull_flag,
    "bear_flag": detect_bear_flag,
    "pennant": detect_pennant,
    "rectangle": detect_rectangle,
}


def _enabled_patterns(config: dict) -> Set[str]:
    raw = str(config.get("chart_pattern_enabled", ALL_PATTERN_IDS))
    if raw.strip().lower() == "all":
        return set(PATTERN_CATALOG)
    return {p.strip() for p in raw.split(",") if p.strip()}


def scan_chart_patterns(
    df: pd.DataFrame,
    config: Optional[dict] = None,
    symbol: str = "",
) -> List[ChartPatternSignal]:
    """Return all active chart patterns detected on one ticker."""
    config = config or {}
    min_bars = int(config.get("chart_pattern_min_bars", 60))
    swing_order = int(config.get("chart_pattern_swing_order", 5))
    min_confidence = float(config.get("chart_pattern_min_confidence", 55))
    enabled = _enabled_patterns(config)
    pattern_filter = config.get("chart_pattern_patterns")
    if pattern_filter:
        allowed = {p.strip() for p in str(pattern_filter).split(",") if p.strip()}
        enabled &= allowed

    empty: List[ChartPatternSignal] = []
    if df is None or len(df) < min_bars:
        return empty
    if not {"Open", "High", "Low", "Close"}.issubset(df.columns):
        return empty

    exclude_today = bool(config.get("chart_pattern_exclude_today", True))
    work = _completed_df(df, exclude_today)
    if len(work) < min_bars:
        return empty

    close = float(work["Close"].iloc[-1])
    hits: List[ChartPatternSignal] = []
    for pattern_id, detector in _DETECTORS.items():
        if pattern_id not in enabled:
            continue
        try:
            if pattern_id in _SWING_ORDER_PATTERNS:
                result = detector(work, order=swing_order)
            else:
                result = detector(work)
        except Exception:  # noqa: BLE001
            continue
        if result is None:
            continue
        if result.confidence < min_confidence:
            continue
        hit = _hit(pattern_id, symbol, close, result, work, config)
        if hit is not None:
            hits.append(hit)

    hits.sort(key=lambda h: (-h.actionability_score, h.distance_to_trigger_pct, h.pattern_age))
    return hits


def explain_chart_patterns(ticker: str, config: dict) -> List[ChartPatternSignal]:
    from tradingagents.screening.prices import download_history

    symbol = ticker.upper()
    if not symbol.endswith((".NS", ".BO")):
        symbol = f"{symbol}.NS"
    period = config.get("chart_pattern_history_period", "2y")
    data = download_history([symbol], period=period)
    df = data.get(symbol)
    if df is None or df.empty:
        return [
            ChartPatternSignal(
                symbol=symbol,
                pattern_id="none",
                pattern_name="—",
                bias="—",
                reliability=0,
                ease=0,
                rejected=True,
                reject_reason="No price history from Yahoo",
                remark="REJECT - no price history from Yahoo",
            )
        ]
    return scan_chart_patterns(df, config, symbol=symbol)


__all__ = [
    "ALL_PATTERN_IDS",
    "ChartPatternSignal",
    "PATTERN_CATALOG",
    "PatternMatch",
    "STRATEGY_ID",
    "STRATEGY_NAME",
    "STRATEGY_VERSION",
    "detect_bear_flag",
    "detect_bull_flag",
    "detect_descending_triangle",
    "detect_double_bottom",
    "detect_double_top",
    "detect_falling_wedge",
    "detect_head_shoulders",
    "detect_inverse_head_shoulders",
    "detect_pennant",
    "detect_rectangle",
    "detect_rising_wedge",
    "explain_chart_patterns",
    "scan_chart_patterns",
]
