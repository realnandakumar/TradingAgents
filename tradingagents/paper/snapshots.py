"""Offline (local JSON) persistence of screen + paper snapshots for the dashboard.

This is the local-file replacement for the old Supabase publisher. The screening
funnel and paper book are unchanged; only the sink differs. Two files under
``~/.tradingagents/paper/`` are written atomically:

- ``paper_snapshot.json`` — latest paper book snapshot (capital, positions, stats)
- ``screens.json``        — recent screen runs, newest first (capped)

Each entry mirrors the old Supabase row shape (``id`` / ``created_at`` / ``data``)
so the dashboard types stay identical.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from tradingagents.sync.supabase_sync import paper_snapshot, screen_snapshot

logger = logging.getLogger(__name__)

_DEFAULT_HOME = os.path.join(os.path.expanduser("~"), ".tradingagents")


def _paper_snapshot_path(config: dict) -> Path:
    path = config.get("paper_snapshot_path") or os.getenv(
        "TRADINGAGENTS_PAPER_SNAPSHOT_PATH",
        os.path.join(_DEFAULT_HOME, "paper", "paper_snapshot.json"),
    )
    return Path(path).expanduser()


def _screens_path(config: dict) -> Path:
    path = config.get("paper_screens_path") or os.getenv(
        "TRADINGAGENTS_PAPER_SCREENS_PATH",
        os.path.join(_DEFAULT_HOME, "paper", "screens.json"),
    )
    return Path(path).expanduser()


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


def _row(data: dict) -> dict:
    now = datetime.now()
    return {
        "id": int(now.timestamp() * 1000),
        "created_at": now.isoformat(timespec="seconds"),
        "data": data,
    }


def save_paper_snapshot(config: dict, book) -> Path:
    """Write the latest paper book snapshot to the local snapshot file."""
    path = _paper_snapshot_path(config)
    _write_json(path, _row(paper_snapshot(book)))
    return path


def save_screen_snapshot(
    config: dict,
    trade_date: str,
    candidates: List,
    opened: Optional[List[str]] = None,
    waits: Optional[List[str]] = None,
) -> Path:
    """Prepend a screen run to the local history file (newest first, capped)."""
    path = _screens_path(config)
    history: list = []
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                history = loaded
        except Exception as e:  # noqa: BLE001
            logger.warning("Could not read screens history (%s); starting fresh", e)

    history.insert(0, _row(screen_snapshot(trade_date, candidates, opened, waits=waits)))
    limit = int(config.get("paper_screens_history", 30))
    history = history[:limit]
    _write_json(path, history)
    return path


def save_results(
    config: dict,
    trade_date: str,
    candidates: List,
    opened: Optional[List[str]],
    book,
    waits: Optional[List[str]] = None,
) -> None:
    """Persist both a screen snapshot and a paper snapshot locally."""
    save_screen_snapshot(config, trade_date, candidates, opened, waits=waits)
    save_paper_snapshot(config, book)
