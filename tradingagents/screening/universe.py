"""Load the NSE stock universe to screen.

Resolution order (first that succeeds wins):
1. An explicit CSV path the caller passes (or ``TRADINGAGENTS_NSE_UNIVERSE_CSV``).
   Accepts either the official NSE index file (a ``Symbol`` column without the
   ``.NS`` suffix) or our own ``symbol,name`` format (``.NS`` suffix present).
2. A live download of the official NSE Nifty-500 constituents list, cached to
   the data cache dir so we only hit the network once a day.
3. The bundled fallback list shipped with the package.

yfinance has no "list all NSE tickers" endpoint, hence this layered approach.
"""

from __future__ import annotations

import csv
import io
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# Official NSE Nifty 500 constituents (Symbol column has no exchange suffix).
NSE_NIFTY500_URL = "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv"

_FALLBACK_CSV = Path(__file__).resolve().parent.parent / "data" / "nse_nifty500_fallback.csv"

# Browser-like headers; NSE rejects bare requests.
_NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Accept": "text/csv,application/csv,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}


def _normalise_symbol(sym: str) -> str:
    """Return an uppercase yfinance NSE symbol, ensuring the ``.NS`` suffix."""
    sym = sym.strip().upper()
    if not sym:
        return ""
    # Already suffixed (any exchange) -> leave as-is. Otherwise assume NSE.
    if "." in sym:
        return sym
    return f"{sym}.NS"


def _parse_symbol_column(text: str) -> List[str]:
    """Extract ``.NS`` symbols from either CSV layout (ours or NSE's)."""
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return []
    # Find the symbol column case-insensitively.
    col = None
    for name in reader.fieldnames:
        if name and name.strip().lower() in ("symbol", "ticker"):
            col = name
            break
    symbols: List[str] = []
    seen = set()
    if col is None:
        return []
    for row in reader:
        norm = _normalise_symbol(row.get(col, ""))
        if norm and norm not in seen:
            seen.add(norm)
            symbols.append(norm)
    return symbols


def _load_from_path(path: Path) -> List[str]:
    text = path.read_text(encoding="utf-8")
    symbols = _parse_symbol_column(text)
    if not symbols:
        raise ValueError(f"No symbol/ticker column found in {path}")
    return symbols


def _download_nse_list(cache_dir: Optional[str]) -> List[str]:
    """Download the official Nifty 500 list, caching to ``cache_dir`` for the day.

    Raises on any network/parse failure so the caller can fall back.
    """
    cache_path = None
    if cache_dir:
        day = datetime.now().strftime("%Y%m%d")
        cache_path = Path(cache_dir) / f"nse_nifty500_{day}.csv"
        if cache_path.exists():
            return _load_from_path(cache_path)

    import requests  # local import: keep module import cheap

    resp = requests.get(NSE_NIFTY500_URL, headers=_NSE_HEADERS, timeout=15)
    resp.raise_for_status()
    symbols = _parse_symbol_column(resp.text)
    if not symbols:
        raise ValueError("NSE list downloaded but no symbols parsed")

    if cache_path is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(resp.text, encoding="utf-8")
    return symbols


def load_universe(
    csv_path: Optional[str] = None,
    cache_dir: Optional[str] = None,
    allow_download: bool = True,
) -> List[str]:
    """Return a list of ``.NS`` ticker symbols to screen.

    Args:
        csv_path: explicit CSV to use (falls back to the
            ``TRADINGAGENTS_NSE_UNIVERSE_CSV`` env var). Highest priority.
        cache_dir: directory for caching the live NSE download.
        allow_download: set False to skip the network and use only
            ``csv_path`` or the bundled fallback (useful for tests/offline).
    """
    csv_path = csv_path or os.getenv("TRADINGAGENTS_NSE_UNIVERSE_CSV")

    if csv_path:
        p = Path(csv_path).expanduser()
        if p.exists():
            logger.info("Loaded NSE universe from %s", p)
            return _load_from_path(p)
        logger.warning("Universe CSV %s not found; trying download/fallback", p)

    if allow_download:
        try:
            symbols = _download_nse_list(cache_dir)
            logger.info("Loaded %d tickers from live NSE Nifty 500 list", len(symbols))
            return symbols
        except Exception as e:  # noqa: BLE001 - any failure -> fallback
            logger.warning("NSE download failed (%s); using bundled fallback list", e)

    symbols = _load_from_path(_FALLBACK_CSV)
    logger.info("Loaded %d tickers from bundled fallback list", len(symbols))
    return symbols
