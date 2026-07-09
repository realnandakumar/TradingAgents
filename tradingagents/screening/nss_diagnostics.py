"""NSS scanner diagnostics and explainability (v1.1).

Parallel evaluation path mirroring ``evaluate_nss`` hard gates without changing
screening behaviour. Adds graduated scoring, consolidation sub-checks, expanded
waterfall, confidence/ratings, and near-miss threshold distances.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import numpy as np
import pandas as pd

from tradingagents.screening.momentum_indicators import supertrend_buy_age
from tradingagents.screening.nss_health import compute_health_from_diagnostics, persist_health
from tradingagents.screening.nss_pipeline import StageResult, evaluate_nss, _ema_slope, _higher_lows_score
from tradingagents.screening.nss_scoring import (
    ModuleDetail,
    build_near_miss_action,
    confidence_from_score,
    evaluate_breakout_module,
    evaluate_consolidation_subchecks,
    evaluate_volume_module,
    overall_rating,
    resolve_threshold,
)
from tradingagents.screening.patterns import rsi
from tradingagents.screening.prices import download_history
from tradingagents.screening.swing_indicators import (
    adx,
    compute_trade_levels,
    ema,
    is_at_new_52_week_low,
    relative_volume,
    supertrend,
    supertrend_flip_to_buy_within,
)
from tradingagents.screening.swing_screener import _CRORE, _fetch_market_caps
from tradingagents.screening.universe import load_universe, load_universe_metadata

SCORE_STAGE_NAMES = ("trend", "consolidation", "breakout", "volume", "momentum", "risk")

EXPANDED_WATERFALL_ORDER = [
    "has_data",
    "history",
    "liquidity",
    "trend",
    "overlap",
    "trading_range",
    "atr_contraction",
    "ema_support",
    "volume_dryup",
    "higher_lows",
    "price_compression",
    "consolidation",
    "breakout_price",
    "breakout_freshness",
    "volume_expansion",
    "momentum",
    "risk",
    "composite",
    "market_cap",
    "picked",
]


def _nss_weights(config: dict) -> Dict[str, float]:
    return {
        "trend": float(config.get("nss_weight_trend", 15)),
        "consolidation": float(config.get("nss_weight_consolidation", 30)),
        "breakout": float(config.get("nss_weight_breakout", 25)),
        "volume": float(config.get("nss_weight_volume", 15)),
        "momentum": float(config.get("nss_weight_momentum", 10)),
        "risk": float(config.get("nss_weight_risk", 5)),
    }


def _module_as_stage(m: ModuleDetail) -> StageResult:
    return StageResult(m.name, m.passed, m.score, m.explanation)


def _weighted_composite(modules: Dict[str, ModuleDetail], weights: Dict[str, float]) -> float:
    total_w = sum(weights.values()) or 1.0
    key_map = {
        "trend": "trend",
        "consolidation": "consolidation",
        "breakout": "breakout",
        "volume": "volume_expansion",
        "momentum": "momentum",
        "risk": "risk",
    }
    total = 0.0
    for wkey, mkey in key_map.items():
        mod = modules.get(mkey)
        if mod:
            total += mod.score * weights[wkey]
    return total / total_w


def _score_components(modules: Dict[str, ModuleDetail], weights: Dict[str, float]) -> Dict[str, float]:
    total_w = sum(weights.values()) or 1.0
    key_map = {
        "trend": "trend",
        "consolidation": "consolidation",
        "breakout": "breakout",
        "volume": "volume_expansion",
        "momentum": "momentum",
        "risk": "risk",
    }
    out = {
        wkey: round(modules[mkey].score * weights[wkey] / total_w, 2)
        for wkey, mkey in key_map.items()
        if mkey in modules
    }
    out["composite"] = round(_weighted_composite(modules, weights), 2)
    return out


@dataclass
class TickerDiagnostic:
    symbol: str
    stock_name: str = ""
    sector: str = ""
    status: str = "rejected"
    failure_stage: Optional[str] = None
    granular_failure_stage: Optional[str] = None
    failure_reason: str = ""
    stages: Dict[str, StageResult] = field(default_factory=dict)
    modules: Dict[str, ModuleDetail] = field(default_factory=dict)
    granular_passed: Dict[str, bool] = field(default_factory=dict)
    score_components: Dict[str, float] = field(default_factory=dict)
    partial_score: float = 0.0
    composite_score: Optional[float] = None
    overall_confidence: str = "low"
    overall_rating: str = "Weak"
    selection_reason: str = ""
    market_cap_cr: Optional[float] = None
    avg_traded_value_cr: Optional[float] = None
    would_pass_pipeline: bool = False

    def stage_rows(self) -> List[dict]:
        return [
            {"name": s.name, "passed": s.passed, "score": round(s.score, 1), "detail": s.detail}
            for s in self.stages.values()
        ]

    def module_rows(self) -> List[dict]:
        return [m.to_dict() for m in self.modules.values()]

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "stock_name": self.stock_name,
            "sector": self.sector,
            "status": self.status,
            "failure_stage": self.failure_stage,
            "granular_failure_stage": self.granular_failure_stage,
            "failure_reason": self.failure_reason,
            "stages": self.stage_rows(),
            "modules": self.module_rows(),
            "granular_passed": self.granular_passed,
            "score_components": self.score_components,
            "partial_score": self.partial_score,
            "composite_score": self.composite_score,
            "overall_confidence": self.overall_confidence,
            "overall_rating": self.overall_rating,
            "selection_reason": self.selection_reason,
            "market_cap_cr": self.market_cap_cr,
            "avg_traded_value_cr": self.avg_traded_value_cr,
            "would_pass_pipeline": self.would_pass_pipeline,
        }


@dataclass
class WaterfallStep:
    stage: str
    label: str
    input_count: int
    output_count: int
    rejection_count: int
    rejection_pct: float
    remaining: int = 0
    dropped: int = 0

    def __post_init__(self):
        self.remaining = self.output_count
        self.dropped = self.rejection_count

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class NearMissEntry:
    rank: int
    symbol: str
    stock_name: str
    failure_stage: str
    failure_reason: str
    failed_condition: str
    partial_score: float
    score_gap: float
    threshold_required: Optional[str]
    threshold_actual: Optional[str]
    threshold_distance: Optional[str]
    watch_action: str
    score_components: Dict[str, float]
    overall_confidence: str
    stages_passed: int
    stages_total: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ScanDiagnosticReport:
    scanned_at: str
    universe_size: int
    waterfall: List[WaterfallStep]
    picks: List[str]
    rejected_count: int
    rejection_by_stage: Dict[str, int]
    near_misses: List[NearMissEntry]
    diagnostics: List[TickerDiagnostic] = field(repr=False)
    market_health: dict = field(default_factory=dict)

    def to_dict(self, *, include_rejections: bool = False) -> dict:
        out = {
            "version": "1.1",
            "scanned_at": self.scanned_at,
            "universe_size": self.universe_size,
            "waterfall": [w.to_dict() for w in self.waterfall],
            "picks": self.picks,
            "rejected_count": self.rejected_count,
            "rejection_by_stage": self.rejection_by_stage,
            "near_misses": [n.to_dict() for n in self.near_misses],
            "market_health": self.market_health,
        }
        if include_rejections:
            out["rejected"] = [d.to_dict() for d in self.diagnostics if d.status != "picked"]
            out["selected"] = [d.to_dict() for d in self.diagnostics if d.status == "picked"]
        return out


def _sync_stages(diag: TickerDiagnostic) -> None:
    diag.stages = {k: _module_as_stage(v) for k, v in diag.modules.items()}


def _finalize_scores(diag: TickerDiagnostic, weights: Dict[str, float], config: dict) -> None:
    diag.score_components = _score_components(diag.modules, weights)
    diag.partial_score = diag.score_components.get("composite", 0.0)
    diag.overall_confidence = confidence_from_score(diag.partial_score)
    diag.overall_rating = overall_rating(diag.partial_score, diag.overall_confidence)
    min_score = resolve_threshold(config, "nss_min_score", 50.0)
    if diag.partial_score >= min_score:
        diag.composite_score = diag.partial_score


def _mark_failure(
    diag: TickerDiagnostic,
    stage: str,
    reason: str,
    weights: Dict[str, float],
    config: dict,
    *,
    granular: Optional[str] = None,
) -> TickerDiagnostic:
    if diag.failure_stage is None:
        diag.failure_stage = stage
        diag.failure_reason = reason
    if diag.granular_failure_stage is None and granular:
        diag.granular_failure_stage = granular
    _sync_stages(diag)
    _finalize_scores(diag, weights, config)
    return diag


def _first_consolidation_fail(cons_mod: ModuleDetail) -> str:
    order = ("trading_range", "atr_contraction", "ema_support")
    for key in order:
        sub = cons_mod.submodules.get(key)
        if sub and not sub.passed:
            return key
    return "consolidation"


def _early_liquidity(df: pd.DataFrame, config: dict) -> tuple[bool, float]:
    traded = float((df["Close"].iloc[-20:] * df["Volume"].iloc[-20:]).mean())
    min_inr = float(config.get("nss_min_avg_traded_value_cr", 10.0)) * _CRORE
    return traded >= min_inr, traded


def diagnose_nss(
    df: pd.DataFrame,
    config: dict,
    *,
    symbol: str = "",
    stock_name: str = "",
    sector: str = "",
) -> TickerDiagnostic:
    """Full v1.1 pass/fail explanation; hard gates match ``evaluate_nss``."""
    weights = _nss_weights(config)
    min_bars = max(
        252,
        int(config.get("nss_ema_slow", 200)),
        int(config.get("nss_consolidation_lookback", 15)),
        int(config.get("nss_breakout_lookback", 20)),
    ) + 10

    diag = TickerDiagnostic(symbol=symbol, stock_name=stock_name, sector=sector)
    gp: Dict[str, bool] = {"has_data": True}

    if len(df) < min_bars:
        gp["history"] = False
        diag.granular_passed = gp
        diag.modules["history"] = ModuleDetail(
            "history", False, 0.0, "low", f"bars={len(df)}, need>={min_bars}"
        )
        return _mark_failure(diag, "history", diag.modules["history"].explanation, weights, config, granular="history")

    gp["history"] = True
    close, high, low, volume = df["Close"], df["High"], df["Low"], df["Volume"]
    latest = float(close.iloc[-1])

    liq_pass, traded_inr = _early_liquidity(df, config)
    traded_cr = round(traded_inr / _CRORE, 2)
    gp["liquidity"] = liq_pass
    diag.modules["liquidity"] = ModuleDetail(
        "liquidity",
        liq_pass,
        100.0 if liq_pass else min(100.0, 100 * traded_inr / (float(config.get("nss_min_avg_traded_value_cr", 10)) * _CRORE)),
        confidence_from_score(100.0 if liq_pass else 30.0),
        f"avg_traded={traded_cr} Cr (precheck)",
    )

    ema50 = ema(close, int(config.get("nss_ema_fast", 50)))
    ema200 = ema(close, int(config.get("nss_ema_slow", 200)))
    st_line, st_trend = supertrend(
        df,
        period=int(config.get("nss_supertrend_period", 10)),
        multiplier=float(config.get("nss_supertrend_multiplier", 3.0)),
    )

    slope200 = _ema_slope(ema200, int(config.get("nss_trend_slope_lookback", 20)))
    trend_ok = latest > float(ema50.iloc[-1]) > float(ema200.iloc[-1]) and slope200 > 0
    trend_score = min(100.0, 60.0 + 100.0 * (float(ema50.iloc[-1]) - float(ema200.iloc[-1])) / latest * 5) if trend_ok else 0.0
    gp["trend"] = trend_ok
    diag.modules["trend"] = ModuleDetail(
        "trend", trend_ok, trend_score, confidence_from_score(trend_score),
        f"EMA50>EMA200, slope200={'+' if slope200 > 0 else '-'}",
    )
    if not trend_ok:
        diag.granular_passed = gp
        return _mark_failure(diag, "trend", diag.modules["trend"].explanation, weights, config, granular="trend")

    swing_pass = True
    swing_expl = "no recent ST flip"
    if config.get("nss_exclude_swing_overlap", True):
        if supertrend_flip_to_buy_within(st_trend, sessions=int(config.get("swing_flip_lookback_sessions", 3))):
            swing_pass = False
            swing_expl = "ST flip within swing lookback"
    mom_pass = True
    mom_expl = "not in momentum continuation zone"
    if config.get("nss_exclude_momentum_overlap", True):
        min_buy = int(config.get("momentum_st_min_buy_sessions", 4))
        if supertrend_buy_age(st_trend) >= min_buy:
            ext = 100.0 * (latest - float(ema50.iloc[-1])) / float(ema50.iloc[-1])
            if ext > float(config.get("nss_momentum_overlap_ext_pct", 8.0)):
                mom_pass = False
                mom_expl = f"ST buy age>={min_buy}, ext={ext:.1f}%"

    overlap_ok = swing_pass and mom_pass
    gp["overlap"] = overlap_ok
    diag.modules["swing_overlap"] = ModuleDetail("swing_overlap", swing_pass, 100.0 if swing_pass else 0.0, confidence_from_score(100 if swing_pass else 0), swing_expl)
    diag.modules["momentum_overlap"] = ModuleDetail("momentum_overlap", mom_pass, 100.0 if mom_pass else 0.0, confidence_from_score(100 if mom_pass else 0), mom_expl)
    if not overlap_ok:
        diag.granular_passed = gp
        stage = "swing_overlap" if not swing_pass else "momentum_overlap"
        return _mark_failure(diag, stage, swing_expl if not swing_pass else mom_expl, weights, config, granular="overlap")

    cons_mod, cons_gate = evaluate_consolidation_subchecks(df, config, ema50=ema50, higher_lows_fn=_higher_lows_score)
    diag.modules["consolidation"] = cons_mod
    for sk, sub in cons_mod.submodules.items():
        gp[sk] = sub.passed
        diag.modules[sk] = sub
    gp["consolidation"] = cons_gate
    if not cons_gate:
        diag.granular_passed = gp
        gran = _first_consolidation_fail(cons_mod)
        return _mark_failure(diag, "consolidation", cons_mod.explanation, weights, config, granular=gran)

    br_mod, br_gate, _ext = evaluate_breakout_module(close, high, latest, config)
    diag.modules["breakout"] = br_mod
    for sk, sub in br_mod.submodules.items():
        gp[sk] = sub.passed
        diag.modules[sk] = sub
    gp["breakout_price"] = True
    gp["breakout_freshness"] = br_mod.submodules["breakout_freshness"].passed
    if not br_gate:
        diag.granular_passed = gp
        gran = "breakout_freshness" if br_mod.submodules["breakout_price"].passed else "breakout_price"
        return _mark_failure(diag, "breakout", br_mod.explanation, weights, config, granular=gran)

    rel_vol = relative_volume(volume, int(config.get("nss_volume_lookback", 20)))
    vol_mod, vol_gate = evaluate_volume_module(rel_vol, config)
    diag.modules["volume_expansion"] = vol_mod
    diag.modules["volume"] = vol_mod
    gp["volume_expansion"] = True

    rsi_val = float(rsi(close, int(config.get("nss_rsi_period", 14))).iloc[-1])
    adx_val = float(adx(df, int(config.get("nss_adx_period", 14))).iloc[-1])
    rsi_min = float(config.get("nss_rsi_min", 45.0))
    rsi_max = float(config.get("nss_rsi_max", 65.0))
    adx_min = float(config.get("nss_adx_min", 15.0))
    mom_ok = rsi_min <= rsi_val <= rsi_max and np.isfinite(adx_val) and adx_val >= adx_min
    mom_score = 0.0
    if rsi_min <= rsi_val <= rsi_max:
        mom_score += 50.0
    if adx_val >= adx_min:
        mom_score += min(50.0, adx_val)
    mom_score = min(100.0, mom_score)
    gp["momentum"] = mom_ok
    diag.modules["momentum"] = ModuleDetail(
        "momentum", mom_ok, mom_score, confidence_from_score(mom_score),
        f"RSI={rsi_val:.1f}, ADX={adx_val:.1f}",
    )
    if not mom_ok:
        diag.granular_passed = gp
        return _mark_failure(diag, "momentum", diag.modules["momentum"].explanation, weights, config, granular="momentum")

    c_look = int(config.get("nss_consolidation_lookback", 15))
    cons_low = float(low.iloc[-c_look:].min())
    st_stop = float(st_line.iloc[-1]) if np.isfinite(st_line.iloc[-1]) else cons_low
    stop = max(cons_low, st_stop)
    if stop >= latest:
        stop = st_stop if st_stop < latest else cons_low
    if stop <= 0 or stop >= latest:
        diag.granular_passed = gp
        return _mark_failure(diag, "risk_setup", f"invalid stop={stop:.2f}", weights, config, granular="risk")

    levels = compute_trade_levels(
        entry=latest, stop_loss=stop,
        target_1_rr=float(config.get("nss_target_1_rr", 1.5)),
        target_2_rr=float(config.get("nss_target_2_rr", 2.5)),
    )
    if levels is None:
        diag.granular_passed = gp
        return _mark_failure(diag, "risk_setup", "trade levels invalid", weights, config, granular="risk")

    risk_pct = 100.0 * (latest - stop) / latest
    max_risk = resolve_threshold(config, "nss_max_risk_pct", 8.0)
    risk_ok = risk_pct <= max_risk
    risk_score = max(0.0, 100.0 - risk_pct * 10.0) if risk_ok else 0.0
    gp["risk"] = risk_ok
    diag.modules["risk"] = ModuleDetail(
        "risk", risk_ok, risk_score, confidence_from_score(risk_score),
        f"risk={risk_pct:.1f}%, max={max_risk:.1f}%",
    )
    if not risk_ok:
        diag.granular_passed = gp
        return _mark_failure(diag, "risk", diag.modules["risk"].explanation, weights, config, granular="risk")

    if is_at_new_52_week_low(close):
        diag.granular_passed = gp
        return _mark_failure(diag, "fifty_two_week", "at 52-week low", weights, config, granular="risk")

    composite = _weighted_composite(diag.modules, weights)
    min_score = resolve_threshold(config, "nss_min_score", 50.0)
    comp_ok = composite >= min_score
    gp["composite"] = comp_ok
    diag.modules["composite"] = ModuleDetail(
        "composite", comp_ok, composite, confidence_from_score(composite),
        f"score={composite:.1f}, min={min_score:.1f}",
    )
    diag.granular_passed = gp
    diag.would_pass_pipeline = comp_ok
    _sync_stages(diag)
    _finalize_scores(diag, weights, config)

    if not comp_ok:
        return _mark_failure(diag, "composite", diag.modules["composite"].explanation, weights, config, granular="composite")

    diag.status = "pipeline_pass"
    return diag


def _apply_post_pipeline_filters(
    diag: TickerDiagnostic,
    config: dict,
    *,
    avg_traded_inr: float,
    market_cap_inr: Optional[float],
) -> TickerDiagnostic:
    min_traded_inr = float(config.get("nss_min_avg_traded_value_cr", 10.0)) * _CRORE
    min_cap_inr = float(config.get("nss_min_market_cap_cr", 5000.0)) * _CRORE
    traded_cr = round(avg_traded_inr / _CRORE, 2)
    diag.avg_traded_value_cr = traded_cr

    liq_pass = avg_traded_inr >= min_traded_inr
    diag.modules["liquidity_final"] = ModuleDetail(
        "liquidity_final", liq_pass, 100.0 if liq_pass else 50.0,
        confidence_from_score(100 if liq_pass else 50),
        f"avg_traded={traded_cr} Cr, min={config.get('nss_min_avg_traded_value_cr', 10)} Cr",
    )
    if not liq_pass:
        diag.status = "rejected"
        diag.granular_passed["liquidity"] = False
        if diag.failure_stage is None:
            diag.failure_stage = "liquidity"
            diag.granular_failure_stage = "liquidity"
            diag.failure_reason = diag.modules["liquidity_final"].explanation
        return diag

    cap_cr = round(market_cap_inr / _CRORE, 1) if market_cap_inr else None
    diag.market_cap_cr = cap_cr
    cap_pass = market_cap_inr is not None and market_cap_inr >= min_cap_inr
    diag.modules["market_cap"] = ModuleDetail(
        "market_cap", cap_pass, 100.0 if cap_pass else 0.0,
        confidence_from_score(100 if cap_pass else 0),
        f"mcap={cap_cr} Cr" if cap_cr else "mcap unavailable",
    )
    diag.granular_passed["market_cap"] = cap_pass
    if not cap_pass:
        diag.status = "rejected"
        if diag.failure_stage is None:
            diag.failure_stage = "market_cap"
            diag.granular_failure_stage = "market_cap"
            diag.failure_reason = diag.modules["market_cap"].explanation
        return diag

    diag.status = "picked"
    diag.failure_stage = None
    diag.granular_failure_stage = None
    diag.failure_reason = ""
    diag.granular_passed["picked"] = True
    top_mod = max(
        (m for k, m in diag.modules.items() if k in ("consolidation", "breakout", "volume_expansion")),
        key=lambda m: m.score,
        default=None,
    )
    diag.selection_reason = (
        f"Passed all gates; strongest module: {top_mod.name} ({top_mod.explanation})"
        if top_mod else "Passed all NSS gates"
    )
    return diag


def _waterfall_labels() -> Dict[str, str]:
    return {
        "universe": "Universe",
        "has_data": "Has price data",
        "history": "History",
        "liquidity": "Liquidity",
        "trend": "Trend",
        "overlap": "Overlap filter",
        "trading_range": "Trading range",
        "atr_contraction": "ATR contraction",
        "ema_support": "EMA support",
        "volume_dryup": "Volume dry-up",
        "higher_lows": "Higher lows",
        "price_compression": "Price compression",
        "consolidation": "Consolidation (gate)",
        "breakout_price": "Breakout",
        "breakout_freshness": "Breakout freshness",
        "volume_expansion": "Volume expansion",
        "momentum": "Momentum",
        "risk": "Risk",
        "composite": "Composite score",
        "market_cap": "Market cap",
        "picked": "Final candidates",
    }


def _passed_through(d: TickerDiagnostic, stage: str) -> bool:
    if stage == "universe":
        return True
    if d.failure_stage == "no_data":
        return False
    if stage == "picked":
        return d.status == "picked"

    order = EXPANDED_WATERFALL_ORDER
    if stage not in order:
        return False
    idx = order.index(stage)
    gp = d.granular_passed or {}

    for s in order[: idx + 1]:
        if s == "has_data":
            if not gp.get("has_data", True):
                return False
        elif not gp.get(s, False):
            return False
    return True


def _count_stage(diagnostics: List[TickerDiagnostic], stage: str, universe_size: int) -> int:
    if stage == "universe":
        return universe_size
    return sum(1 for d in diagnostics if _passed_through(d, stage))


def _build_waterfall(diagnostics: List[TickerDiagnostic], universe_size: int) -> List[WaterfallStep]:
    labels = _waterfall_labels()
    steps: List[WaterfallStep] = []
    prev = universe_size
    steps.append(WaterfallStep("universe", labels["universe"], universe_size, universe_size, 0, 0.0))

    for stage in EXPANDED_WATERFALL_ORDER:
        out = _count_stage(diagnostics, stage, universe_size)
        dropped = prev - out
        pct = round(100.0 * dropped / prev, 1) if prev else 0.0
        steps.append(WaterfallStep(stage, labels.get(stage, stage), prev, out, dropped, pct))
        prev = out
    return steps


def _threshold_details(diag: TickerDiagnostic, config: dict) -> tuple[Optional[str], Optional[str], Optional[str], float]:
    min_score = resolve_threshold(config, "nss_min_score", 50.0)
    stage = diag.granular_failure_stage or diag.failure_stage or ""
    req = act = dist = None
    gap = max(0.0, min_score - diag.partial_score)

    if stage in ("volume", "volume_expansion"):
        mult = resolve_threshold(config, "nss_volume_mult", 1.2)
        vol_mod = diag.modules.get("volume_expansion")
        rel = None
        if vol_mod:
            for token in vol_mod.explanation.split():
                if token.startswith("rel_vol="):
                    rel = token.replace("rel_vol=", "").replace("x", "")
        req = f"{mult:.2f}x"
        act = f"{rel}x" if rel else "n/a"
        if rel:
            try:
                dist = f"{float(mult) - float(rel):.2f}x short"
            except ValueError:
                dist = None
    elif stage == "composite":
        req = f"{min_score:.1f}"
        act = f"{diag.partial_score:.1f}"
        dist = f"{gap:.1f} points short"
    elif stage == "breakout_freshness":
        fresh = int(resolve_threshold(config, "nss_breakout_fresh_sessions", 3))
        req = f"<= {fresh} sessions"
        act = "older breakout"
        dist = "outside freshness window"
    elif stage == "breakout_price":
        req = "close > prior range high"
        sub = diag.modules.get("breakout_price")
        if sub is None and diag.modules.get("breakout"):
            sub = diag.modules["breakout"].submodules.get("breakout_price")
        if sub:
            act = sub.explanation
        dist = "no breakout above range"
    elif stage in ("trading_range", "atr_contraction", "ema_support", "consolidation"):
        sub = diag.modules.get(stage)
        if sub is None and diag.modules.get("consolidation"):
            sub = diag.modules["consolidation"].submodules.get(stage)
        if sub:
            act = sub.explanation
            req = "consolidation gate"
            dist = "check failed"

    if stage in ("volume", "volume_expansion") and diag.partial_score >= min_score:
        gap = 0.0

    return req, act, dist, gap


def _near_misses(diagnostics: List[TickerDiagnostic], config: dict, *, limit: int = 50) -> List[NearMissEntry]:
    rejected = [d for d in diagnostics if d.status != "picked"]
    rejected.sort(key=lambda d: (sum(1 for v in d.granular_passed.values() if v), d.partial_score), reverse=True)
    entries: List[NearMissEntry] = []
    for i, d in enumerate(rejected[:limit], 1):
        req, act, dist, gap = _threshold_details(d, config)
        stage = d.granular_failure_stage or d.failure_stage or "unknown"
        entries.append(NearMissEntry(
            rank=i,
            symbol=d.symbol,
            stock_name=d.stock_name,
            failure_stage=stage,
            failure_reason=d.failure_reason,
            failed_condition=d.failure_reason,
            partial_score=d.partial_score,
            score_gap=round(gap, 2),
            threshold_required=req,
            threshold_actual=act,
            threshold_distance=dist,
            watch_action=build_near_miss_action(stage, required=req, actual=act, score_gap=gap),
            score_components=d.score_components,
            overall_confidence=d.overall_confidence,
            stages_passed=sum(1 for v in d.granular_passed.values() if v),
            stages_total=len(d.granular_passed),
        ))
    return entries


def run_scan_diagnostics(
    config: dict,
    progress: Optional[Callable[[str], None]] = None,
    *,
    near_miss_limit: int = 50,
    persist_health_metrics: bool = True,
) -> ScanDiagnosticReport:
    def _log(msg: str):
        if progress:
            progress(msg)

    universe = load_universe(
        csv_path=config.get("screen_universe_csv"),
        cache_dir=config.get("data_cache_dir"),
    )
    metadata = load_universe_metadata(
        csv_path=config.get("screen_universe_csv"),
        cache_dir=config.get("data_cache_dir"),
    )

    period = config.get("nss_history_period", "2y")
    _log(f"Downloading {period} history for {len(universe)} tickers...")
    price_data = download_history(universe, period=period)

    diagnostics: List[TickerDiagnostic] = []
    pipeline_pass: List[tuple[TickerDiagnostic, float]] = []

    for sym in universe:
        meta = metadata.get(sym, {})
        name = meta.get("name") or sym.replace(".NS", "")
        sector = meta.get("sector") or "—"
        df = price_data.get(sym)
        if df is None:
            d = TickerDiagnostic(
                symbol=sym, stock_name=name, sector=sector,
                failure_stage="no_data", granular_failure_stage="has_data",
                failure_reason="no price history",
            )
            d.granular_passed = {"has_data": False}
            diagnostics.append(d)
            continue

        diag = diagnose_nss(df, config, symbol=sym, stock_name=name, sector=sector)
        if diag.would_pass_pipeline:
            traded = float((df["Close"].iloc[-20:] * df["Volume"].iloc[-20:]).mean())
            pipeline_pass.append((diag, traded))
        diagnostics.append(diag)

    _log(f"Applying liquidity and market-cap filters to {len(pipeline_pass)} pipeline pass(es)...")
    caps: Dict[str, Optional[float]] = {}
    if pipeline_pass:
        caps = _fetch_market_caps([d.symbol for d, _ in pipeline_pass])
    for diag, traded in pipeline_pass:
        _apply_post_pipeline_filters(diag, config, avg_traded_inr=traded, market_cap_inr=caps.get(diag.symbol))

    rejection_by_stage: Dict[str, int] = {}
    for d in diagnostics:
        if d.status == "picked":
            continue
        stage = d.granular_failure_stage or d.failure_stage or "unknown"
        rejection_by_stage[stage] = rejection_by_stage.get(stage, 0) + 1

    picks = [d.symbol for d in diagnostics if d.status == "picked"]
    picks.sort(key=lambda s: next(d.partial_score for d in diagnostics if d.symbol == s), reverse=True)

    health = compute_health_from_diagnostics(diagnostics, len(universe))
    if persist_health_metrics:
        persist_health(health, config)
        _log(f"Market health persisted ({health.date})")

    return ScanDiagnosticReport(
        scanned_at=datetime.now().isoformat(timespec="seconds"),
        universe_size=len(universe),
        waterfall=_build_waterfall(diagnostics, len(universe)),
        picks=picks,
        rejected_count=sum(1 for d in diagnostics if d.status != "picked"),
        rejection_by_stage=rejection_by_stage,
        near_misses=_near_misses(diagnostics, config, limit=near_miss_limit),
        market_health=health.to_dict(),
        diagnostics=diagnostics,
    )


def explain_ticker(
    symbol: str,
    config: dict,
    *,
    price_data: Optional[Dict[str, pd.DataFrame]] = None,
) -> TickerDiagnostic:
    sym = symbol.upper().strip()
    if not sym.endswith(".NS") and not sym.endswith(".BO"):
        sym = f"{sym}.NS"

    metadata = load_universe_metadata(
        csv_path=config.get("screen_universe_csv"),
        cache_dir=config.get("data_cache_dir"),
    )
    meta = metadata.get(sym, {})
    name = meta.get("name") or sym.replace(".NS", "")
    sector = meta.get("sector") or "—"

    if price_data is None:
        price_data = download_history([sym], period=config.get("nss_history_period", "2y"))

    df = price_data.get(sym)
    if df is None:
        return TickerDiagnostic(
            symbol=sym, stock_name=name, sector=sector,
            failure_stage="no_data", failure_reason="no price history",
        )

    diag = diagnose_nss(df, config, symbol=sym, stock_name=name, sector=sector)
    if diag.would_pass_pipeline:
        traded = float((df["Close"].iloc[-20:] * df["Volume"].iloc[-20:]).mean())
        caps = _fetch_market_caps([sym])
        _apply_post_pipeline_filters(diag, config, avg_traded_inr=traded, market_cap_inr=caps.get(sym))

    snap = evaluate_nss(df, config)
    if snap and diag.status == "picked":
        diag.composite_score = snap.composite_score
    return diag
