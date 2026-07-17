"""Screening funnel: universe -> relative strength -> pattern engine -> rank,
then Market Analyst on top-N → RS Desk PM (Tech-Desk-style) on a separate book.

Reports are written to the shared ``tech_analyze_reports_dir`` so Tech Desk and
RS Desk both see the latest MA report per ticker.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from .levels import compute_levels
from .patterns import PatternScore, score_patterns
from .prices import download_history
from .relative_strength import RSResult, compute_relative_strength
from .universe import load_universe, load_universe_metadata

logger = logging.getLogger(__name__)


@dataclass
class Candidate:
    symbol: str
    rs: RSResult
    pattern: PatternScore
    composite: float
    levels: Optional[dict] = None
    sector: str = ""
    stock_name: str = ""
    decision_rating: Optional[str] = None
    report: Optional[str] = None
    ma_summary: Optional[dict] = None

    @property
    def fired_signals(self) -> List[str]:
        return self.pattern.fired


def screen_candidates(config: dict, progress: Optional[Callable[[str], None]] = None) -> List[Candidate]:
    """Run the free part of the funnel and return ranked candidates."""

    def _log(msg: str):
        logger.info(msg)
        if progress:
            progress(msg)

    benchmark = config.get("screen_benchmark", "^NSEI")
    period = config.get("screen_history_period", "1y")
    min_pct = float(config.get("screen_rs_min_percentile", 50.0))

    universe = load_universe(
        csv_path=config.get("screen_universe_csv"),
        cache_dir=config.get("data_cache_dir"),
    )
    metadata = load_universe_metadata(
        csv_path=config.get("screen_universe_csv"),
        cache_dir=config.get("data_cache_dir"),
        allow_download=True,
    )
    _log(f"Universe: {len(universe)} tickers")

    _log("Downloading price history (this is the slow-ish free step)...")
    price_data = download_history(universe, period=period)
    _log(f"Got usable history for {len(price_data)} tickers")

    rs_results = compute_relative_strength(
        universe, benchmark=benchmark, period=period, price_data=price_data
    )
    rs_results = [r for r in rs_results if r.rs_percentile >= min_pct]
    _log(f"{len(rs_results)} tickers pass the RS gate (>= {min_pct:.0f}th percentile)")

    candidates: List[Candidate] = []
    for r in rs_results:
        df = price_data.get(r.symbol)
        if df is None:
            continue
        ps = score_patterns(r.symbol, df)
        composite = ps.score + r.rs_percentile / 100.0
        levels = compute_levels(
            df,
            entry=r.close,
            stop_atr_mult=float(config.get("levels_stop_atr_mult", 2.0)),
            target_rr=float(config.get("levels_target_rr", 2.0)),
        )
        meta = metadata.get(r.symbol, {})
        candidates.append(
            Candidate(
                symbol=r.symbol,
                rs=r,
                pattern=ps,
                composite=composite,
                levels=levels,
                sector=meta.get("sector") or "—",
                stock_name=meta.get("name") or r.symbol.replace(".NS", "").replace(".BO", ""),
            )
        )

    candidates.sort(key=lambda c: c.composite, reverse=True)

    max_per_sector = int(config.get("paper_max_per_sector", 4))
    if max_per_sector > 0:
        from collections import Counter

        counts: Counter[str] = Counter()
        diversified: List[Candidate] = []
        for c in candidates:
            sector = c.sector or "—"
            if counts[sector] >= max_per_sector:
                continue
            diversified.append(c)
            counts[sector] += 1
        candidates = diversified

    return candidates


@dataclass
class ScreenRun:
    trade_date: str
    candidates: List[Candidate]
    paper_summary: Dict = field(default_factory=dict)
    opened: List[str] = field(default_factory=list)
    waits: List[str] = field(default_factory=list)
    skipped: List[dict] = field(default_factory=list)
    rs_desk_report: Dict = field(default_factory=dict)


def _analyze_candidate_ma(
    cand: Candidate,
    trade_date: str,
    config: dict,
) -> Tuple[Optional[dict], Optional[str]]:
    """Run Market Analyst only; save under shared tech_reports; return summary."""
    from tradingagents.analysis.tech_analyze import run_tech_analyze, save_tech_report
    from tradingagents.tech_desk.report_excerpt import extract_final_proposal, extract_pm_summary

    result = run_tech_analyze(cand.symbol, trade_date, config=config, asset_type="stock")
    market_report = result.get("market_report") or ""
    summary = extract_pm_summary(market_report) or {}
    if not summary.get("proposal"):
        proposal = (extract_final_proposal(market_report) or "").upper()
        if proposal:
            summary = {**summary, "proposal": proposal}

    try:
        base = Path(
            config.get("tech_analyze_reports_dir")
            or Path.home() / ".tradingagents" / "tech_reports"
        )
        out = base / cand.symbol.replace(".NS", "").replace(".BO", "") / trade_date
        save_tech_report(result, out)
    except Exception as e:  # noqa: BLE001
        logger.warning("Could not save tech report for %s (%s)", cand.symbol, e)

    return summary or None, market_report


def run_screen(
    config: dict,
    trade_date: Optional[str] = None,
    progress: Optional[Callable[[str], None]] = None,
    analyze: bool = True,
) -> ScreenRun:
    """Full funnel: screen → MA on top-N → RS Desk PM → separate RS book."""
    from tradingagents.rs_desk import as_tech_desk_config, run_rs_desk_process
    from tradingagents.tech_desk.manager import TechDeskPaperTradeManager
    from tradingagents.tech_desk.plan_from_ma import trade_plan_from_pm_summary
    from tradingagents.tech_desk.schemas import PlanAction

    def _log(msg: str):
        if progress:
            progress(msg)

    trade_date = trade_date or datetime.now().strftime("%Y-%m-%d")
    top_n = int(config.get("screen_top_n", 10))
    min_conf = int(config.get("rs_desk_min_confidence", config.get("tech_desk_min_confidence", 60)))

    all_candidates = screen_candidates(config, progress=progress)
    top = all_candidates[:top_n]
    _log(f"Selected top {len(top)} of {len(all_candidates)} candidates for Market Analyst")

    rs_cfg = as_tech_desk_config(config)
    manager = TechDeskPaperTradeManager(rs_cfg)
    run = ScreenRun(trade_date=trade_date, candidates=top)
    run.paper_summary = manager.book.stats()

    if not analyze:
        return run

    analyzed_tickers: List[str] = []

    for i, cand in enumerate(top, 1):
        _log(
            f"[{i}/{len(top)}] Market Analyst {cand.symbol} "
            f"(signals: {cand.pattern.summary()})..."
        )
        try:
            summary, report = _analyze_candidate_ma(cand, trade_date, config)
        except Exception as e:  # noqa: BLE001
            logger.warning("Market Analyst failed for %s: %s", cand.symbol, e)
            continue

        cand.report = report
        cand.ma_summary = summary
        if summary:
            cand.decision_rating = str(summary.get("proposal") or "").upper() or None

        analyzed_tickers.append(cand.symbol)
        price = float(cand.rs.close)
        live = manager.book.latest_price(cand.symbol)
        if live is not None:
            price = float(live)

        plan, skip_reason = trade_plan_from_pm_summary(
            cand.symbol, summary, price, min_confidence=min_conf
        )
        if plan is not None:
            cand.levels = {
                "stoploss": plan.stop_loss,
                "target": plan.target_1,
                "entry_zone_low": plan.zone_low,
                "entry_zone_high": plan.zone_high,
            }
            if plan.action == PlanAction.WAIT:
                cand.decision_rating = cand.decision_rating or "WAIT"
            _log(
                f"    -> MA {cand.decision_rating}: preview "
                f"{plan.action.value}/{plan.entry_type.value} "
                f"SL {plan.stop_loss} T1 {plan.target_1} "
                f"zone {plan.zone_low}–{plan.zone_high}"
            )
        else:
            _log(f"    -> MA skip preview: {skip_reason}")

    if not analyzed_tickers:
        _log("No Market Analyst reports — skipping RS Desk PM")
        try:
            from tradingagents.paper.snapshots import save_screen_snapshot

            save_screen_snapshot(config, trade_date, top, opened=[], waits=[])
        except Exception as e:  # noqa: BLE001
            logger.warning("Dashboard snapshot save failed: %s", e)
        return run

    _log(
        f"RS Desk PM on {len(analyzed_tickers)} tickers "
        f"(shared tech_reports, separate rs_desk book)..."
    )
    report = run_rs_desk_process(
        config,
        tickers=analyzed_tickers,
        process_date=trade_date,
        progress=progress,
    )

    if report.get("skipped"):
        _log(f"RS Desk process skipped: {report.get('reason')}")
        run.rs_desk_report = report
        return run

    run.opened = list(report.get("opened") or [])
    run.waits = list(report.get("waits") or [])
    raw_skips = report.get("skip_entries")
    run.skipped = raw_skips if isinstance(raw_skips, list) else []
    run.rs_desk_report = report
    run.paper_summary = TechDeskPaperTradeManager(as_tech_desk_config(config)).book.stats()

    for cand in top:
        if cand.symbol in run.opened:
            cand.decision_rating = cand.decision_rating or "BUY"
        elif cand.symbol in run.waits:
            cand.decision_rating = cand.decision_rating or "WAIT"

    _log(
        f"Done: opened {run.opened}; waits {run.waits}; "
        f"skipped {len(run.skipped)} (RS Desk book)"
    )

    try:
        from tradingagents.paper.snapshots import save_screen_snapshot

        save_screen_snapshot(
            config,
            trade_date,
            top,
            opened=run.opened,
            waits=run.waits,
        )
        _log("Saved screen results for the dashboard")
    except Exception as e:  # noqa: BLE001
        logger.warning("Dashboard snapshot save failed: %s", e)

    return run
