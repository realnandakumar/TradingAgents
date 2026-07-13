"""Collect the full symbol set for daily OHLCV sync."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from tradingagents.analysis.watchlist import load_watchlist
from tradingagents.dataflows.custom_tickers import load_custom_tickers
from tradingagents.screening.universe import _normalise_symbol, load_universe

logger = logging.getLogger(__name__)

_BOOK_PATH_KEYS = (
    "swing_book_path",
    "momentum_book_path",
    "nss_book_path",
    "strsi_book_path",
    "trama_book_path",
    "gap_fill_book_path",
    "nwe_book_path",
    "pattern_forecast_book_path",
    "tech_desk_book_path",
)


def _resolve_benchmark(config: dict) -> Optional[str]:
    explicit = config.get("benchmark_ticker")
    if explicit:
        raw = str(explicit).strip().upper()
        if raw.startswith("^"):
            return raw
        return _normalise_symbol(raw) or raw
    bench = config.get("screen_benchmark") or config.get("paper_benchmark")
    if bench:
        raw = str(bench).strip().upper()
        if raw.startswith("^"):
            return raw
        return _normalise_symbol(raw) or raw
    return "^NSEI"


def _open_tickers_from_book(book_path: Path) -> List[str]:
    if not book_path.exists():
        return []
    try:
        data = json.loads(book_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Could not read book %s (%s)", book_path, e)
        return []
    positions = data.get("positions", []) if isinstance(data, dict) else data
    if not isinstance(positions, list):
        return []
    out: List[str] = []
    for pos in positions:
        if not isinstance(pos, dict):
            continue
        if pos.get("status") != "open":
            continue
        ticker = pos.get("ticker") or pos.get("symbol")
        if not ticker:
            continue
        norm = _normalise_symbol(str(ticker))
        if norm:
            out.append(norm)
    return out


def _open_position_tickers(config: dict) -> List[str]:
    tickers: List[str] = []
    for key in _BOOK_PATH_KEYS:
        raw = config.get(key)
        if not raw:
            continue
        tickers.extend(_open_tickers_from_book(Path(str(raw)).expanduser()))
    return tickers


def collect_sync_symbols(config: Optional[dict] = None) -> List[str]:
    """Return deduplicated, sorted symbols for price-cache sync.

    Sources: NSE universe, tech watchlist, custom tickers, open desk positions,
    and the configured benchmark index.
    """
    cfg: Dict = dict(config or {})
    seen: set[str] = set()
    symbols: List[str] = []

    def _add(items: List[str]) -> None:
        for sym in items:
            norm = _normalise_symbol(sym) if sym else ""
            if norm and norm not in seen:
                seen.add(norm)
                symbols.append(norm)

    _add(
        load_universe(
            csv_path=cfg.get("screen_universe_csv"),
            cache_dir=cfg.get("data_cache_dir"),
            allow_download=True,
        )
    )
    _add(load_watchlist(cfg.get("tech_watchlist_path")))
    _add(load_custom_tickers(cfg.get("custom_tickers_path")))
    _add(_open_position_tickers(cfg))

    bench = _resolve_benchmark(cfg)
    if bench:
        sym = bench.strip().upper()
        if sym and sym not in seen:
            seen.add(sym)
            symbols.append(sym)

    return sorted(symbols)
