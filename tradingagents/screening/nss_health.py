"""NSS market health metrics — daily funnel statistics with historical persistence."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

_DEFAULT_HOME = os.path.join(os.path.expanduser("~"), ".tradingagents")


@dataclass
class MarketHealthSnapshot:
    date: str
    universe_size: int
    trend_stocks: int
    consolidating_stocks: int
    breakout_candidates: int
    volume_confirmed: int
    final_picks: int
    scanned_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def health_history_path(config: dict) -> Path:
    raw = config.get("nss_health_history_path") or os.path.join(
        _DEFAULT_HOME, "nss", "health_history.json"
    )
    return Path(raw).expanduser()


def compute_health_from_diagnostics(diagnostics: list, universe_size: int) -> MarketHealthSnapshot:
    """Derive market health counts from a diagnostics run."""
    trend_n = consol_n = breakout_n = vol_n = 0
    for d in diagnostics:
        gp = getattr(d, "granular_passed", {}) or {}
        if gp.get("trend"):
            trend_n += 1
        if gp.get("consolidation"):
            consol_n += 1
        if gp.get("breakout_price"):
            breakout_n += 1
        if gp.get("volume_expansion"):
            vol_n += 1

    return MarketHealthSnapshot(
        date=datetime.now().strftime("%Y-%m-%d"),
        universe_size=universe_size,
        trend_stocks=trend_n,
        consolidating_stocks=consol_n,
        breakout_candidates=breakout_n,
        volume_confirmed=vol_n,
        final_picks=sum(1 for d in diagnostics if d.status == "picked"),
        scanned_at=datetime.now().isoformat(timespec="seconds"),
    )


def persist_health(snapshot: MarketHealthSnapshot, config: dict) -> Path:
    path = health_history_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)

    history: List[dict] = []
    if path.exists():
        try:
            history = json.loads(path.read_text(encoding="utf-8")).get("records", [])
        except Exception:  # noqa: BLE001
            history = []

    history = [h for h in history if h.get("date") != snapshot.date]
    history.append(snapshot.to_dict())
    history.sort(key=lambda h: h.get("date", ""))

    keep = int(config.get("nss_health_history_days", 365))
    if len(history) > keep:
        history = history[-keep:]

    path.write_text(json.dumps({"records": history}, indent=2), encoding="utf-8")
    return path


def load_health_history(config: dict, *, limit: Optional[int] = None) -> List[MarketHealthSnapshot]:
    path = health_history_path(config)
    if not path.exists():
        return []
    try:
        records = json.loads(path.read_text(encoding="utf-8")).get("records", [])
    except Exception:  # noqa: BLE001
        return []
    snaps = [MarketHealthSnapshot(**r) for r in records]
    if limit:
        snaps = snaps[-limit:]
    return snaps
