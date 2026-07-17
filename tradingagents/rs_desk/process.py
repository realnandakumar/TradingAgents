"""RS Desk process — same PM pipeline as Tech Desk, separate book, shared reports."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Callable, Dict, List, Optional

from tradingagents.llm_clients import create_llm_client
from tradingagents.rs_desk.candidates import resolve_rs_desk_tickers
from tradingagents.rs_desk.config_overlay import as_tech_desk_config
from tradingagents.tech_desk.agents.portfolio_manager import run_tech_desk_batch_pm
from tradingagents.tech_desk.entry_rules import promote_proximity_entries
from tradingagents.tech_desk.manager import TechDeskPaperTradeManager
from tradingagents.tech_desk.pm_validation import enforce_entry_timing
from tradingagents.tech_desk.process import _provider_kwargs, fetch_prices
from tradingagents.tech_desk.report_loader import load_tech_reports
from tradingagents.tech_desk.schemas import render_batch_decision

logger = logging.getLogger(__name__)


def run_rs_desk_process(
    config: dict,
    *,
    tickers: Optional[List[str]] = None,
    reports_dir: Optional[str] = None,
    process_date: Optional[str] = None,
    progress: Optional[Callable[[str], None]] = None,
    pm_runner=run_tech_desk_batch_pm,
) -> dict:
    """Load latest shared tech reports for RS candidates, run PM, execute on RS book.

    Reports come from ``tech_analyze_reports_dir`` (shared with Tech Desk) — whichever
    source wrote the newest report for a ticker wins.
    """

    def _log(msg: str) -> None:
        if progress:
            progress(msg)

    process_date = process_date or datetime.now().strftime("%Y-%m-%d")
    cfg = as_tech_desk_config(config)
    reports_dir = reports_dir or cfg.get("tech_analyze_reports_dir")

    candidate_tickers = tickers or resolve_rs_desk_tickers(config)
    if not candidate_tickers:
        return {
            "skipped": True,
            "reason": "no_candidates",
            "reports_dir": str(reports_dir),
            "stale_tickers": [],
        }

    _log(
        f"RS Desk: loading latest shared reports for {len(candidate_tickers)} tickers..."
    )
    max_age = cfg.get("tech_desk_max_report_age_days")
    candidates, stale_tickers = load_tech_reports(
        reports_dir,
        tickers=candidate_tickers,
        max_report_age_days=max_age,
        as_of=process_date,
    )
    if not candidates:
        return {
            "skipped": True,
            "reason": "no_reports",
            "reports_dir": str(reports_dir),
            "candidate_tickers": candidate_tickers,
            "stale_tickers": stale_tickers,
        }

    snapshots_by_ticker = {s.ticker.upper(): s for s in candidates}

    manager = TechDeskPaperTradeManager(cfg)
    open_positions = [p for p in manager.book.positions if p.get("status") == "open"]
    slots_available = max(0, manager.max_positions - len(open_positions))

    all_tickers = list(
        {c.ticker for c in candidates} | {p["ticker"] for p in open_positions}
    )
    _log(f"Fetching prices for {len(all_tickers)} tickers...")
    prices = fetch_prices(all_tickers, manager)

    _log("Running RS Desk PM on batch (same agent as Tech Desk)...")
    llm_kwargs = _provider_kwargs(cfg)
    client = create_llm_client(
        provider=cfg["llm_provider"],
        model=cfg["quick_think_llm"],
        base_url=cfg.get("backend_url"),
        **llm_kwargs,
    )
    llm = client.get_llm()

    decision, pm_error = pm_runner(
        llm,
        candidates,
        open_positions,
        slots_available,
        cfg,
        prices=prices,
        as_of=process_date,
    )

    decision = promote_proximity_entries(decision, prices, snapshots_by_ticker, cfg)
    decision = enforce_entry_timing(decision, prices, snapshots_by_ticker)

    _log("Executing RS Desk batch decision...")
    report = manager.process_batch(
        decision,
        prices,
        process_date=process_date,
        snapshots=snapshots_by_ticker,
    )
    skip_entries = list(report.get("skipped") or [])
    report["skip_entries"] = skip_entries
    report["skipped"] = False
    report["desk"] = "rs_desk"
    report["candidates"] = len(candidates)
    report["candidate_tickers"] = candidate_tickers
    report["stale_tickers"] = stale_tickers
    report["slots_available"] = slots_available
    report["decision"] = decision.model_dump()
    report["decision_markdown"] = render_batch_decision(decision, prices=prices)
    if pm_error:
        report["pm_error"] = pm_error
    return report
