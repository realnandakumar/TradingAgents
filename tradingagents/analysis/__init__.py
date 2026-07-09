"""Programmatic analysis runner for web dashboard and automation."""

from tradingagents.analysis.report import save_report_to_disk
from tradingagents.analysis.runner import run_analysis_job

__all__ = ["save_report_to_disk", "run_analysis_job"]
