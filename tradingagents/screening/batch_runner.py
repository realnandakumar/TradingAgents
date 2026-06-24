"""Screening funnel: universe -> relative strength -> pattern engine -> rank,
then (optionally) deep AI analysis + paper trades on the top names.

Two entry points:
- :func:`screen_candidates` -- free/fast: returns ranked candidates with their
  RS and which technical signals fired. No LLM calls. Use it to preview picks.
- :func:`run_screen` -- the full pipeline: takes the top-N candidates, runs the
  TradingAgents analysis on each (India mode), records bullish calls in the
  paper book, and marks the book to market.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, List, Optional

from .levels import compute_levels
from .patterns import PatternScore, score_patterns
from .prices import download_history
from .relative_strength import RSResult, compute_relative_strength
from .universe import load_universe

logger = logging.getLogger(__name__)

# Ratings that trigger a simulated buy in the paper book.
BULLISH_RATINGS = {"Buy", "Overweight"}


@dataclass
class Candidate:
    symbol: str
    rs: RSResult
    pattern: PatternScore
    composite: float                 # ranking score: pattern weight + RS bonus
    levels: Optional[dict] = None    # entry / stoploss / target (ATR-based)
    # Filled by run_screen after AI analysis:
    decision_rating: Optional[str] = None
    report: Optional[str] = None

    @property
    def fired_signals(self) -> List[str]:
        return self.pattern.fired


def screen_candidates(config: dict, progress: Optional[Callable[[str], None]] = None) -> List[Candidate]:
    """Run the free part of the funnel and return ranked candidates.

    Ranking gate: keep names at/above ``screen_rs_min_percentile`` relative
    strength, then sort by a composite = pattern score + (RS percentile / 100).
    Patterns drive the ranking; relative strength breaks ties and rewards the
    strongest names.
    """
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
        candidates.append(
            Candidate(symbol=r.symbol, rs=r, pattern=ps, composite=composite, levels=levels)
        )

    candidates.sort(key=lambda c: c.composite, reverse=True)
    return candidates


@dataclass
class ScreenRun:
    trade_date: str
    candidates: List[Candidate]          # the top-N that were analyzed
    paper_summary: Dict = field(default_factory=dict)
    opened: List[str] = field(default_factory=list)


def run_screen(
    config: dict,
    trade_date: Optional[str] = None,
    progress: Optional[Callable[[str], None]] = None,
    analyze: bool = True,
) -> ScreenRun:
    """Full funnel: screen -> analyze top-N -> paper-trade bullish calls.

    Set ``analyze=False`` to stop after screening (no LLM calls) -- handy for
    a dry-run preview. ``trade_date`` defaults to today (YYYY-MM-DD).
    """
    from tradingagents.paper.book import PaperBook  # local import: cheap preview path

    def _log(msg: str):
        if progress:
            progress(msg)

    trade_date = trade_date or datetime.now().strftime("%Y-%m-%d")
    top_n = int(config.get("screen_top_n", 10))

    all_candidates = screen_candidates(config, progress=progress)
    top = all_candidates[:top_n]
    _log(f"Selected top {len(top)} of {len(all_candidates)} candidates for analysis")

    book = PaperBook(config)
    run = ScreenRun(trade_date=trade_date, candidates=top)

    # Always mark existing positions to market / close matured ones.
    run.paper_summary = book.mark_to_market()

    if not analyze:
        return run

    # India mode for the analysis pipeline.
    ta_config = dict(config)
    ta_config["reddit_market"] = "india"
    ta_config["stocktwits_market"] = "india"

    from tradingagents.graph.trading_graph import TradingAgentsGraph

    ta = TradingAgentsGraph(config=ta_config)

    for i, cand in enumerate(top, 1):
        _log(f"[{i}/{len(top)}] Analyzing {cand.symbol} (signals: {cand.pattern.summary()})...")
        try:
            _state, rating = ta.propagate(cand.symbol, trade_date, asset_type="stock")
        except Exception as e:  # noqa: BLE001 - one bad ticker shouldn't sink the run
            logger.warning("Analysis failed for %s: %s", cand.symbol, e)
            continue
        cand.decision_rating = rating

        if rating in BULLISH_RATINGS:
            pos = book.open_position(
                ticker=cand.symbol,
                rating=rating,
                entry_price=cand.rs.close,
                entry_date=trade_date,
                signals=cand.fired_signals,
                levels=cand.levels,
            )
            if pos is not None:
                run.opened.append(cand.symbol)
                _log(f"    -> {rating}: opened paper position in {cand.symbol}")

    # Refresh summary after opening new positions.
    run.paper_summary = book.mark_to_market()

    # Publish results to Supabase for the dashboard (best-effort, no-op without creds).
    try:
        from tradingagents.sync import sync_results

        if sync_results(config, trade_date, top, run.opened, book):
            _log("Synced results to dashboard")
    except Exception as e:  # noqa: BLE001 - sync must never break a run
        logger.warning("Dashboard sync failed: %s", e)

    return run
