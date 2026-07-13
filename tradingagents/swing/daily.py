"""Daily swing portfolio run (9:30 AM IST workflow)."""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Dict, Optional, TYPE_CHECKING

from tradingagents.screening.swing_screener import screen_swing
from tradingagents.swing.manager import PortfolioPaperTradeManager, ReplacementProposal

if TYPE_CHECKING:
    import pandas as pd


def run_swing_daily(
    config: dict,
    progress: Optional[Callable[[str], None]] = None,
    approve: Optional[Callable[[ReplacementProposal], bool]] = None,
    force: bool = False,
    price_data: Optional[Dict[str, "pd.DataFrame"]] = None,
) -> dict:
    def _log(msg: str):
        if progress:
            progress(msg)

    _log("Running swing screener (daily 1D bars)...")
    picks = screen_swing(config, progress=progress, price_data=price_data)

    manager = PortfolioPaperTradeManager(config)
    screen_date = datetime.now().strftime("%Y-%m-%d")
    report = manager.run_daily(picks, screen_date=screen_date, approve=approve)
    report["skipped"] = False
    report["picks"] = [p.symbol for p in picks]
    return report
