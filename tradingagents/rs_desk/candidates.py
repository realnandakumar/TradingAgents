"""Resolve which tickers the RS Desk PM should process."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import List, Optional, Set

from tradingagents.rs_desk.config_overlay import as_tech_desk_config
from tradingagents.tech_desk.manager import TechDeskPaperTradeManager

logger = logging.getLogger(__name__)


def _screens_path(config: dict) -> Path:
    home = os.path.join(os.path.expanduser("~"), ".tradingagents")
    path = config.get("paper_screens_path") or os.getenv(
        "TRADINGAGENTS_PAPER_SCREENS_PATH",
        os.path.join(home, "paper", "screens.json"),
    )
    return Path(path).expanduser()


def last_screen_tickers(config: dict, *, limit: Optional[int] = None) -> List[str]:
    """Tickers from the newest screen snapshot (top-N shortlist)."""
    path = _screens_path(config)
    if not path.exists():
        return []
    try:
        history = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        logger.warning("Could not read screens history (%s)", e)
        return []
    if not isinstance(history, list) or not history:
        return []
    data = history[0].get("data") or {}
    candidates = data.get("candidates") or []
    symbols = [c.get("symbol") for c in candidates if c.get("symbol")]
    top_n = limit if limit is not None else int(config.get("screen_top_n", 10))
    return symbols[:top_n]


def resolve_rs_desk_tickers(
    config: dict,
    *,
    extra: Optional[List[str]] = None,
) -> List[str]:
    """Union of ``extra``, last screen shortlist, and open/pending RS book."""
    cfg = as_tech_desk_config(config)
    manager = TechDeskPaperTradeManager(cfg)

    ordered: List[str] = []
    seen: Set[str] = set()

    def _add(ticker: str) -> None:
        if not ticker:
            return
        key = ticker.upper()
        if key in seen:
            return
        seen.add(key)
        ordered.append(ticker)

    for t in extra or []:
        _add(t)
    for t in last_screen_tickers(config):
        _add(t)
    for p in manager.book.positions:
        if p.get("status") == "open" and p.get("ticker"):
            _add(p["ticker"])
    for row in manager.book._load_pending():  # noqa: SLF001
        if row.get("ticker"):
            _add(row["ticker"])

    return ordered
