"""Programmatic analysis runner for web dashboard and automation."""

from tradingagents.analysis.report import save_report_to_disk
from tradingagents.analysis.runner import run_analysis_job
from tradingagents.analysis.tech_analyze import (
    run_tech_analyze,
    run_tech_analyze_batch,
    save_tech_report,
)
from tradingagents.analysis.watchlist import (
    add_to_watchlist,
    list_watchlist,
    load_watchlist,
    remove_from_watchlist,
    save_watchlist,
)

__all__ = [
    "save_report_to_disk",
    "run_analysis_job",
    "run_tech_analyze",
    "run_tech_analyze_batch",
    "save_tech_report",
    "load_watchlist",
    "save_watchlist",
    "add_to_watchlist",
    "remove_from_watchlist",
    "list_watchlist",
]
