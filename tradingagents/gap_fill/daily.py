"""Daily Gap Fill portfolio run."""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Dict, Optional, TYPE_CHECKING

from tradingagents.screening.gap_fill_screener import screen_gap_fill
from tradingagents.swing.exits import is_nse_trading_day
from tradingagents.gap_fill.manager import GapFillPaperTradeManager, ReplacementProposal

if TYPE_CHECKING:
    import pandas as pd


def run_gap_fill_daily(
    config: dict,
    progress: Optional[Callable[[str], None]] = None,
    approve: Optional[Callable[[ReplacementProposal], bool]] = None,
    force: bool = False,
    price_data: Optional[Dict[str, "pd.DataFrame"]] = None,
) -> dict:
    def _log(msg: str):
        if progress:
            progress(msg)

    if not force and not is_nse_trading_day():
        return {"skipped": True, "reason": "not_a_trading_day"}

    _log("Running Gap Fill screener (daily 1D bars)...")
    picks = screen_gap_fill(config, progress=progress, price_data=price_data)

    manager = GapFillPaperTradeManager(config)
    screen_date = datetime.now().strftime("%Y-%m-%d")
    report = manager.run_daily(picks, screen_date=screen_date, approve=approve)
    report["skipped"] = False
    report["picks"] = [p.symbol for p in picks if p.direction == "BUY"]
    return report
