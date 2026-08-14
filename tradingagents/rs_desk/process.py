"""RS Desk process — Path 5 Trader + script assemble; separate book, shared reports."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Callable, Dict, List, Optional

from tradingagents.llm_clients import create_llm_client
from tradingagents.rs_desk.candidates import resolve_rs_desk_tickers
from tradingagents.rs_desk.config_overlay import _DEFAULT_HOME, as_tech_desk_config
from tradingagents.tech_desk.agents.trader import run_tech_desk_traders
from tradingagents.tech_desk.assemble import assemble_decision_from_traders
from tradingagents.tech_desk.entry_rules import promote_proximity_entries
from tradingagents.tech_desk.manager import TechDeskPaperTradeManager
from tradingagents.tech_desk.pm_validation import enforce_entry_timing
from tradingagents.tech_desk.process import (
    _extra_skips_from_gates,
    _provider_kwargs,
    fetch_prices,
    partition_actionable_reports,
)
from tradingagents.tech_desk.report_loader import load_tech_reports
from tradingagents.tech_desk.schemas import SkipEntry, render_batch_decision
from tradingagents.tech_desk.trader_persist import persist_trader_reports
from tradingagents.tech_desk.universe_gate import (
    assert_pending_paths_isolated,
    filter_decision_entries_to_universe,
)

logger = logging.getLogger(__name__)


def run_rs_desk_process(
    config: dict,
    *,
    tickers: Optional[List[str]] = None,
    reports_dir: Optional[str] = None,
    process_date: Optional[str] = None,
    progress: Optional[Callable[[str], None]] = None,
) -> dict:
    """Load shared tech reports → Trader → script assemble → execute on RS book.

    Daily LLM PM removed (same as Tech Desk). Weekly review stays separate.
    """

    def _log(msg: str) -> None:
        if progress:
            progress(msg)

    process_date = process_date or datetime.now().strftime("%Y-%m-%d")
    cfg = as_tech_desk_config(config)
    reports_dir = reports_dir or cfg.get("tech_analyze_reports_dir")

    tech_pending_default = os.path.join(_DEFAULT_HOME, "tech_desk", "pending_entries.json")
    assert_pending_paths_isolated(
        config.get("tech_desk_pending_path") or tech_pending_default,
        cfg.get("tech_desk_pending_path"),
    )

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
    entry_candidates, stand_aside_reports, thin_reports = partition_actionable_reports(
        candidates
    )
    if thin_reports:
        _log(
            f"RS Desk: skipping {len(thin_reports)} thin report(s): "
            + ", ".join(f"{t['ticker']} ({t['reason']})" for t in thin_reports)
        )
    if stand_aside_reports:
        _log(
            f"RS Desk: stand-aside {len(stand_aside_reports)}: "
            + ", ".join(f"{t['ticker']} ({t['reason']})" for t in stand_aside_reports)
        )

    manager = TechDeskPaperTradeManager(cfg)
    open_positions = [p for p in manager.book.positions if p.get("status") == "open"]

    if not entry_candidates and not open_positions:
        return {
            "skipped": True,
            "reason": "no_actionable_reports",
            "reports_dir": str(reports_dir),
            "candidate_tickers": candidate_tickers,
            "stale_tickers": stale_tickers,
            "thin_reports": thin_reports,
            "stand_aside_reports": stand_aside_reports,
        }

    slots_available = max(0, manager.max_positions - len(open_positions))

    all_tickers = list(
        {c.ticker for c in candidates} | {p["ticker"] for p in open_positions}
    )
    _log(f"Fetching prices for {len(all_tickers)} tickers...")
    prices = fetch_prices(all_tickers, manager)

    trader_plans = []
    trader_skips: List[SkipEntry] = []

    if entry_candidates:
        min_rr = cfg.get(
            "tech_desk_min_rr",
            config.get("rs_desk_min_rr", config.get("tech_desk_min_rr", 1.5)),
        )
        cfg["tech_desk_min_rr"] = min_rr
        _log(
            f"RS Desk Path 5: Trader on {len(entry_candidates)} reports "
            f"(min R:R {min_rr}; script assemble — no daily LLM PM)..."
        )
        llm_kwargs = _provider_kwargs(cfg)
        client = create_llm_client(
            provider=cfg["llm_provider"],
            model=cfg["quick_think_llm"],
            base_url=cfg.get("backend_url"),
            **llm_kwargs,
        )
        llm = client.get_llm()
        trader_plans, trader_skips = run_tech_desk_traders(
            llm,
            entry_candidates,
            prices,
            cfg,
            progress=_log,
        )
        _log(
            f"RS Trader done: {len(trader_plans)} plan(s), {len(trader_skips)} skip(s). "
            f"Assembling..."
        )
    else:
        _log("RS Desk: no actionable entries — script assemble only.")

    decision = assemble_decision_from_traders(
        trader_plans,
        trader_skips,
        slots_available=slots_available,
        extra_skips=_extra_skips_from_gates(thin_reports, stand_aside_reports),
    )

    saved_traders = persist_trader_reports(
        snapshots_by_ticker=snapshots_by_ticker,
        plans=trader_plans,
        skips=trader_skips
        + _extra_skips_from_gates(thin_reports, stand_aside_reports),
        process_date=process_date,
    )
    if saved_traders:
        _log(f"RS Desk: saved trader.json for {len(saved_traders)} ticker(s)")

    decision = promote_proximity_entries(decision, prices, snapshots_by_ticker, cfg)
    decision = enforce_entry_timing(decision, prices, snapshots_by_ticker)
    decision = filter_decision_entries_to_universe(
        decision,
        candidate_tickers,
        reason="not in current RS Desk candidate set",
    )

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
    report["candidates"] = len(entry_candidates)
    report["trader_plans"] = len(trader_plans)
    report["trader_skips"] = [s.model_dump() for s in trader_skips]
    report["thin_reports"] = thin_reports
    report["stand_aside_reports"] = stand_aside_reports
    report["assemble"] = "script"
    report["trader_reports_saved"] = saved_traders
    report["candidate_tickers"] = candidate_tickers
    report["stale_tickers"] = stale_tickers
    report["slots_available"] = slots_available
    report["decision"] = decision.model_dump()
    report["decision_markdown"] = render_batch_decision(decision, prices=prices)
    report["pending_path"] = str(manager.book.pending_path)
    report["book_path"] = str(manager.book.path)
    # Enrich on-disk process log (manager wrote a thinner copy before decision attached)
    try:
        from tradingagents.paper.json_store import dump_json

        log_path = manager.process_log_dir / f"{process_date}.json"
        dump_json(log_path, report, default=str)
    except OSError:
        pass
    return report
