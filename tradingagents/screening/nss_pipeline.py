"""NANDA Swing Scanner (NSS) — modular structure-first pipeline stages."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from tradingagents.screening.momentum_indicators import supertrend_buy_age
from tradingagents.screening.patterns import rsi
from tradingagents.screening.swing_indicators import (
    adx,
    average_true_range_series,
    compute_trade_levels,
    ema,
    is_at_new_52_week_low,
    relative_volume,
    supertrend,
    supertrend_flip_to_buy_within,
)


@dataclass
class StageResult:
    name: str
    passed: bool
    score: float
    detail: str


@dataclass
class NSSSnapshot:
    stages: Dict[str, StageResult]
    composite_score: float
    primary_reason: str
    confidence: str
    entry: float
    stop_loss: float
    target_1: float
    target_2: float
    stop_loss_pct: float
    target_1_pct: float
    target_2_pct: float
    risk_reward_ratio: float
    risk_reward_ratio_2: float
    risk_pct: float
    rsi: float
    adx: float
    relative_volume: float
    range_pct: float
    atr_ratio: float
    avg_traded_value_inr: float
    breakout_ok: bool = False
    volume_ok: bool = False
    extra: Dict[str, float] = field(default_factory=dict)


def _ema_slope(series: pd.Series, lookback: int = 20) -> float:
    if len(series) < lookback + 1:
        return 0.0
    recent = series.iloc[-lookback:]
    x = np.arange(len(recent), dtype=float)
    coeffs = np.polyfit(x, recent.values.astype(float), 1)
    return float(coeffs[0])


def _higher_lows_score(lows: pd.Series, sessions: int = 10) -> float:
    if len(lows) < sessions:
        return 0.0
    window = lows.iloc[-sessions:]
    pivots = []
    for i in range(1, len(window) - 1):
        if window.iloc[i] <= window.iloc[i - 1] and window.iloc[i] <= window.iloc[i + 1]:
            pivots.append(float(window.iloc[i]))
    if len(pivots) < 2:
        return 40.0
    rising = sum(1 for i in range(1, len(pivots)) if pivots[i] > pivots[i - 1])
    return min(100.0, 40.0 + 30.0 * rising)


def evaluate_nss(df: pd.DataFrame, config: dict) -> Optional[NSSSnapshot]:
    """Run all NSS stages; return snapshot when composite >= min_score."""
    min_bars = max(
        252,
        int(config.get("nss_ema_slow", 200)),
        int(config.get("nss_consolidation_lookback", 15)),
        int(config.get("nss_breakout_lookback", 20)),
    ) + 10
    if len(df) < min_bars:
        return None

    weights = {
        "trend": float(config.get("nss_weight_trend", 15)),
        "consolidation": float(config.get("nss_weight_consolidation", 30)),
        "breakout": float(config.get("nss_weight_breakout", 25)),
        "volume": float(config.get("nss_weight_volume", 15)),
        "momentum": float(config.get("nss_weight_momentum", 10)),
        "risk": float(config.get("nss_weight_risk", 5)),
    }

    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]
    latest = float(close.iloc[-1])

    ema50 = ema(close, int(config.get("nss_ema_fast", 50)))
    ema200 = ema(close, int(config.get("nss_ema_slow", 200)))
    st_line, st_trend = supertrend(
        df,
        period=int(config.get("nss_supertrend_period", 10)),
        multiplier=float(config.get("nss_supertrend_multiplier", 3.0)),
    )

    stages: Dict[str, StageResult] = {}

    # --- Trend (hard) ---
    slope200 = _ema_slope(ema200, int(config.get("nss_trend_slope_lookback", 20)))
    trend_ok = (
        latest > float(ema50.iloc[-1]) > float(ema200.iloc[-1])
        and slope200 > 0
    )
    trend_score = 100.0 if trend_ok else 0.0
    if not trend_ok:
        trend_score = 0.0
    else:
        spread = 100.0 * (float(ema50.iloc[-1]) - float(ema200.iloc[-1])) / latest
        trend_score = min(100.0, 60.0 + spread * 5)
    stages["trend"] = StageResult(
        "trend",
        trend_ok,
        trend_score,
        f"EMA50>EMA200, slope200={'+' if slope200 > 0 else '-'}",
    )
    if not trend_ok:
        return None

    # --- Anti-overlap ---
    if config.get("nss_exclude_swing_overlap", True):
        if supertrend_flip_to_buy_within(
            st_trend, sessions=int(config.get("swing_flip_lookback_sessions", 3))
        ):
            return None
    if config.get("nss_exclude_momentum_overlap", True):
        min_buy = int(config.get("momentum_st_min_buy_sessions", 4))
        if supertrend_buy_age(st_trend) >= min_buy:
            ext = 100.0 * (latest - float(ema50.iloc[-1])) / float(ema50.iloc[-1])
            if ext > float(config.get("nss_momentum_overlap_ext_pct", 8.0)):
                return None

    # --- Consolidation ---
    c_look = int(config.get("nss_consolidation_lookback", 15))
    c_max_range = float(config.get("nss_consolidation_max_range_pct", 8.0))
    window_h = float(high.iloc[-c_look:].max())
    window_l = float(low.iloc[-c_look:].min())
    range_pct = 100.0 * (window_h - window_l) / latest if latest > 0 else 99.0

    atr5 = float(average_true_range_series(df, 14).iloc[-5:].mean())
    atr20 = float(average_true_range_series(df, 14).iloc[-20:].mean())
    atr_ratio = atr5 / atr20 if atr20 > 0 else 1.0

    held_support = float(low.iloc[-c_look:].min()) >= float(ema50.iloc[-c_look:].min()) * 0.98
    hl_score = _higher_lows_score(low, c_look)

    tight = range_pct <= c_max_range
    contracting = atr_ratio <= float(config.get("nss_atr_contraction_max", 0.95))
    cons_pass = tight and contracting and held_support
    cons_score = 0.0
    if tight:
        cons_score += 40.0 * max(0.0, 1.0 - range_pct / c_max_range)
    if contracting:
        cons_score += 30.0 * max(0.0, 1.0 - atr_ratio)
    if held_support:
        cons_score += 15.0
    cons_score += 0.15 * hl_score
    cons_score = min(100.0, cons_score)

    stages["consolidation"] = StageResult(
        "consolidation",
        cons_pass,
        cons_score,
        f"range={range_pct:.1f}%, ATR5/20={atr_ratio:.2f}, support={'Y' if held_support else 'N'}",
    )
    if not cons_pass:
        return None

    # --- Breakout (scored only; no hard gate on close above prior range high) ---
    b_look = int(config.get("nss_breakout_lookback", 20))
    fresh = int(config.get("nss_breakout_fresh_sessions", 3))
    prior_high = float(high.iloc[-(b_look + 1) : -1].max())
    broke = latest > prior_high
    recent_break = False
    for i in range(1, fresh + 1):
        if float(close.iloc[-i]) > float(high.iloc[-(b_look + i) : -i].max()):
            recent_break = True
            break
    br_pass = True
    extension = 100.0 * (latest - prior_high) / prior_high if prior_high > 0 else 0.0
    br_score = 0.0
    if broke:
        br_score = min(100.0, 70.0 + extension * 5)
    elif prior_high > 0:
        # Proximity score when still inside the range (pre-breakout consolidation)
        gap_pct = 100.0 * (prior_high - latest) / prior_high
        br_score = max(0.0, min(60.0, 60.0 - gap_pct * 3.0))
    if recent_break:
        br_score = min(100.0, br_score + 15.0)
    stages["breakout"] = StageResult(
        "breakout",
        br_pass,
        br_score,
        f"close {latest:.2f} vs prior high {prior_high:.2f}, fresh={'Y' if recent_break else 'N'}",
    )

    # --- Volume (scored + displayed; not a hard gate) ---
    vol_mult = float(config.get("nss_volume_mult", 1.2))
    rel_vol = relative_volume(volume, int(config.get("nss_volume_lookback", 20)))
    vol_meets_ref = rel_vol is not None and rel_vol >= vol_mult
    vol_score = min(100.0, (rel_vol or 0) / vol_mult * 80.0) if rel_vol else 0.0
    vol_detail = (
        f"rel_vol={rel_vol:.2f}x (ref>={vol_mult:.2f}x, "
        f"{'met' if vol_meets_ref else 'below ref'})"
        if rel_vol is not None
        else "n/a"
    )
    stages["volume"] = StageResult(
        "volume",
        True,
        vol_score,
        vol_detail,
    )

    # --- Momentum (confirm) ---
    rsi_val = float(rsi(close, int(config.get("nss_rsi_period", 14))).iloc[-1])
    adx_series = adx(df, int(config.get("nss_adx_period", 14)))
    adx_val = float(adx_series.iloc[-1])
    rsi_min = float(config.get("nss_rsi_min", 45.0))
    rsi_max = float(config.get("nss_rsi_max", 65.0))
    adx_min = float(config.get("nss_adx_min", 15.0))
    mom_pass = rsi_min <= rsi_val <= rsi_max and np.isfinite(adx_val) and adx_val >= adx_min
    mom_score = 0.0
    if rsi_min <= rsi_val <= rsi_max:
        mom_score += 50.0
    if adx_val >= adx_min:
        mom_score += min(50.0, adx_val)
    stages["momentum"] = StageResult(
        "momentum",
        mom_pass,
        min(100.0, mom_score),
        f"RSI={rsi_val:.1f}, ADX={adx_val:.1f}",
    )
    if not mom_pass:
        return None

    # --- Risk ---
    max_risk = float(config.get("nss_max_risk_pct", 8.0))
    cons_low = float(low.iloc[-c_look:].min())
    st_stop = float(st_line.iloc[-1]) if np.isfinite(st_line.iloc[-1]) else cons_low
    stop = max(cons_low, st_stop)
    if stop >= latest:
        stop = st_stop if st_stop < latest else cons_low
    if stop <= 0 or stop >= latest:
        return None

    levels = compute_trade_levels(
        entry=latest,
        stop_loss=stop,
        target_1_rr=float(config.get("nss_target_1_rr", 1.5)),
        target_2_rr=float(config.get("nss_target_2_rr", 2.5)),
    )
    if levels is None:
        return None

    risk_pct = 100.0 * (latest - stop) / latest
    risk_pass = risk_pct <= max_risk
    risk_score = max(0.0, 100.0 - risk_pct * 10.0) if risk_pass else 0.0
    stages["risk"] = StageResult(
        "risk",
        risk_pass,
        risk_score,
        f"risk={risk_pct:.1f}%, stop={stop:.2f}",
    )
    if not risk_pass:
        return None

    if is_at_new_52_week_low(close):
        return None

    total_w = sum(weights.values()) or 1.0
    composite = sum(stages[k].score * weights[k] for k in weights if k in stages) / total_w
    min_score = float(config.get("nss_min_score", 50.0))
    if composite < min_score:
        return None

    passed = [k for k, s in stages.items() if s.passed]
    primary = max(
        (k for k in ("consolidation", "breakout", "volume") if k in passed),
        key=lambda k: stages[k].score,
        default="breakout",
    )
    confidence = "high" if composite >= 75 else "medium" if composite >= 60 else "low"

    traded = float((close.iloc[-20:] * volume.iloc[-20:]).mean())

    return NSSSnapshot(
        stages=stages,
        composite_score=round(composite, 2),
        primary_reason=primary,
        confidence=confidence,
        avg_traded_value_inr=traded,
        rsi=round(rsi_val, 2),
        adx=round(adx_val, 2),
        relative_volume=round(rel_vol or 0, 4),
        range_pct=round(range_pct, 2),
        atr_ratio=round(atr_ratio, 3),
        risk_pct=round(risk_pct, 2),
        breakout_ok=bool(broke or recent_break),
        volume_ok=bool(vol_meets_ref),
        **levels,
        extra={"extension_break_pct": round(extension, 2)},
    )


def explain_nss_failure(df: pd.DataFrame, config: dict) -> List[StageResult]:
    """Best-effort stage report even when stock fails (for --explain)."""
    from tradingagents.screening.nss_diagnostics import diagnose_nss

    diag = diagnose_nss(df, config)
    return list(diag.stages.values())
