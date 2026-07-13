"""Orchestrate Tech Desk batch process: load reports → PM → execute."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Callable, Dict, List, Optional

from tradingagents.analysis.watchlist import load_watchlist
from tradingagents.llm_clients import create_llm_client
from tradingagents.tech_desk.agents.portfolio_manager import run_tech_desk_batch_pm
from tradingagents.tech_desk.entry_rules import promote_proximity_entries
from tradingagents.tech_desk.manager import TechDeskPaperTradeManager
from tradingagents.tech_desk.pm_validation import enforce_entry_timing
from tradingagents.tech_desk.report_loader import load_tech_reports
from tradingagents.tech_desk.schemas import render_batch_decision

logger = logging.getLogger(__name__)


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


def run_tech_desk_process(
    config: dict,
    *,
    reports_dir: Optional[str] = None,
    process_date: Optional[str] = None,
    progress: Optional[Callable[[str], None]] = None,
    pm_runner=run_tech_desk_batch_pm,
) -> dict:
    """Load saved tech-analyze reports, run PM batch, execute trades."""
    def _log(msg: str) -> None:
        if progress:
            progress(msg)

    process_date = process_date or datetime.now().strftime("%Y-%m-%d")
    reports_dir = reports_dir or config.get("tech_analyze_reports_dir")

    watchlist = load_watchlist()
    if not watchlist:
        return {
            "skipped": True,
            "reason": "empty_watchlist",
            "reports_dir": str(reports_dir),
            "stale_tickers": [],
        }

    _log(f"Loading saved tech-analyze reports for {len(watchlist)} watchlist tickers...")
    max_age = config.get("tech_desk_max_report_age_days")
    candidates, stale_tickers = load_tech_reports(
        reports_dir,
        tickers=watchlist,
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
        }

    snapshots_by_ticker = {s.ticker.upper(): s for s in candidates}

    manager = TechDeskPaperTradeManager(config)
    open_positions = [p for p in manager.book.positions if p.get("status") == "open"]
    slots_available = max(0, manager.max_positions - len(open_positions))

    all_tickers = list({c.ticker for c in candidates} | {p["ticker"] for p in open_positions})
    _log(f"Fetching prices for {len(all_tickers)} tickers...")
    prices = fetch_prices(all_tickers, manager)

    _log("Running Tech Desk PM on batch...")
    llm_kwargs = _provider_kwargs(config)
    client = create_llm_client(
        provider=config["llm_provider"],
        model=config["quick_think_llm"],
        base_url=config.get("backend_url"),
        **llm_kwargs,
    )
    llm = client.get_llm()

    decision, pm_error = pm_runner(
        llm,
        candidates,
        open_positions,
        slots_available,
        config,
        prices=prices,
        as_of=process_date,
    )

    decision = promote_proximity_entries(decision, prices, snapshots_by_ticker, config)
    decision = enforce_entry_timing(decision, prices, snapshots_by_ticker)

    _log("Executing batch decision...")
    report = manager.process_batch(
        decision,
        prices,
        process_date=process_date,
        snapshots=snapshots_by_ticker,
    )
    report["skipped"] = False
    report["candidates"] = len(candidates)
    report["watchlist_count"] = len(watchlist)
    report["stale_tickers"] = stale_tickers
    report["slots_available"] = slots_available
    report["decision"] = decision.model_dump()
    report["decision_markdown"] = render_batch_decision(decision, prices=prices)
    if pm_error:
        report["pm_error"] = pm_error
    return report
