"""SuperTrend + RSI strategy package."""

from .book import STRATEGY_NAME, SuperTrendRSIPositionBook
from .daily import run_supertrend_rsi_daily
from .manager import ReplacementProposal, SuperTrendRSIPaperTradeManager
from tradingagents.screening.supertrend_rsi_engine import (
    STRATEGY_ID,
    STRATEGY_VERSION,
    SuperTrendRSISignal,
    evaluate_supertrend_rsi,
)
from tradingagents.screening.supertrend_rsi_screener import (
    SuperTrendRSIPick,
    explain_supertrend_rsi,
    screen_supertrend_rsi,
)
from tradingagents.swing.exits import ExitReason, is_nse_trading_day

__all__ = [
    "STRATEGY_ID",
    "STRATEGY_NAME",
    "STRATEGY_VERSION",
    "SuperTrendRSISignal",
    "SuperTrendRSIPick",
    "SuperTrendRSIPositionBook",
    "SuperTrendRSIPaperTradeManager",
    "ReplacementProposal",
    "evaluate_supertrend_rsi",
    "screen_supertrend_rsi",
    "explain_supertrend_rsi",
    "run_supertrend_rsi_daily",
    "ExitReason",
    "is_nse_trading_day",
]
