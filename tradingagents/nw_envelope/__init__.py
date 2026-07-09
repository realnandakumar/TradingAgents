"""NW Envelope strategy package."""

from .book import STRATEGY_NAME, NwEnvelopePositionBook
from .daily import run_nw_envelope_daily
from .manager import ReplacementProposal, NwEnvelopePaperTradeManager
from tradingagents.screening.nw_envelope_engine import (
    STRATEGY_ID,
    STRATEGY_NAME as ENGINE_NAME,
    STRATEGY_VERSION,
    NwEnvelopeSignal,
    evaluate_nw_envelope,
    explain_nw_envelope,
)
from tradingagents.screening.nw_envelope_screener import NwEnvelopePick, screen_nw_envelope
from tradingagents.swing.exits import ExitReason, is_nse_trading_day

__all__ = [
    "STRATEGY_ID",
    "STRATEGY_NAME",
    "STRATEGY_VERSION",
    "ENGINE_NAME",
    "NwEnvelopeSignal",
    "NwEnvelopePick",
    "NwEnvelopePositionBook",
    "NwEnvelopePaperTradeManager",
    "ReplacementProposal",
    "evaluate_nw_envelope",
    "explain_nw_envelope",
    "screen_nw_envelope",
    "run_nw_envelope_daily",
    "ExitReason",
    "is_nse_trading_day",
]
