"""Tests for collect_sync_symbols deduplication."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tradingagents.dataflows.custom_tickers import save_custom_tickers
from tradingagents.dataflows.sync_symbols import collect_sync_symbols

pytestmark = pytest.mark.unit


def test_collect_sync_symbols_dedupes(tmp_path, monkeypatch):
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    custom_path = tmp_path / "custom_tickers.txt"
    watchlist_path = tmp_path / "watchlist.txt"
    swing_book = tmp_path / "swing" / "positions.json"
    swing_book.parent.mkdir(parents=True)
    swing_book.write_text(
        json.dumps(
            {
                "positions": [
                    {"ticker": "RELIANCE.NS", "status": "open"},
                    {"ticker": "TCS.NS", "status": "closed"},
                ]
            }
        ),
        encoding="utf-8",
    )

    universe_csv = tmp_path / "universe.csv"
    universe_csv.write_text(
        "symbol\nRELIANCE\nINFY\n",
        encoding="utf-8",
    )
    watchlist_path.write_text("RELIANCE\nHDFCBANK\n", encoding="utf-8")
    save_custom_tickers(["INFY.NS", "WIPRO.NS"], path=str(custom_path))

    config = {
        "screen_universe_csv": str(universe_csv),
        "data_cache_dir": str(cache_dir),
        "tech_watchlist_path": str(watchlist_path),
        "custom_tickers_path": str(custom_path),
        "swing_book_path": str(swing_book),
        "screen_benchmark": "^NSEI",
    }

    symbols = collect_sync_symbols(config)

    assert symbols == sorted(set(symbols))
    assert "RELIANCE.NS" in symbols
    assert "INFY.NS" in symbols
    assert "HDFCBANK.NS" in symbols
    assert "WIPRO.NS" in symbols
    assert "TCS.NS" not in symbols
    assert "^NSEI" in symbols
    assert symbols.count("RELIANCE.NS") == 1
