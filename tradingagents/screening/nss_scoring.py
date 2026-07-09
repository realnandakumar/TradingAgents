"""NSS v1.1 scoring, confidence, and threshold architecture.

Screening gates in ``evaluate_nss`` remain binary/fixed. This module provides
graduated scores, consolidation sub-checks, and explainability helpers used by
the diagnostics layer only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from tradingagents.screening.swing_indicators import average_true_range_series, ema


class ThresholdMode(str, Enum):
    """Adaptive threshold modes (v1.1 architecture only — all run as FIXED today)."""

    FIXED = "fixed"
    PERCENTILE = "percentile"
    ATR_BASED = "atr_based"
    MARKET_REGIME = "market_regime"


@dataclass
class ModuleDetail:
    """Score + confidence + explanation for one diagnostic module."""

    name: str
    passed: bool
    score: float
    confidence: str
    explanation: str
    submodules: Dict[str, "ModuleDetail"] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "passed": self.passed,
            "score": round(self.score, 2),
            "confidence": self.confidence,
            "explanation": self.explanation,
            "submodules": {k: v.to_dict() for k, v in self.submodules.items()},
        }


def get_threshold_mode(config: dict) -> ThresholdMode:
    raw = str(config.get("nss_threshold_mode", ThresholdMode.FIXED.value)).lower()
    try:
        return ThresholdMode(raw)
    except ValueError:
        return ThresholdMode.FIXED


def resolve_threshold(config: dict, key: str, default: float) -> float:
    """Return threshold value. Only FIXED is active in v1.1."""
    mode = get_threshold_mode(config)
    if mode != ThresholdMode.FIXED:
        # Architecture hook — future modes read nss_threshold_overrides / regime data
        pass
    overrides = config.get("nss_threshold_overrides") or {}
    if key in overrides:
        return float(overrides[key])
    return float(config.get(key, default))


def confidence_from_score(score: float, *, high: float = 75.0, medium: float = 50.0) -> str:
    if score >= high:
        return "high"
    if score >= medium:
        return "medium"
    return "low"


def overall_rating(score: float, confidence: str) -> str:
    if score >= 75 and confidence == "high":
        return "Strong"
    if score >= 60 and confidence in ("high", "medium"):
        return "Moderate"
    if score >= 45:
        return "Watch"
    return "Weak"


def _volume_score_tiers(config: dict) -> List[Tuple[float, float]]:
    default = [
        (2.00, 10.0),
        (1.75, 9.0),
        (1.50, 8.0),
        (1.30, 6.0),
        (1.15, 4.0),
        (0.0, 0.0),
    ]
    tiers = config.get("nss_volume_score_tiers")
    if not tiers:
        return default
    return [(float(t[0]), float(t[1])) for t in tiers]


def graduated_volume_score(rel_vol: Optional[float], config: dict) -> Tuple[float, str]:
    """Graduated volume score on 0–10 scale (v1.1 diagnostics)."""
    if rel_vol is None or rel_vol <= 0:
        return 0.0, "relative volume unavailable"
    for floor, pts in _volume_score_tiers(config):
        if rel_vol >= floor:
            return pts, f"rel_vol={rel_vol:.2f}x -> score {pts:.0f}/10"
    return 0.0, f"rel_vol={rel_vol:.2f}x below minimum tier"


def volume_hard_gate_pass(rel_vol: Optional[float], config: dict) -> bool:
    """Unchanged screening gate — binary >= nss_volume_mult."""
    mult = resolve_threshold(config, "nss_volume_mult", 1.2)
    return rel_vol is not None and rel_vol >= mult


def _freshness_score_table(config: dict) -> List[Tuple[int, float]]:
    default = [
        (0, 25.0),
        (1, 22.0),
        (2, 20.0),
        (3, 17.0),
        (4, 12.0),
        (5, 8.0),
    ]
    table = config.get("nss_breakout_freshness_scores")
    if not table:
        return default
    return [(int(t[0]), float(t[1])) for t in table]


def breakout_age_sessions(
    close: pd.Series,
    high: pd.Series,
    breakout_lookback: int,
    max_scan: int = 10,
) -> Optional[int]:
    """Sessions since price first closed above the prior-range high (-1 = never broke)."""
    if len(close) < breakout_lookback + 2:
        return None
    latest = float(close.iloc[-1])
    prior_high = float(high.iloc[-(breakout_lookback + 1) : -1].max())
    if latest <= prior_high:
        return None
    for age in range(0, min(max_scan, len(close) - breakout_lookback)):
        i = age + 1
        ref_high = float(high.iloc[-(breakout_lookback + i) : -i].max())
        if float(close.iloc[-i]) > ref_high:
            return age
    return max_scan


def freshness_score(age_sessions: Optional[int], config: dict) -> Tuple[float, str]:
    """Freshness score 0–25 based on breakout age."""
    if age_sessions is None:
        return 0.0, "no breakout detected"
    table = _freshness_score_table(config)
    for max_age, pts in table:
        if age_sessions == max_age:
            label = "today" if max_age == 0 else f"{max_age} session(s) ago"
            return pts, f"breakout {label} -> freshness {pts:.0f}/25"
    return 0.0, f"breakout {age_sessions}+ sessions ago -> freshness 0/25"


def breakout_hard_gate_pass(age_sessions: Optional[int], config: dict) -> bool:
    """Unchanged screening gate — breakout within fresh_sessions."""
    if age_sessions is None:
        return False
    fresh = int(resolve_threshold(config, "nss_breakout_fresh_sessions", 3))
    return age_sessions <= fresh


def _consolidation_weights(config: dict) -> Dict[str, float]:
    return {
        "trading_range": float(config.get("nss_consol_weight_range", 25)),
        "atr_contraction": float(config.get("nss_consol_weight_atr", 20)),
        "volume_dryup": float(config.get("nss_consol_weight_vol_dryup", 15)),
        "ema_support": float(config.get("nss_consol_weight_ema", 20)),
        "higher_lows": float(config.get("nss_consol_weight_hl", 10)),
        "price_compression": float(config.get("nss_consol_weight_compression", 10)),
    }


def evaluate_consolidation_subchecks(
    df: pd.DataFrame,
    config: dict,
    *,
    ema50: pd.Series,
    higher_lows_fn,
) -> Tuple[ModuleDetail, bool]:
    """Split consolidation into independent diagnostic checks."""
    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]
    latest = float(close.iloc[-1])

    c_look = int(config.get("nss_consolidation_lookback", 15))
    c_max_range = resolve_threshold(config, "nss_consolidation_max_range_pct", 8.0)
    atr_max = resolve_threshold(config, "nss_atr_contraction_max", 0.95)
    dryup_ratio = float(config.get("nss_volume_dryup_ratio", 0.85))

    window_h = float(high.iloc[-c_look:].max())
    window_l = float(low.iloc[-c_look:].min())
    range_pct = 100.0 * (window_h - window_l) / latest if latest > 0 else 99.0

    atr5 = float(average_true_range_series(df, 14).iloc[-5:].mean())
    atr20 = float(average_true_range_series(df, 14).iloc[-20:].mean())
    atr_ratio = atr5 / atr20 if atr20 > 0 else 1.0

    held_support = float(low.iloc[-c_look:].min()) >= float(ema50.iloc[-c_look:].min()) * 0.98
    hl_score = higher_lows_fn(low, c_look)

    vol_consol = float(volume.iloc[-c_look:].mean())
    vol_base = float(volume.iloc[-(c_look + 20) : -c_look].mean()) if len(volume) > c_look + 20 else vol_consol
    vol_dry = vol_consol < vol_base * dryup_ratio if vol_base > 0 else False

    half = max(3, c_look // 2)
    range_recent = 100.0 * (float(high.iloc[-half:].max()) - float(low.iloc[-half:].min())) / latest
    range_prior = 100.0 * (float(high.iloc[-c_look:-half].max()) - float(low.iloc[-c_look:-half].min())) / latest
    compressing = range_recent < range_prior if range_prior > 0 else False

    tight = range_pct <= c_max_range
    contracting = atr_ratio <= atr_max

    subs: Dict[str, ModuleDetail] = {}

    range_pts = min(100.0, 100.0 * max(0.0, 1.0 - range_pct / c_max_range)) if c_max_range else 0.0
    subs["trading_range"] = ModuleDetail(
        "trading_range",
        tight,
        range_pts,
        confidence_from_score(range_pts),
        f"range={range_pct:.1f}% vs max {c_max_range:.1f}%",
    )

    atr_pts = min(100.0, 100.0 * max(0.0, 1.0 - atr_ratio / atr_max)) if atr_max else 0.0
    subs["atr_contraction"] = ModuleDetail(
        "atr_contraction",
        contracting,
        atr_pts,
        confidence_from_score(atr_pts),
        f"ATR5/20={atr_ratio:.2f} vs max {atr_max:.2f}",
    )

    dry_pts = 80.0 if vol_dry else 20.0
    subs["volume_dryup"] = ModuleDetail(
        "volume_dryup",
        vol_dry,
        dry_pts,
        confidence_from_score(dry_pts),
        f"consol_vol={vol_consol:.0f} vs base={vol_base:.0f} (need <{dryup_ratio:.0%} of base)",
    )

    ema_pts = 100.0 if held_support else 0.0
    subs["ema_support"] = ModuleDetail(
        "ema_support",
        held_support,
        ema_pts,
        confidence_from_score(ema_pts),
        f"low held above EMA50 support ({'Y' if held_support else 'N'})",
    )

    subs["higher_lows"] = ModuleDetail(
        "higher_lows",
        hl_score >= 50.0,
        hl_score,
        confidence_from_score(hl_score),
        f"higher-lows pattern score {hl_score:.0f}/100",
    )

    comp_pts = 80.0 if compressing else 30.0
    subs["price_compression"] = ModuleDetail(
        "price_compression",
        compressing,
        comp_pts,
        confidence_from_score(comp_pts),
        f"recent range {range_recent:.1f}% vs prior {range_prior:.1f}%",
    )

    weights = _consolidation_weights(config)
    total_w = sum(weights.values()) or 1.0
    composite = sum(subs[k].score * weights[k] for k in weights if k in subs) / total_w

    # Screening gate unchanged: range + ATR + EMA support (same as evaluate_nss)
    gate_pass = tight and contracting and held_support

    parent = ModuleDetail(
        "consolidation",
        gate_pass,
        min(100.0, composite),
        confidence_from_score(composite),
        f"gate={'PASS' if gate_pass else 'FAIL'} (range+ATR+EMA); composite={composite:.1f}",
        submodules=subs,
    )
    return parent, gate_pass


def evaluate_breakout_module(
    close: pd.Series,
    high: pd.Series,
    latest: float,
    config: dict,
) -> Tuple[ModuleDetail, bool, float]:
    """Breakout with price break + freshness sub-scores (diagnostics)."""
    b_look = int(config.get("nss_breakout_lookback", 20))
    prior_high = float(high.iloc[-(b_look + 1) : -1].max())
    broke = latest > prior_high
    age = breakout_age_sessions(close, high, b_look)
    fresh_pts, fresh_expl = freshness_score(age, config)
    fresh_gate = breakout_hard_gate_pass(age, config)

    extension = 100.0 * (latest - prior_high) / prior_high if prior_high > 0 else 0.0
    price_pts = min(100.0, 70.0 + extension * 5) if broke else 0.0

    subs = {
        "breakout_price": ModuleDetail(
            "breakout_price",
            True,
            price_pts,
            confidence_from_score(price_pts),
            f"close {latest:.2f} vs prior high {prior_high:.2f} (not a hard gate)",
        ),
        "breakout_freshness": ModuleDetail(
            "breakout_freshness",
            fresh_gate,
            fresh_pts * 4.0,  # scale 0-25 to 0-100 for display
            confidence_from_score(fresh_pts * 4.0),
            fresh_expl,
        ),
    }

    # Combined breakout score: 60% price + 40% freshness (configurable)
    w_price = float(config.get("nss_breakout_weight_price", 0.6))
    w_fresh = float(config.get("nss_breakout_weight_freshness", 0.4))
    combined = w_price * price_pts + w_fresh * (fresh_pts * 4.0)
    gate_pass = True

    parent = ModuleDetail(
        "breakout",
        gate_pass,
        combined,
        confidence_from_score(combined),
        f"gate={'PASS' if gate_pass else 'FAIL'}; combined={combined:.1f}",
        submodules=subs,
    )
    return parent, gate_pass, extension


def evaluate_volume_module(
    rel_vol: Optional[float],
    config: dict,
) -> Tuple[ModuleDetail, bool]:
    """Graduated volume scoring; reference threshold shown, not a hard gate."""
    grad_pts, expl = graduated_volume_score(rel_vol, config)
    display_score = grad_pts * 10.0  # 0-10 -> 0-100
    mult = resolve_threshold(config, "nss_volume_mult", 1.2)
    meets_ref = volume_hard_gate_pass(rel_vol, config)

    return ModuleDetail(
        "volume_expansion",
        True,
        display_score,
        confidence_from_score(display_score),
        f"{expl}; ref >={mult:.2f}x ({'met' if meets_ref else 'below ref'}, not gated)",
    ), True


def build_near_miss_action(
    failure_stage: Optional[str],
    *,
    required: Any = None,
    actual: Any = None,
    score_gap: float = 0.0,
) -> str:
    if failure_stage == "volume_expansion" or failure_stage == "volume":
        return "Watch next session for volume confirmation."
    if failure_stage in ("breakout", "breakout_freshness"):
        return "Watch for fresh breakout within freshness window."
    if failure_stage == "consolidation" or failure_stage in (
        "trading_range", "atr_contraction", "ema_support",
    ):
        return "Watch for tighter range and ATR contraction."
    if failure_stage == "composite":
        return f"Needs {score_gap:.1f} more composite points to qualify."
    if failure_stage == "trend":
        return "Wait for EMA50>EMA200 uptrend structure."
    return "Monitor — setup not yet complete."
