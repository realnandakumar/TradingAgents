"""Daily RS Desk run — rules-only exits and pending zone fills."""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Optional

from tradingagents.rs_desk.config_overlay import as_tech_desk_config
from tradingagents.tech_desk.manager import TechDeskPaperTradeManager


def run_rs_desk_daily(
    config: dict,
    progress: Optional[Callable[[str], None]] = None,
    force: bool = False,
) -> dict:
    def _log(msg: str) -> None:
        if progress:
            progress(msg)

    _log("RS Desk daily — exits and zone fills (no LLM)...")
    manager = TechDeskPaperTradeManager(as_tech_desk_config(config))
    as_of = datetime.now().strftime("%Y-%m-%d")
    report = manager.run_daily(as_of=as_of)
    report["skipped"] = False
    report["desk"] = "rs_desk"
    return report
