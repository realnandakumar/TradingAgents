"""Daily NSS portfolio run."""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Dict, Optional, TYPE_CHECKING

from tradingagents.screening.nss_screener import screen_nss
from tradingagents.nss.manager import NSSPaperTradeManager, ReplacementProposal

if TYPE_CHECKING:
    import pandas as pd


def run_nss_daily(
    config: dict,
    progress: Optional[Callable[[str], None]] = None,
    approve: Optional[Callable[[ReplacementProposal], bool]] = None,
    force: bool = False,
    price_data: Optional[Dict[str, "pd.DataFrame"]] = None,
) -> dict:
    def _log(msg: str):
        if progress:
            progress(msg)

    _log("Running NSS screener (daily 1D bars)...")
    picks = screen_nss(config, progress=progress, price_data=price_data)

    manager = NSSPaperTradeManager(config)
    screen_date = datetime.now().strftime("%Y-%m-%d")
    report = manager.run_daily(picks, screen_date=screen_date, approve=approve)
    report["skipped"] = False
    report["picks"] = [p.symbol for p in picks]
    return report
