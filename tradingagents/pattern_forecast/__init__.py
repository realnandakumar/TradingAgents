"""Pattern Forecast strategy package."""

from .book import STRATEGY_NAME, PatternForecastPositionBook
from .daily import run_pattern_forecast_daily
from .exits import ExitReason
from .manager import PatternForecastPaperTradeManager, ReplacementProposal
from tradingagents.screening.pattern_forecast_engine import (
    STRATEGY_ID,
    STRATEGY_NAME as ENGINE_NAME,
    STRATEGY_VERSION,
    PatternForecastSignal,
    evaluate_pattern_forecast,
    explain_pattern_forecast,
)
from tradingagents.screening.pattern_forecast_screener import PatternForecastPick, screen_pattern_forecast
from tradingagents.swing.exits import is_nse_trading_day

__all__ = [
    "STRATEGY_ID",
    "STRATEGY_NAME",
    "STRATEGY_VERSION",
    "ENGINE_NAME",
    "PatternForecastSignal",
    "PatternForecastPick",
    "PatternForecastPositionBook",
    "PatternForecastPaperTradeManager",
    "ReplacementProposal",
    "evaluate_pattern_forecast",
    "explain_pattern_forecast",
    "screen_pattern_forecast",
    "run_pattern_forecast_daily",
    "ExitReason",
    "is_nse_trading_day",
]
