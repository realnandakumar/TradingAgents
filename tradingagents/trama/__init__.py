"""TRAMA crossover strategy package."""

from .book import STRATEGY_NAME, TramaPositionBook
from .daily import run_trama_daily
from .manager import ReplacementProposal, TramaPaperTradeManager
from tradingagents.screening.trama_engine import (
    STRATEGY_ID,
    STRATEGY_NAME as ENGINE_NAME,
    STRATEGY_VERSION,
    TramaSignal,
    evaluate_trama,
    explain_trama,
)
from tradingagents.screening.trama_screener import TramaPick, screen_trama
from tradingagents.swing.exits import ExitReason, is_nse_trading_day

__all__ = [
    "STRATEGY_ID",
    "STRATEGY_NAME",
    "STRATEGY_VERSION",
    "ENGINE_NAME",
    "TramaSignal",
    "TramaPick",
    "TramaPositionBook",
    "TramaPaperTradeManager",
    "ReplacementProposal",
    "evaluate_trama",
    "explain_trama",
    "screen_trama",
    "run_trama_daily",
    "ExitReason",
    "is_nse_trading_day",
]
