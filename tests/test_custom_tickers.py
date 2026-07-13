"""Tests for custom tickers persistence."""

from __future__ import annotations

import pytest

from tradingagents.dataflows.custom_tickers import (
    add_custom_ticker,
    list_custom_tickers,
    load_custom_tickers,
    remove_custom_ticker,
    save_custom_tickers,
)

pytestmark = pytest.mark.unit


def test_add_remove_list_custom_tickers(tmp_path):
    path = tmp_path / "custom_tickers.txt"

    assert load_custom_tickers(str(path)) == []

    updated = add_custom_ticker(["reliance", "TCS.NS"], path=str(path))
    assert updated == ["RELIANCE.NS", "TCS.NS"]
    assert list_custom_tickers(str(path)) == ["RELIANCE.NS", "TCS.NS"]

    dup = add_custom_ticker(["RELIANCE", "INFY"], path=str(path))
    assert dup == ["RELIANCE.NS", "TCS.NS", "INFY.NS"]

    remaining = remove_custom_ticker(["tcs.ns"], path=str(path))
    assert remaining == ["RELIANCE.NS", "INFY.NS"]

    save_custom_tickers(["WIPRO.NS"], path=str(path))
    assert load_custom_tickers(str(path)) == ["WIPRO.NS"]
