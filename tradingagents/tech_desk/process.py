"""Orchestrate Tech Desk batch process: load reports → Trader → script assemble → execute."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Callable, Dict, List, Optional

from tradingagents.analysis.watchlist import load_watchlist
from tradingagents.llm_clients import create_llm_client
from tradingagents.tech_desk.agents.trader import run_tech_desk_traders
from tradingagents.tech_desk.assemble import assemble_decision_from_traders
from tradingagents.tech_desk.entry_rules import promote_proximity_entries
from tradingagents.tech_desk.manager import TechDeskPaperTradeManager
from tradingagents.tech_desk.pm_validation import enforce_entry_timing
from tradingagents.tech_desk.report_excerpt import pm_summary_thin_reason
from tradingagents.tech_desk.report_loader import TechReportSnapshot, load_tech_reports
from tradingagents.tech_desk.schemas import SkipEntry, render_batch_decision
from tradingagents.tech_desk.trader_persist import persist_trader_reports
from tradingagents.tech_desk.universe_gate import (
    assert_pending_paths_isolated,
    filter_decision_entries_to_universe,
    ticker_in_universe,
    universe_key_set,
)

logger = logging.getLogger(__name__)


def partition_actionable_reports(
    candidates: List[TechReportSnapshot],
) -> tuple[List[TechReportSnapshot], List[dict], List[dict]]:
    """Split reports into actionable / stand-aside / thin (needs re-analyze)."""
    from tradingagents.tech_desk.report_excerpt import is_stand_aside_pm_summary

    actionable: List[TechReportSnapshot] = []
    stand_aside: List[dict] = []
    thin: List[dict] = []
    for snap in candidates:
        reason = pm_summary_thin_reason(snap.pm_summary)
        if reason is None:
            actionable.append(snap)
        elif is_stand_aside_pm_summary(snap.pm_summary):
            stand_aside.append(
                {
                    "ticker": snap.ticker,
                    "report_date": snap.report_date,
                    "reason": reason,
                }
            )
        else:
            thin.append(
                {
                    "ticker": snap.ticker,
                    "report_date": snap.report_date,
                    "reason": reason or "thin pm_summary",
                }
            )
    return actionable, stand_aside, thin


def _provider_kwargs(config: dict) -> dict:
    kwargs: dict = {}
    provider = config.get("llm_provider", "").lower()
    if provider == "google" and config.get("google_thinking_level"):
        kwargs["thinking_level"] = config["google_thinking_level"]
    elif provider == "openai" and config.get("openai_reasoning_effort"):
        kwargs["reasoning_effort"] = config["openai_reasoning_effort"]
    elif provider == "anthropic" and config.get("anthropic_effort"):
        kwargs["effort"] = config["anthropic_effort"]
    return kwargs


def fetch_prices(tickers: List[str], book: TechDeskPaperTradeManager) -> Dict[str, float]:
    prices: Dict[str, float] = {}
    for ticker in tickers:
        price = book.book.latest_price(ticker)
        if price is not None:
            prices[ticker] = price
    return prices


def _extra_skips_from_gates(
    thin_reports: List[dict],
    stand_aside_reports: List[dict],
) -> List[SkipEntry]:
    skips: List[SkipEntry] = []
    for thin in thin_reports:
        skips.append(
            SkipEntry(
                ticker=thin["ticker"],
                reason=f"thin pm_summary: {thin['reason']} — re-run tech-analyze",
            )
        )
    for aside in stand_aside_reports:
        skips.append(SkipEntry(ticker=aside["ticker"], reason=aside["reason"]))
    return skips


def run_tech_desk_process(
    config: dict,
    *,
    reports_dir: Optional[str] = None,
    process_date: Optional[str] = None,
    progress: Optional[Callable[[str], None]] = None,
) -> dict:
    """Load reports → Path-5 Trader → script assemble → execute.

    New opens/waits are restricted to the **current watchlist**. Open positions
    are not closed here (weekly position review). Pending is Tech Desk only.

    Daily LLM Portfolio Manager is removed — assemble is deterministic ranking
    and slot fill. Replacement / rotation can be added later as rules.
    """

    def _log(msg: str) -> None:
        if progress:
            progress(msg)

    process_date = process_date or datetime.now().strftime("%Y-%m-%d")
    reports_dir = reports_dir or config.get("tech_analyze_reports_dir")

    assert_pending_paths_isolated(
        config.get("tech_desk_pending_path"),
        config.get("rs_desk_pending_path"),
    )

    watchlist = load_watchlist()
    manager = TechDeskPaperTradeManager(config)
    open_positions = [p for p in manager.book.positions if p.get("status") == "open"]

    report_tickers = list(
        dict.fromkeys([*(watchlist or []), *[p["ticker"] for p in open_positions]])
    )
    if not report_tickers:
        return {
            "skipped": True,
            "reason": "empty_watchlist",
            "reports_dir": str(reports_dir),
            "stale_tickers": [],
            "pending_path": str(manager.book.pending_path),
        }

    _log(
        f"Loading latest shared tech reports for {len(report_tickers)} tickers "
        f"(watchlist + open; new entries gated to watchlist)..."
    )
    max_age = config.get("tech_desk_max_report_age_days")
    candidates, stale_tickers = load_tech_reports(
        reports_dir,
        tickers=report_tickers,
        max_report_age_days=max_age,
        as_of=process_date,
    )
    if not candidates:
        return {
            "skipped": True,
            "reason": "no_reports",
            "reports_dir": str(reports_dir),
            "watchlist_count": len(watchlist),
            "stale_tickers": stale_tickers,
            "pending_path": str(manager.book.pending_path),
        }

    wl_universe = universe_key_set(watchlist or [])
    wl_candidates = [c for c in candidates if ticker_in_universe(c.ticker, wl_universe)]
    entry_candidates, stand_aside_reports, thin_reports = partition_actionable_reports(
        wl_candidates
    )
    if thin_reports:
        _log(
            f"Skipping {len(thin_reports)} thin report(s) (need re-analyze): "
            + ", ".join(f"{t['ticker']} ({t['reason']})" for t in thin_reports)
        )
    if stand_aside_reports:
        _log(
            f"Stand-aside {len(stand_aside_reports)} (no long setup): "
            + ", ".join(f"{t['ticker']} ({t['reason']})" for t in stand_aside_reports)
        )
    snapshots_by_ticker = {s.ticker.upper(): s for s in candidates}

    if not entry_candidates and not open_positions:
        return {
            "skipped": True,
            "reason": "no_actionable_reports",
            "reports_dir": str(reports_dir),
            "watchlist_count": len(watchlist or []),
            "stale_tickers": stale_tickers,
            "thin_reports": thin_reports,
            "stand_aside_reports": stand_aside_reports,
            "pending_path": str(manager.book.pending_path),
        }

    slots_available = max(0, manager.max_positions - len(open_positions))

    all_tickers = list({c.ticker for c in candidates} | {p["ticker"] for p in open_positions})
    _log(f"Fetching prices for {len(all_tickers)} tickers...")
    prices = fetch_prices(all_tickers, manager)

    trader_plans = []
    trader_skips: List[SkipEntry] = []

    if entry_candidates:
        _log(
            f"Path 5: Tech Desk Trader on {len(entry_candidates)} MA reports "
            f"(min R:R {config.get('tech_desk_min_rr', 1.5)}; "
            f"script assemble — no daily LLM PM)..."
        )
        llm_kwargs = _provider_kwargs(config)
        client = create_llm_client(
            provider=config["llm_provider"],
            model=config["quick_think_llm"],
            base_url=config.get("backend_url"),
            **llm_kwargs,
        )
        llm = client.get_llm()
        trader_plans, trader_skips = run_tech_desk_traders(
            llm,
            entry_candidates,
            prices,
            config,
            progress=_log,
        )
        _log(
            f"Trader done: {len(trader_plans)} plan(s), {len(trader_skips)} skip(s). "
            f"Assembling decision (script PM)..."
        )
    else:
        _log("No actionable entry candidates — script assemble only (no closes).")

    decision = assemble_decision_from_traders(
        trader_plans,
        trader_skips,
        slots_available=slots_available,
        extra_skips=_extra_skips_from_gates(thin_reports, stand_aside_reports),
    )

    saved_traders = persist_trader_reports(
        snapshots_by_ticker=snapshots_by_ticker,
        plans=trader_plans,
        skips=list(trader_skips)
        + _extra_skips_from_gates(thin_reports, stand_aside_reports),
        process_date=process_date,
    )
    if saved_traders:
        _log(f"Saved trader.json for {len(saved_traders)} ticker(s)")

    decision = promote_proximity_entries(decision, prices, snapshots_by_ticker, config)
    decision = enforce_entry_timing(decision, prices, snapshots_by_ticker)
    decision = filter_decision_entries_to_universe(
        decision,
        watchlist or [],
        reason="not on current Tech Desk watchlist",
    )

    _log("Executing batch decision...")
    report = manager.process_batch(
        decision,
        prices,
        process_date=process_date,
        snapshots=snapshots_by_ticker,
    )
    skip_entries = list(report.get("skipped") or [])
    report["skip_entries"] = skip_entries
    report["skipped"] = False
    report["candidates"] = len(entry_candidates)
    report["trader_plans"] = len(trader_plans)
    report["trader_skips"] = [s.model_dump() for s in trader_skips]
    report["thin_reports"] = thin_reports
    report["stand_aside_reports"] = stand_aside_reports
    report["assemble"] = "script"
    report["trader_reports_saved"] = saved_traders
    report["watchlist_count"] = len(watchlist or [])
    report["watchlist"] = list(watchlist or [])
    report["stale_tickers"] = stale_tickers
    report["slots_available"] = slots_available
    report["decision"] = decision.model_dump()
    report["decision_markdown"] = render_batch_decision(decision, prices=prices)
    report["pending_path"] = str(manager.book.pending_path)
    report["book_path"] = str(manager.book.path)
    # Enrich on-disk process log (manager wrote a thinner copy before decision attached)
    try:
        import json as _json

        log_path = manager.process_log_dir / f"{process_date}.json"
        log_path.write_text(_json.dumps(report, indent=2, default=str), encoding="utf-8")
    except OSError:
        pass
    return report
