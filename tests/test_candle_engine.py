"""Unit tests for confirmed Japanese candlestick detectors."""

from __future__ import annotations

import pandas as pd
import pytest

from tradingagents.screening.candle_engine import scan_candlesticks

pytestmark = pytest.mark.unit


def _df(rows):
    idx = pd.to_datetime([r[0] for r in rows])
    return pd.DataFrame(
        {
            "Open": [r[1] for r in rows],
            "High": [r[2] for r in rows],
            "Low": [r[3] for r in rows],
            "Close": [r[4] for r in rows],
            "Volume": [1000] * len(rows),
        },
        index=idx,
    )


def test_hammer_requires_confirm_bar():
    # Quiet bars, then hammer, then confirm above mid
    rows = [
        ("2026-07-01", 100, 101, 99, 100),
        ("2026-07-02", 100, 101, 99, 100),
        ("2026-07-03", 100, 101, 99, 100),
        ("2026-07-04", 100, 101, 99, 100),
        ("2026-07-05", 100, 101, 99, 100),
        ("2026-07-06", 100, 101, 99, 100),
        ("2026-07-07", 100, 101, 99, 100),
        ("2026-07-08", 100, 101, 99, 100),
        ("2026-07-09", 100, 101, 99, 100),
        ("2026-07-10", 100, 101, 99, 100),
        ("2026-07-11", 100, 101, 99, 100),
        ("2026-07-12", 100, 101, 99, 100),
        ("2026-07-13", 100, 101, 99, 100),
        ("2026-07-14", 100, 101, 99, 100),
        ("2026-07-15", 98, 99, 90, 97),  # hammer: long lower wick
        ("2026-07-16", 97.5, 102, 97, 101),  # confirm
    ]
    hits = scan_candlesticks(_df(rows), {"candle_enabled": "hammer"}, symbol="TEST.NS")
    assert any(h.pattern_id == "hammer" and h.bias == "BULLISH" for h in hits)
    hammer = next(h for h in hits if h.pattern_id == "hammer")
    assert hammer.stop_loss < hammer.entry_level
    assert hammer.target_1 > hammer.entry_level


def test_hammer_without_confirm_is_ignored():
    rows = [
        ("2026-07-01", 100, 101, 99, 100),
        ("2026-07-02", 100, 101, 99, 100),
        ("2026-07-03", 100, 101, 99, 100),
        ("2026-07-04", 100, 101, 99, 100),
        ("2026-07-05", 100, 101, 99, 100),
        ("2026-07-06", 100, 101, 99, 100),
        ("2026-07-07", 100, 101, 99, 100),
        ("2026-07-08", 100, 101, 99, 100),
        ("2026-07-09", 100, 101, 99, 100),
        ("2026-07-10", 100, 101, 99, 100),
        ("2026-07-11", 100, 101, 99, 100),
        ("2026-07-12", 100, 101, 99, 100),
        ("2026-07-13", 100, 101, 99, 100),
        ("2026-07-14", 100, 101, 99, 100),
        ("2026-07-15", 100, 101, 99, 100),
        ("2026-07-16", 98, 99, 90, 97),  # hammer as last bar — no confirm yet
    ]
    hits = scan_candlesticks(_df(rows), {"candle_enabled": "hammer"}, symbol="TEST.NS")
    assert hits == []


def test_bullish_engulfing_with_confirm():
    rows = [
        ("2026-07-01", 100, 101, 99, 100),
        ("2026-07-02", 100, 101, 99, 100),
        ("2026-07-03", 100, 101, 99, 100),
        ("2026-07-04", 100, 101, 99, 100),
        ("2026-07-05", 100, 101, 99, 100),
        ("2026-07-06", 100, 101, 99, 100),
        ("2026-07-07", 100, 101, 99, 100),
        ("2026-07-08", 100, 101, 99, 100),
        ("2026-07-09", 100, 101, 99, 100),
        ("2026-07-10", 100, 101, 99, 100),
        ("2026-07-11", 100, 101, 99, 100),
        ("2026-07-12", 100, 101, 99, 100),
        ("2026-07-13", 100, 101, 99, 100),
        ("2026-07-14", 105, 106, 100, 101),  # bearish prior
        ("2026-07-15", 100, 108, 99.5, 107),  # bullish engulfing
        ("2026-07-16", 107, 110, 106, 109),  # confirm above high
    ]
    hits = scan_candlesticks(
        _df(rows),
        {"candle_enabled": "bullish_engulfing"},
        symbol="TEST.NS",
    )
    assert any(h.pattern_id == "bullish_engulfing" for h in hits)
