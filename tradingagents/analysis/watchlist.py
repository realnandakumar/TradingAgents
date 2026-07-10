"""Watchlist persistence for quick tech-analyze runs."""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import List, Optional

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.screening.universe import _normalise_symbol


def _resolve_path(path: Optional[str] = None) -> Path:
    if path:
        return Path(path).expanduser()
    return Path(DEFAULT_CONFIG["tech_watchlist_path"]).expanduser()


def _parse_symbols_from_text(text: str) -> List[str]:
    """Parse one-per-line or CSV with symbol/ticker column."""
    text = text.strip()
    if not text:
        return []

    first_line = text.split("\n", 1)[0]
    if "," in first_line:
        reader = csv.DictReader(io.StringIO(text))
        if reader.fieldnames:
            col = None
            for name in reader.fieldnames:
                if name and name.strip().lower() in ("symbol", "ticker"):
                    col = name
                    break
            if col:
                symbols: List[str] = []
                seen: set[str] = set()
                for row in reader:
                    norm = _normalise_symbol(row.get(col, ""))
                    if norm and norm not in seen:
                        seen.add(norm)
                        symbols.append(norm)
                if symbols:
                    return symbols

    symbols = []
    seen: set[str] = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        sym = line.split(",")[0].strip() if "," in line else line
        norm = _normalise_symbol(sym)
        if norm and norm not in seen:
            seen.add(norm)
            symbols.append(norm)
    return symbols


def load_watchlist(path: Optional[str] = None) -> List[str]:
    """Load symbols from the watchlist file. Returns [] if missing."""
    p = _resolve_path(path)
    if not p.exists():
        return []
    return _parse_symbols_from_text(p.read_text(encoding="utf-8"))


def save_watchlist(symbols: List[str], path: Optional[str] = None) -> Path:
    """Persist symbols to the watchlist file (one per line)."""
    p = _resolve_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    normalized: List[str] = []
    seen: set[str] = set()
    for sym in symbols:
        norm = _normalise_symbol(sym)
        if norm and norm not in seen:
            seen.add(norm)
            normalized.append(norm)
    p.write_text(
        "\n".join(normalized) + ("\n" if normalized else ""),
        encoding="utf-8",
    )
    return p


def add_to_watchlist(symbols: List[str], path: Optional[str] = None) -> List[str]:
    """Append symbols to the watchlist, deduplicating."""
    current = load_watchlist(path)
    seen = set(current)
    for sym in symbols:
        norm = _normalise_symbol(sym)
        if norm and norm not in seen:
            seen.add(norm)
            current.append(norm)
    save_watchlist(current, path)
    return current


def remove_from_watchlist(symbols: List[str], path: Optional[str] = None) -> List[str]:
    """Remove symbols from the watchlist."""
    remove_set = {_normalise_symbol(s) for s in symbols}
    remove_set.discard("")
    current = [s for s in load_watchlist(path) if s not in remove_set]
    save_watchlist(current, path)
    return current


def list_watchlist(path: Optional[str] = None) -> List[str]:
    """Return the current watchlist symbols."""
    return load_watchlist(path)
