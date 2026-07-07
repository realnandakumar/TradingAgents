"""Daily SuperTrend+RSI portfolio run."""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Optional

from tradingagents.screening.supertrend_rsi_screener import screen_supertrend_rsi
from tradingagents.swing.exits import is_nse_trading_day
from tradingagents.supertrend_rsi.manager import ReplacementProposal, SuperTrendRSIPaperTradeManager


def run_supertrend_rsi_daily(
    config: dict,
    progress: Optional[Callable[[str], None]] = None,
    approve: Optional[Callable[[ReplacementProposal], bool]] = None,
    force: bool = False,
) -> dict:
    def _log(msg: str):
        if progress:
            progress(msg)

    if not force and not is_nse_trading_day():
        return {"skipped": True, "reason": "not_a_trading_day"}

    _log("Running SuperTrend+RSI screener (daily 1D bars)...")
    picks = screen_supertrend_rsi(config, progress=progress)

    manager = SuperTrendRSIPaperTradeManager(config)
    screen_date = datetime.now().strftime("%Y-%m-%d")
    report = manager.run_daily(picks, screen_date=screen_date, approve=approve)
    report["skipped"] = False
    report["picks"] = [p.symbol for p in picks if p.direction == "BUY"]
    return report
