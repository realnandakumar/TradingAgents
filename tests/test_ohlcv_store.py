"""Unit tests for canonical OHLCV store (merge, manifest, migration)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from tradingagents.dataflows.ohlcv_store import (
    _merge_bars,
    _needs_sync,
    canonical_csv_path,
    migrate_legacy_cache,
    read_bars,
    read_history,
    sync_price_cache,
    write_bars,
)
from tradingagents.dataflows.config import set_config

pytestmark = pytest.mark.unit


def _bars(dates, closes):
    return pd.DataFrame(
        {
            "Date": pd.to_datetime(dates),
            "Open": closes,
            "High": closes,
            "Low": closes,
            "Close": closes,
            "Volume": [1000] * len(dates),
        }
    )


def test_merge_bars_dedupes_and_sorts():
    a = _bars(["2024-01-01", "2024-01-02"], [100, 101])
    b = _bars(["2024-01-02", "2024-01-03"], [999, 102])
    merged = _merge_bars(a, b)
    assert list(merged["Date"].dt.strftime("%Y-%m-%d")) == [
        "2024-01-01",
        "2024-01-02",
        "2024-01-03",
    ]
    assert merged.loc[merged["Date"] == "2024-01-02", "Close"].iloc[0] == 999


def test_symbol_cache_filename_ampersand():
    from tradingagents.dataflows.utils import symbol_cache_filename

    assert symbol_cache_filename("M&M.NS") == "M_M.NS"
    assert symbol_cache_filename("J&KBANK.NS") == "J_KBANK.NS"
    assert symbol_cache_filename("^NSEI") == "_NSEI"
    path = canonical_csv_path("M&M.NS", cache_dir="/tmp/cache")
    assert path.name == "M_M.NS.csv"


def test_write_and_read_bars_roundtrip(tmp_path):
    set_config({
        "data_cache_dir": str(tmp_path),
        "prices_db_path": str(tmp_path / "prices.db"),
    })
    df = _bars(["2024-06-01", "2024-06-02"], [50, 51])
    write_bars("TEST.NS", df, cache_dir=str(tmp_path))
    path = canonical_csv_path("TEST.NS", cache_dir=str(tmp_path))
    assert path.exists()
    loaded = read_bars("TEST.NS", cache_dir=str(tmp_path))
    assert len(loaded) == 2
    assert loaded["Close"].iloc[-1] == 51


def test_read_history_filters_period(tmp_path):
    end = pd.Timestamp.today().normalize()
    dates = pd.bdate_range(end=end, periods=800)
    df = _bars(dates, list(range(800)))
    write_bars("FILTER.NS", df, cache_dir=str(tmp_path))
    out = read_history(["FILTER.NS"], period="1y", cache_dir=str(tmp_path))
    assert "FILTER.NS" in out
    assert len(out["FILTER.NS"]) < 400


def test_needs_sync_respects_manifest_freshness(tmp_path):
    today = pd.Timestamp.today().normalize()
    manifest = {
        "version": 1,
        "symbols": {
            "FRESH.NS": {"last_bar": today.strftime("%Y-%m-%d"), "rows": 10, "synced_at": ""},
        },
    }
    assert _needs_sync("FRESH.NS", manifest, str(tmp_path), mode="incremental") is False

    stale = today - pd.Timedelta(days=5)
    manifest["symbols"]["STALE.NS"] = {
        "last_bar": stale.strftime("%Y-%m-%d"),
        "rows": 10,
        "synced_at": "",
    }
    assert _needs_sync("STALE.NS", manifest, str(tmp_path), mode="incremental") is True


def test_sync_updates_manifest(monkeypatch, tmp_path):
    set_config({
        "data_cache_dir": str(tmp_path),
        "prices_db_path": str(tmp_path / "prices.db"),
    })
    universe = ["SYNC.NS"]
    fetched = {
        "SYNC.NS": _bars(["2024-01-01", "2024-01-02"], [10, 11]),
    }

    monkeypatch.setattr(
        "tradingagents.dataflows.ohlcv_store._download_batch",
        lambda *a, **k: fetched,
    )

    report = sync_price_cache(universe, mode="full", cache_dir=str(tmp_path))
    assert report.synced == 1
    assert report.failed == 0

    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["symbols"]["SYNC.NS"]["first_bar"] == "2024-01-01"
    assert manifest["symbols"]["SYNC.NS"]["last_bar"] == "2024-01-02"
    assert manifest["symbols"]["SYNC.NS"]["rows"] == 2

    from tradingagents.dataflows.ohlcv_db import read_bars_db

    db_rows = read_bars_db("SYNC.NS", db_path=str(tmp_path / "prices.db"))
    assert len(db_rows) == 2


def test_migrate_legacy_cache(tmp_path):
    legacy = tmp_path / "RELIANCE.NS-YFin-data-2020-01-01-2025-01-01.csv"
    df = _bars(["2023-01-01", "2023-01-02"], [100, 101])
    df.to_csv(legacy, index=False)

    n = migrate_legacy_cache(str(tmp_path))
    assert n == 1
    assert not legacy.exists()
    assert canonical_csv_path("RELIANCE.NS", cache_dir=str(tmp_path)).exists()
    loaded = read_bars("RELIANCE.NS", cache_dir=str(tmp_path))
    assert len(loaded) == 2
