"""Rewrite paper books and daily reports with strict JSON (no Python NaN)."""
from __future__ import annotations

import json
from pathlib import Path

from tradingagents.paper.json_store import dump_json

HOME = Path.home() / ".tradingagents"
DESKS = [
    "momentum",
    "supertrend_rsi",
    "pattern_forecast",
    "trama",
    "swing",
    "nss",
    "gap_fill",
    "nw_envelope",
    "tech_desk",
    "rs_desk",
    "paper",
]


def _rewrite(path: Path) -> bool:
    if not path.exists():
        return False
    raw = path.read_text(encoding="utf-8")
    if "NaN" not in raw and "Infinity" not in raw:
        json.loads(raw)  # must already be strict
        return False
    data = json.loads(raw)
    dump_json(path, data)
    json.loads(path.read_text(encoding="utf-8"))
    print(f"rewrote {path}")
    return True


def main() -> None:
    names = (
        "positions.json",
        "pending_entries.json",
        "pending_dismissed.json",
        "pending_replacements.json",
        "closed_history.json",
        "screener.json",
        "paper_snapshot.json",
        "screens.json",
    )
    for desk in DESKS:
        root = HOME / desk
        for name in names:
            _rewrite(root / name)
        for path in sorted((root / "daily").glob("*.json")):
            _rewrite(path)
        for path in sorted((root / "process").glob("*.json")):
            _rewrite(path)
    for extra in (HOME / "candlesticks" / "screener.json", HOME / "chart_patterns" / "screener.json"):
        _rewrite(extra)


if __name__ == "__main__":
    main()
