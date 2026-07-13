"""Custom ticker list for price sync beyond the NSE universe."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.screening.universe import _normalise_symbol


def _resolve_path(path: Optional[str] = None) -> Path:
    if path:
        return Path(path).expanduser()
    return Path(DEFAULT_CONFIG["custom_tickers_path"]).expanduser()


def _parse_symbols_from_text(text: str) -> List[str]:
    symbols: List[str] = []
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


def load_custom_tickers(path: Optional[str] = None) -> List[str]:
    """Load symbols from the custom tickers file. Returns [] if missing."""
    p = _resolve_path(path)
    if not p.exists():
        return []
    return _parse_symbols_from_text(p.read_text(encoding="utf-8"))


def save_custom_tickers(symbols: List[str], path: Optional[str] = None) -> Path:
    """Persist symbols to the custom tickers file (one per line)."""
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


def add_custom_ticker(symbols: List[str], path: Optional[str] = None) -> List[str]:
    """Append symbols to the custom tickers list, deduplicating."""
    current = load_custom_tickers(path)
    seen = set(current)
    for sym in symbols:
        norm = _normalise_symbol(sym)
        if norm and norm not in seen:
            seen.add(norm)
            current.append(norm)
    save_custom_tickers(current, path)
    return current


def remove_custom_ticker(symbols: List[str], path: Optional[str] = None) -> List[str]:
    """Remove symbols from the custom tickers list."""
    remove_set = {_normalise_symbol(s) for s in symbols}
    remove_set.discard("")
    current = [s for s in load_custom_tickers(path) if s not in remove_set]
    save_custom_tickers(current, path)
    return current


def list_custom_tickers(path: Optional[str] = None) -> List[str]:
    """Return the current custom ticker symbols."""
    return load_custom_tickers(path)
