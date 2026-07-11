"""Tech Desk paper trading — batch PM over saved tech-analyze reports."""

from .book import STRATEGY_NAME, TechDeskPositionBook
from .daily import run_tech_desk_daily
from .exits import ExitReason, zone_fill_price
from .manager import TechDeskPaperTradeManager
from .process import run_tech_desk_process
from .report_loader import TechReportSnapshot, load_tech_reports
from .schemas import TechDeskBatchDecision, TechDeskPositionReview, TechTradePlan

__all__ = [
    "STRATEGY_NAME",
    "TechDeskPositionBook",
    "TechDeskPaperTradeManager",
    "TechDeskBatchDecision",
    "TechDeskPositionReview",
    "TechTradePlan",
    "TechReportSnapshot",
    "ExitReason",
    "load_tech_reports",
    "run_tech_desk_process",
    "run_tech_desk_daily",
    "zone_fill_price",
]
