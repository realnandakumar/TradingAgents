"""Tests for SQLite OHLCV store."""

from __future__ import annotations

import pandas as pd
import pytest

from tradingagents.dataflows.ohlcv_db import (
    read_bars,
    read_bars_as_of,
    read_bars_db,
    read_history_db,
    upsert_bars,
)

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


def test_read_bars_as_of_no_lookahead(tmp_path):
    db_path = tmp_path / "prices.db"
    dates = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"])
    df = _bars(dates, [10, 11, 12, 13])
    upsert_bars("PIT.NS", df, db_path=str(db_path))

    as_of = read_bars_as_of("PIT.NS", "2024-01-03", db_path=str(db_path))
    assert list(as_of["Date"].dt.strftime("%Y-%m-%d")) == ["2024-01-02", "2024-01-03"]

    alias = read_bars("PIT.NS", db_path=str(db_path))
    assert len(alias) == 4


def test_upsert_read_and_period_filter(tmp_path):
    db_path = tmp_path / "prices.db"
    end = pd.Timestamp.today().normalize()
    dates = pd.bdate_range(end=end, periods=300)
    df = _bars(dates, list(range(300)))
    upsert_bars("TEST.NS", df, db_path=str(db_path))

    loaded = read_bars_db("TEST.NS", db_path=str(db_path))
    assert len(loaded) == 300

    sliced = read_bars_db("TEST.NS", start=dates[-60].strftime("%Y-%m-%d"), db_path=str(db_path))
    assert len(sliced) >= 40

    history = read_history_db(["TEST.NS"], period="1y", db_path=str(db_path))
    assert "TEST.NS" in history
    assert len(history["TEST.NS"]) >= 1
