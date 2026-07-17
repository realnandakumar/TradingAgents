"""RS Desk — RS+pattern screen → Market Analyst → Tech-Desk-style PM, own book.

Shares ``tech_analyze_reports_dir`` with Tech Desk (latest report per ticker wins).
Capital book / pending / daily / process logs live under ``~/.tradingagents/rs_desk/``.
"""

from .config_overlay import as_tech_desk_config
from .daily import run_rs_desk_daily
from .process import run_rs_desk_process

STRATEGY_NAME = "rs_desk"

__all__ = [
    "STRATEGY_NAME",
    "as_tech_desk_config",
    "run_rs_desk_process",
    "run_rs_desk_daily",
]
