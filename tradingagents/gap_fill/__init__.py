"""Gap Fill strategy package."""

from .book import STRATEGY_NAME, GapFillPositionBook
from .daily import run_gap_fill_daily
from .manager import GapFillPaperTradeManager, ReplacementProposal
from tradingagents.screening.gap_fill_engine import (
    STRATEGY_ID,
    STRATEGY_NAME as ENGINE_NAME,
    STRATEGY_VERSION,
    GapFillSignal,
    evaluate_gap_fill,
    explain_gap_fill,
    pick_passes_long_entry,
)
from tradingagents.screening.gap_fill_screener import GapFillPick, screen_gap_fill
from tradingagents.swing.exits import ExitReason, is_nse_trading_day

__all__ = [
    "STRATEGY_ID",
    "STRATEGY_NAME",
    "STRATEGY_VERSION",
    "ENGINE_NAME",
    "GapFillSignal",
    "GapFillPick",
    "GapFillPositionBook",
    "GapFillPaperTradeManager",
    "ReplacementProposal",
    "evaluate_gap_fill",
    "explain_gap_fill",
    "pick_passes_long_entry",
    "screen_gap_fill",
    "run_gap_fill_daily",
    "ExitReason",
    "is_nse_trading_day",
]
