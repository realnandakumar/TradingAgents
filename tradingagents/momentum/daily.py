"""Daily momentum portfolio run."""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Dict, Optional, TYPE_CHECKING

from tradingagents.screening.momentum_screener import screen_momentum
from tradingagents.swing.exits import is_nse_trading_day
from tradingagents.momentum.manager import MomentumPaperTradeManager, ReplacementProposal

if TYPE_CHECKING:
    import pandas as pd


def run_momentum_daily(
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

    _log("Running momentum screener (daily 1D bars)...")
    picks = screen_momentum(config, progress=progress, price_data=price_data)

    manager = MomentumPaperTradeManager(config)
    screen_date = datetime.now().strftime("%Y-%m-%d")
    report = manager.run_daily(picks, screen_date=screen_date, approve=approve)
    report["skipped"] = False
    report["picks"] = [p.symbol for p in picks]
    return report
