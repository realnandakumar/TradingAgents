"""Echo-inspired pattern finder: correlate recent price action with 2y history.

v1: Pearson correlation on 20-day returns, best non-overlapping analogue,
5-day projection + mandatory SL from scaled analogue min low.

v1.1 (accuracy-tuned): bullish-only analogues, 2-of-5 consensus median,
recency-weighted composite score, min hist forward 1.5%, Pearson correlation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

from tradingagents.screening.pattern_forecast_filters import (
    atr_regime_match,
    cap_target_with_atr,
    compute_stop_v17,
    consensus_dispersion_ok,
    stock_regime_ok,
    volume_fwd_confirmed,
    weekly_regime_ok,
)

STRATEGY_ID = "pattern_forecast"
STRATEGY_NAME = "Pattern Forecast"
STRATEGY_VERSION = "1.1"


@dataclass
class PatternForecastSignal:
    symbol: str
    direction: str = "NONE"  # UP | DOWN | NONE
    probability: float = 0.0  # 0-100, from correlation strength
    correlation: float = 0.0
    composite_score: float = 0.0
    hist_fwd_return_pct: float = 0.0
    risk_reward: float = 0.0
    close: float = 0.0
    projected_close_5d: float = 0.0
    projected_max_high_5d: float = 0.0
    projected_min_low_5d: float = 0.0
    stop_loss: float = 0.0
    stop_loss_pct: float = 0.0
    projected_move_pct: float = 0.0
    projected_max_pct: float = 0.0
    pattern_window: int = 20
    horizon_days: int = 5
    analogue_end_date: str = ""
    bullish_analogues: int = 0
    consensus_count: int = 0
    remark: str = ""
    rejected: bool = False
    reject_reason: str = ""
    stock_name: str = ""
    sector: str = ""
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "strategy_id": STRATEGY_ID,
            "strategy_name": STRATEGY_NAME,
            "version": STRATEGY_VERSION,
            "symbol": self.symbol,
            "direction": self.direction,
            "probability": self.probability,
            "correlation": self.correlation,
            "composite_score": self.composite_score,
            "hist_fwd_return_pct": self.hist_fwd_return_pct,
            "risk_reward": self.risk_reward,
            "close": self.close,
            "projected_close_5d": self.projected_close_5d,
            "projected_max_high_5d": self.projected_max_high_5d,
            "projected_min_low_5d": self.projected_min_low_5d,
            "stop_loss": self.stop_loss,
            "stop_loss_pct": self.stop_loss_pct,
            "projected_move_pct": self.projected_move_pct,
            "projected_max_pct": self.projected_max_pct,
            "pattern_window": self.pattern_window,
            "horizon_days": self.horizon_days,
            "analogue_end_date": self.analogue_end_date,
            "bullish_analogues": self.bullish_analogues,
            "consensus_count": self.consensus_count,
            "remark": self.remark,
            "rejected": self.rejected,
            "reject_reason": self.reject_reason,
            "reasons": self.reasons,
        }


@dataclass
class _AnalogueCandidate:
    start_i: int
    correlation: float
    hist_fwd_return_pct: float
    projected_close: float
    projected_max: float
    projected_min: float
    stop_loss: float
    move_pct: float
    max_pct: float
    risk_reward: float
    composite_score: float
    analogue_end_date: str


def _return_series(close: pd.Series) -> np.ndarray:
    """Daily pct returns; first NaN filled with 0."""
    r = close.pct_change().replace([np.inf, -np.inf], np.nan).fillna(0.0).to_numpy(dtype=float)
    return r


def _segment_correlation(pattern: np.ndarray, seg: np.ndarray, method: str = "pearson") -> float:
    """Pearson or Spearman correlation between two return windows."""
    if method == "spearman":
        c = pd.Series(pattern).corr(pd.Series(seg), method="spearman")
        return float(c) if c is not None and not np.isnan(c) else float("nan")
    c = float(np.corrcoef(pattern, seg)[0, 1])
    return c


def _search_end(n: int, window: int, horizon: int) -> int:
    return min(n - 2 * window + 1, n - window - horizon)


def find_best_analogue(
    returns: np.ndarray,
    window: int,
    horizon: int,
) -> Tuple[int, float]:
    """Return (start_index, correlation) of best historical match (v1 compat)."""
    n = len(returns)
    if n < window + horizon + 10:
        return -1, 0.0

    pattern = returns[-window:]
    if pattern.std() < 1e-12:
        return -1, 0.0

    search_end = _search_end(n, window, horizon)
    if search_end <= 0:
        return -1, 0.0

    best_i = -1
    best_corr = -2.0
    for i in range(search_end):
        seg = returns[i : i + window]
        if seg.std() < 1e-12:
            continue
        c = float(np.corrcoef(pattern, seg)[0, 1])
        if np.isnan(c):
            continue
        if c > best_corr:
            best_corr = c
            best_i = i

    return best_i, best_corr


def nifty_regime_ok(
    benchmark_df: Optional[pd.DataFrame],
    ma_period: int = 20,
) -> Tuple[bool, str]:
    """True when Nifty close is above its moving average (long-friendly regime)."""
    if benchmark_df is None or benchmark_df.empty or "Close" not in benchmark_df.columns:
        return True, "no benchmark data"
    close = benchmark_df["Close"].astype(float)
    if len(close) < ma_period:
        return True, f"insufficient benchmark bars ({len(close)} < {ma_period})"
    ma = float(close.rolling(ma_period).mean().iloc[-1])
    last = float(close.iloc[-1])
    if last > ma:
        return True, f"Nifty {last:.0f} > MA{ma_period} {ma:.0f}"
    return False, f"Nifty {last:.0f} below MA{ma_period} {ma:.0f}"


def _composite_score(
    correlation: float,
    hist_fwd_pct: float,
    risk_reward: float,
    recency_factor: float = 1.0,
) -> float:
    return round(
        correlation * (1.0 + hist_fwd_pct / 100.0) * min(risk_reward, 3.0) * recency_factor,
        4,
    )


def _recency_factor(start_i: int, search_end: int, weight: float) -> float:
    """Boost more recent analogues (higher index = closer to today)."""
    if weight <= 0 or search_end <= 1:
        return 1.0
    return 1.0 + weight * (start_i / (search_end - 1))


def _find_bullish_candidates(
    df: pd.DataFrame,
    close: pd.Series,
    high: pd.Series,
    low: pd.Series,
    returns: np.ndarray,
    window: int,
    horizon: int,
    min_corr: float,
    min_hist_fwd_pct: float,
    config: dict,
    corr_method: str = "pearson",
) -> List[_AnalogueCandidate]:
    use_v17 = bool(config.get("pattern_forecast_use_v17", False))
    max_stop_pct = float(config.get("pattern_forecast_max_stop_pct", 7.0))
    min_stop_pct = float(config.get("pattern_forecast_min_stop_pct", 2.0))
    n = len(returns)
    search_end = _search_end(n, window, horizon)
    if search_end <= 0:
        return []

    pattern = returns[-window:]
    if pattern.std() < 1e-12:
        return []

    current_close = float(close.iloc[-1])
    candidates: List[_AnalogueCandidate] = []
    recency_weight = float(config.get("pattern_forecast_recency_weight", 0.0))

    for i in range(search_end):
        seg = returns[i : i + window]
        if seg.std() < 1e-12:
            continue
        corr = _segment_correlation(pattern, seg, method=corr_method)
        if np.isnan(corr) or corr < min_corr:
            continue

        hist_end_idx = i + window - 1
        fwd_start = i + window
        fwd_end = fwd_start + horizon

        hist_close_end = float(close.iloc[hist_end_idx])
        if hist_close_end <= 0:
            continue

        hist_fwd_close = float(close.iloc[fwd_end - 1])
        hist_fwd_pct = 100.0 * (hist_fwd_close - hist_close_end) / hist_close_end
        if hist_fwd_pct < min_hist_fwd_pct:
            continue

        hist_fwd_max = float(high.iloc[fwd_start:fwd_end].max())
        hist_fwd_min = float(low.iloc[fwd_start:fwd_end].min())
        scale = current_close / hist_close_end

        projected_close = round(hist_fwd_close * scale, 2)
        projected_max = round(hist_fwd_max * scale, 2)
        projected_min = round(hist_fwd_min * scale, 2)

        if use_v17:
            projected_max = cap_target_with_atr(current_close, projected_max, df, config)
            stop = compute_stop_v17(current_close, df, projected_min, window, config)
        else:
            stop = _clamp_stop_loss(current_close, projected_min, max_stop_pct, min_stop_pct)
        if stop is None:
            continue

        risk = current_close - stop
        if risk <= 0:
            continue
        rr = (projected_max - current_close) / risk
        move_pct = round(100.0 * (projected_close - current_close) / current_close, 2)
        max_pct = round(100.0 * (projected_max - current_close) / current_close, 2)

        try:
            analogue_date = close.index[hist_end_idx].strftime("%Y-%m-%d")
        except Exception:  # noqa: BLE001
            analogue_date = ""

        score = _composite_score(
            corr, hist_fwd_pct, rr, _recency_factor(i, search_end, recency_weight)
        )
        candidates.append(
            _AnalogueCandidate(
                start_i=i,
                correlation=corr,
                hist_fwd_return_pct=round(hist_fwd_pct, 2),
                projected_close=projected_close,
                projected_max=projected_max,
                projected_min=projected_min,
                stop_loss=stop,
                move_pct=move_pct,
                max_pct=max_pct,
                risk_reward=round(rr, 2),
                composite_score=score,
                analogue_end_date=analogue_date,
            )
        )

    candidates.sort(key=lambda c: c.composite_score, reverse=True)
    return candidates


def _filter_analogue_pool_v17(
    candidates: List[_AnalogueCandidate],
    df: pd.DataFrame,
    window: int,
    horizon: int,
    config: dict,
) -> List[_AnalogueCandidate]:
    """Keep analogues whose historical window matches current ATR/volume regime."""
    if not bool(config.get("pattern_forecast_use_v17", True)):
        return candidates
    if not bool(config.get("pattern_forecast_require_analogue_quality", True)):
        return candidates
    atr_tol = float(config.get("pattern_forecast_atr_regime_tolerance_pct", 40.0))
    atr_period = int(config.get("pattern_forecast_atr_period", 14))
    min_vol_ratio = float(config.get("pattern_forecast_min_fwd_volume_ratio", 0.8))
    kept: List[_AnalogueCandidate] = []
    for cand in candidates:
        hist_end_idx = cand.start_i + window - 1
        fwd_start = cand.start_i + window
        fwd_end = fwd_start + horizon
        ok, _ = atr_regime_match(df, hist_end_idx, atr_tol, atr_period)
        if not ok:
            continue
        ok, _ = volume_fwd_confirmed(df, fwd_start, fwd_end, min_vol_ratio)
        if not ok:
            continue
        kept.append(cand)
    return kept


def _analogue_quality_ok(
    cand: _AnalogueCandidate,
    df: pd.DataFrame,
    window: int,
    horizon: int,
    config: dict,
) -> Tuple[bool, str]:
    pool = _filter_analogue_pool_v17([cand], df, window, horizon, config)
    if pool:
        return True, "analogue quality ok"
    return False, "anchor analogue failed ATR/volume quality"


def _build_consensus(
    candidates: List[_AnalogueCandidate],
    top_n: int,
    min_agree: int,
    current_close: float,
    config: dict,
) -> Optional[Tuple[_AnalogueCandidate, int]]:
    """Median projection from top analogues; dispersion cap in v1.7."""
    if len(candidates) < min_agree:
        return None

    pool = candidates[:top_n]
    if len(pool) < min_agree:
        return None

    median_n = int(config.get("pattern_forecast_consensus_median_n", 3))
    median_pool = pool[: min(median_n, len(pool))]

    if bool(config.get("pattern_forecast_use_consensus_dispersion", False)) or bool(
        config.get("pattern_forecast_use_v17", False)
    ):
        max_disp = float(config.get("pattern_forecast_consensus_dispersion_max_pct", 12.0))
        ok, _ = consensus_dispersion_ok(median_pool, max_disp, current_close)
        if not ok:
            return None

    proj_close = round(float(np.median([c.projected_close for c in median_pool])), 2)
    proj_max = round(float(np.median([c.projected_max for c in median_pool])), 2)
    proj_min = round(float(np.median([c.projected_min for c in median_pool])), 2)
    stop = round(float(np.median([c.stop_loss for c in median_pool])), 2)

    if stop >= current_close or stop <= 0:
        return None

    risk = current_close - stop
    if risk <= 0:
        return None

    move_pct = round(100.0 * (proj_close - current_close) / current_close, 2)
    max_pct = round(100.0 * (proj_max - current_close) / current_close, 2)
    rr = (proj_max - current_close) / risk

    corr = float(np.median([c.correlation for c in median_pool]))
    hist_fwd = round(float(np.median([c.hist_fwd_return_pct for c in median_pool])), 2)
    score = _composite_score(corr, hist_fwd, rr)
    anchor = pool[0]

    merged = _AnalogueCandidate(
        start_i=anchor.start_i,
        correlation=corr,
        hist_fwd_return_pct=hist_fwd,
        projected_close=proj_close,
        projected_max=proj_max,
        projected_min=proj_min,
        stop_loss=stop,
        move_pct=move_pct,
        max_pct=max_pct,
        risk_reward=round(rr, 2),
        composite_score=score,
        analogue_end_date=anchor.analogue_end_date,
    )
    return merged, len(pool)


def evaluate_pattern_forecast(
    df: pd.DataFrame,
    config: Optional[dict] = None,
    symbol: str = "",
    benchmark_df: Optional[pd.DataFrame] = None,
) -> PatternForecastSignal:
    """Find best bullish 2y analogue and project 5-day UP target + mandatory SL."""
    config = config or {}
    window = int(config.get("pattern_forecast_window", 20))
    horizon = int(config.get("pattern_forecast_horizon", 5))
    min_corr = float(config.get("pattern_forecast_min_correlation", 0.60))
    min_bars = int(config.get("pattern_forecast_min_bars", 126))
    bullish_only = bool(config.get("pattern_forecast_bullish_only", True))
    use_v17 = bool(config.get("pattern_forecast_use_v17", False))
    min_hist_fwd = float(config.get("pattern_forecast_min_hist_fwd_pct", 2.0 if use_v17 else 1.0))
    min_move = float(config.get("pattern_forecast_min_projected_move_pct", 2.0))
    max_move = float(config.get("pattern_forecast_max_projected_move_pct", 12.0 if use_v17 else 15.0))
    min_max_touch = float(config.get("pattern_forecast_min_max_touch_pct", 3.0))
    min_rr = float(config.get("pattern_forecast_min_risk_reward", 2.0 if use_v17 else 1.5))
    max_stop_pct = float(config.get("pattern_forecast_max_stop_pct", 7.0 if use_v17 else 5.0))
    min_stop_pct = float(config.get("pattern_forecast_min_stop_pct", 2.0))
    require_nifty = bool(config.get("pattern_forecast_require_nifty_above_ma", True))
    require_stock_ma = bool(config.get("pattern_forecast_require_stock_above_ma", True))
    stock_ma = int(config.get("pattern_forecast_stock_ma_period", 20))
    min_stock_ret = float(config.get("pattern_forecast_min_stock_return_20d", 0.0))
    require_weekly = bool(config.get("pattern_forecast_require_weekly_above_ma", True))
    weekly_ma = int(config.get("pattern_forecast_weekly_ma_period", 10))
    nifty_ma = int(config.get("pattern_forecast_nifty_ma_period", 20))
    corr_method = str(config.get("pattern_forecast_correlation_method", "pearson")).lower()
    consensus_top_n = int(config.get("pattern_forecast_consensus_top_n", 5))
    consensus_min = int(config.get("pattern_forecast_consensus_min_agree", 2))
    use_consensus = bool(config.get("pattern_forecast_use_consensus", True))

    empty = PatternForecastSignal(symbol=symbol, direction="NONE", rejected=True)

    if df is None or len(df) < min_bars:
        empty.reject_reason = f"Insufficient history (need >= {min_bars} bars)"
        empty.remark = f"REJECT - {empty.reject_reason}"
        return empty
    if "Close" not in df.columns:
        empty.reject_reason = "Missing Close column"
        empty.remark = f"REJECT - {empty.reject_reason}"
        return empty

    close = df["Close"].astype(float)
    current_close = float(close.iloc[-1])
    if bool(config.get("pattern_forecast_require_positive_20d_return", False)):
        if len(close) >= 21:
            ret_20 = 100.0 * (current_close - float(close.iloc[-21])) / float(close.iloc[-21])
            min_ret = float(config.get("pattern_forecast_min_stock_return_20d", 0.0))
            if ret_20 < min_ret:
                empty.reject_reason = (
                    f"Momentum filter: 20d return {ret_20:.1f}% below min {min_ret:.1f}%"
                )
                empty.remark = f"REJECT - {empty.reject_reason}"
                return empty

    if require_nifty:
        ok, nifty_note = nifty_regime_ok(benchmark_df, ma_period=nifty_ma)
        if not ok:
            empty.reject_reason = f"Nifty regime filter: {nifty_note}"
            empty.remark = f"REJECT - {empty.reject_reason}"
            return empty

    if use_v17 and require_stock_ma:
        ok, stock_note = stock_regime_ok(df, ma_period=stock_ma, min_return_20d_pct=min_stock_ret)
        if not ok:
            empty.reject_reason = f"Stock regime filter: {stock_note}"
            empty.remark = f"REJECT - {empty.reject_reason}"
            return empty

    if use_v17 and require_weekly:
        ok, weekly_note = weekly_regime_ok(df, ma_period=weekly_ma)
        if not ok:
            empty.reject_reason = f"Weekly regime filter: {weekly_note}"
            empty.remark = f"REJECT - {empty.reject_reason}"
            return empty

    close = df["Close"].astype(float)
    high = df["High"].astype(float) if "High" in df.columns else close
    low = df["Low"].astype(float) if "Low" in df.columns else close
    returns = _return_series(close)

    if bullish_only:
        candidates = _find_bullish_candidates(
            df, close, high, low, returns, window, horizon,
            min_corr, min_hist_fwd, config, corr_method=corr_method,
        )
        if not candidates:
            empty.reject_reason = (
                f"No bullish analogue ({corr_method} corr>={min_corr:.2f}, "
                f"hist fwd>={min_hist_fwd:.1f}%)"
            )
            empty.remark = f"REJECT - {empty.reject_reason}"
            return empty

        consensus_count = 1
        if use_consensus:
            built = _build_consensus(
                candidates, consensus_top_n, consensus_min, current_close, config
            )
            if built is None:
                empty.reject_reason = (
                    f"Consensus failed (need {consensus_min} of top {consensus_top_n}, "
                    f"have {len(candidates)} bullish)"
                )
                empty.remark = f"REJECT - {empty.reject_reason}"
                return empty
            best, consensus_count = built
            if use_v17:
                ok, note = _analogue_quality_ok(best, df, window, horizon, config)
                if not ok:
                    empty.reject_reason = f"Analogue quality filter: {note}"
                    empty.remark = f"REJECT - {empty.reject_reason}"
                    return empty
        else:
            best = candidates[0]
            if use_v17:
                ok, note = _analogue_quality_ok(best, df, window, horizon, config)
                if not ok:
                    empty.reject_reason = f"Analogue quality filter: {note}"
                    empty.remark = f"REJECT - {empty.reject_reason}"
                    return empty
    else:
        best_i, corr = find_best_analogue(returns, window=window, horizon=horizon)
        if best_i < 0 or corr < min_corr:
            empty.reject_reason = "No valid analogue"
            empty.remark = f"REJECT - {empty.reject_reason}"
            return empty
        hist_end_idx = best_i + window - 1
        fwd_start = best_i + window
        fwd_end = fwd_start + horizon
        hist_close_end = float(close.iloc[hist_end_idx])
        hist_fwd_close = float(close.iloc[fwd_end - 1])
        hist_fwd_pct = 100.0 * (hist_fwd_close - hist_close_end) / hist_close_end
        hist_fwd_max = float(high.iloc[fwd_start:fwd_end].max())
        hist_fwd_min = float(low.iloc[fwd_start:fwd_end].min())
        scale = current_close / hist_close_end
        projected_close = round(hist_fwd_close * scale, 2)
        projected_max = round(hist_fwd_max * scale, 2)
        projected_min = round(hist_fwd_min * scale, 2)
        stop = _clamp_stop_loss(current_close, projected_min, max_stop_pct, min_stop_pct)
        if stop is None:
            empty.reject_reason = "Could not derive mandatory stop loss"
            empty.remark = f"REJECT - {empty.reject_reason}"
            return empty
        risk = current_close - stop
        rr = (projected_max - current_close) / risk if risk > 0 else 0
        try:
            analogue_date = close.index[hist_end_idx].strftime("%Y-%m-%d")
        except Exception:  # noqa: BLE001
            analogue_date = ""
        best = _AnalogueCandidate(
            start_i=best_i,
            correlation=corr,
            hist_fwd_return_pct=round(hist_fwd_pct, 2),
            projected_close=projected_close,
            projected_max=projected_max,
            projected_min=projected_min,
            stop_loss=stop,
            move_pct=round(100.0 * (projected_close - current_close) / current_close, 2),
            max_pct=round(100.0 * (projected_max - current_close) / current_close, 2),
            risk_reward=round(rr, 2),
            composite_score=_composite_score(corr, hist_fwd_pct, rr),
            analogue_end_date=analogue_date,
        )
        candidates = [best]
        consensus_count = 1

    if best.move_pct > max_move:
        empty.reject_reason = (
            f"Projected move {best.move_pct:.1f}% exceeds cap {max_move:.1f}% (outlier)"
        )
        empty.remark = f"REJECT - {empty.reject_reason}"
        return empty
    if best.move_pct < min_move:
        empty.reject_reason = f"Projected move {best.move_pct:.1f}% below minimum {min_move:.1f}%"
        empty.remark = f"REJECT - {empty.reject_reason}"
        return empty
    if best.max_pct < min_max_touch:
        empty.reject_reason = f"Max touch {best.max_pct:.1f}% below minimum {min_max_touch:.1f}%"
        empty.remark = f"REJECT - {empty.reject_reason}"
        return empty
    if best.risk_reward < min_rr:
        empty.reject_reason = f"R:R {best.risk_reward:.2f} below minimum {min_rr:.2f}"
        empty.remark = f"REJECT - {empty.reject_reason}"
        return empty

    direction = "UP" if best.projected_close > current_close else "DOWN"
    if bullish_only and direction != "UP":
        empty.reject_reason = "Bullish-only mode requires UP projection"
        empty.remark = f"REJECT - {empty.reject_reason}"
        return empty

    probability = round(best.correlation * 100, 1)
    stop_loss_pct = round(-100.0 * (current_close - best.stop_loss) / current_close, 2)

    remark = (
        f"UP - score {best.composite_score:.3f} - {corr_method} corr {best.correlation:.2f} "
        f"({probability:.0f}%) - consensus {consensus_count}/{consensus_top_n} - "
        f"hist fwd +{best.hist_fwd_return_pct:.1f}% - R:R {best.risk_reward:.1f} - "
        f"analogue {best.analogue_end_date} - proj 5d {best.move_pct:+.1f}% - "
        f"max {best.projected_max:.2f} ({best.max_pct:+.1f}%) - SL {best.stop_loss:.2f}"
    )

    reasons = [
        f"v{STRATEGY_VERSION} BUY-only: {len(candidates)} bullish analogue(s), "
        f"consensus {consensus_count}/{consensus_top_n}",
        f"Correlation: {corr_method} · median corr {best.correlation:.3f} (min {min_corr:.2f})",
        f"Median hist forward: +{best.hist_fwd_return_pct:.2f}% (min {min_hist_fwd:.1f}%)",
        f"Composite score: {best.composite_score:.4f}",
        f"R:R {best.risk_reward:.2f} (min {min_rr:.1f}) · move {best.move_pct:+.2f}% "
        f"(cap {max_move:.1f}%)",
        f"SL {best.stop_loss:.2f} ({stop_loss_pct:.2f}%) · max {best.max_pct:+.2f}%",
        f"Anchor analogue {best.analogue_end_date}",
    ]
    if use_v17:
        reasons.append("v1.7 filters: stock MA, ATR/volume on top analogues, ATR stop/target")
    if require_nifty and benchmark_df is not None:
        _, nifty_note = nifty_regime_ok(benchmark_df, ma_period=nifty_ma)
        reasons.append(f"Nifty regime: {nifty_note}")

    return PatternForecastSignal(
        symbol=symbol,
        direction=direction,
        probability=probability,
        correlation=round(best.correlation, 4),
        composite_score=best.composite_score,
        hist_fwd_return_pct=best.hist_fwd_return_pct,
        risk_reward=best.risk_reward,
        close=round(current_close, 2),
        projected_close_5d=best.projected_close,
        projected_max_high_5d=best.projected_max,
        projected_min_low_5d=best.projected_min,
        stop_loss=best.stop_loss,
        stop_loss_pct=stop_loss_pct,
        projected_move_pct=best.move_pct,
        projected_max_pct=best.max_pct,
        pattern_window=window,
        horizon_days=horizon,
        analogue_end_date=best.analogue_end_date,
        bullish_analogues=len(candidates),
        consensus_count=consensus_count,
        remark=remark,
        rejected=False,
        reasons=reasons,
    )


def explain_pattern_forecast(ticker: str, config: dict) -> PatternForecastSignal:
    """Download one ticker and return pattern forecast with remarks."""
    from tradingagents.screening.prices import download_history

    symbol = ticker.upper()
    if not symbol.endswith((".NS", ".BO")):
        symbol = f"{symbol}.NS"
    period = config.get("pattern_forecast_history_period", "2y")
    benchmark = config.get("paper_benchmark", "^NSEI")
    data = download_history([symbol, benchmark], period=period)
    df = data.get(symbol)
    bench = data.get(benchmark)
    if df is None or df.empty:
        return PatternForecastSignal(
            symbol=symbol,
            rejected=True,
            reject_reason="No price history from Yahoo",
            remark="REJECT - no price history from Yahoo",
        )
    return evaluate_pattern_forecast(df, config, symbol=symbol, benchmark_df=bench)


def _clamp_stop_loss(
    entry: float,
    analogue_stop: float,
    max_stop_pct: float,
    min_stop_pct: float,
) -> Optional[float]:
    """Derive mandatory long stop from scaled analogue min low, clamped to risk band."""
    if entry <= 0:
        return None
    floor = round(entry * (1.0 - max_stop_pct / 100.0), 2)
    cap = round(entry * (1.0 - min_stop_pct / 100.0), 2)
    raw = round(min(analogue_stop, cap), 2)
    if raw >= entry:
        raw = cap
    if raw <= floor:
        raw = floor
    if raw <= 0 or raw >= entry:
        return None
    return raw
