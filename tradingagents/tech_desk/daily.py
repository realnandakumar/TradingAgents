"""Daily Tech Desk run — rules-only exits and pending zone fills."""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Optional

from tradingagents.swing.exits import is_nse_trading_day
from tradingagents.tech_desk.manager import TechDeskPaperTradeManager


def run_tech_desk_daily(
    config: dict,
    progress: Optional[Callable[[str], None]] = None,
    force: bool = False,
) -> dict:
    def _log(msg: str) -> None:
        if progress:
            progress(msg)

    if not force and not is_nse_trading_day():
        return {"skipped": True, "reason": "not_a_trading_day"}

    _log("Tech Desk daily — exits and zone fills (no LLM)...")
    manager = TechDeskPaperTradeManager(config)
    as_of = datetime.now().strftime("%Y-%m-%d")
    report = manager.run_daily(as_of=as_of)
    report["skipped"] = False
    return report
