"""Unit tests for Chart Patterns engine."""

from __future__ import annotations

import pandas as pd
import pytest

from tradingagents.screening.chart_pattern_engine import (
    STRATEGY_ID,
    STRATEGY_NAME,
    PATTERN_CATALOG,
    detect_double_bottom,
    scan_chart_patterns,
)

pytestmark = pytest.mark.unit

BASE_CONFIG = {
    "chart_pattern_min_bars": 60,
    "chart_pattern_swing_order": 5,
    "chart_pattern_min_confidence": 0,
    "chart_pattern_max_age_days": 14,
    "chart_pattern_max_distance_to_trigger_pct": 10.0,
}


def _ohlc(closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame({
        "Open": closes,
        "High": [c * 1.005 for c in closes],
        "Low": [c * 0.995 for c in closes],
        "Close": closes,
        "Volume": [1_000_000] * len(closes),
    })


def _embed_peak(close: list[float], idx: int, level: float, order: int = 5) -> None:
    for d in range(-order, order + 1):
        j = idx + d
        if 0 <= j < len(close):
            close[j] = level - abs(d) * 0.2


def _embed_trough(close: list[float], idx: int, level: float, order: int = 5) -> None:
    for d in range(-order, order + 1):
        j = idx + d
        if 0 <= j < len(close):
            close[j] = level + abs(d) * 0.2


def _double_bottom_df() -> pd.DataFrame:
    n = 90
    close = [112.0] * n
    _embed_trough(close, 28, 100.0)
    _embed_trough(close, 78, 100.5)
    for i in range(80, n - 1):
        close[i] = 108.0 + (i - 80) * 0.15
    close[-1] = 110.5
    return _ohlc(close)


def _ascending_triangle_df() -> pd.DataFrame:
    n = 100
    close = [115.0] * n
    for idx in (18, 48, 78):
        _embed_peak(close, idx, 120.0)
    for idx, level in ((33, 100.0), (63, 105.0), (93, 110.0)):
        _embed_trough(close, idx, level)
    close[-1] = 118.0
    return _ohlc(close)


def _rectangle_df() -> pd.DataFrame:
    n = 100
    close = [110.0] * n
    for idx in (20, 50, 80):
        _embed_peak(close, idx, 120.0)
    for idx in (35, 65, 95):
        _embed_trough(close, idx, 100.0)
    close[-1] = 110.0
    return _ohlc(close)


def test_strategy_meta():
    assert STRATEGY_ID == "chart_patterns"
    assert STRATEGY_NAME == "Chart Patterns"
    assert "double_bottom" in PATTERN_CATALOG


def test_double_bottom_detector():
    df = _double_bottom_df()
    hit = detect_double_bottom(df, order=5)
    assert hit is not None
    assert hit.confidence >= 70.0
    assert "twin troughs" in hit.detail


def test_scan_finds_double_bottom():
    df = _double_bottom_df()
    hits = scan_chart_patterns(
        df,
        {**BASE_CONFIG, "chart_pattern_enabled": "double_bottom"},
        symbol="TEST.NS",
    )
    assert hits
    assert hits[0].pattern_id == "double_bottom"
    assert hits[0].symbol == "TEST.NS"
    assert hits[0].setup_status in {"AT_TRIGGER", "APPROACHING"}
    assert hits[0].actionability_score > 0


def test_scan_finds_ascending_triangle():
    df = _ascending_triangle_df()
    hits = scan_chart_patterns(
        df,
        {**BASE_CONFIG, "chart_pattern_enabled": "ascending_triangle"},
        symbol="TRI.NS",
    )
    assert hits
    assert any(h.pattern_id == "ascending_triangle" for h in hits)


def test_scan_finds_rectangle():
    df = _rectangle_df()
    hits = scan_chart_patterns(
        df,
        {
            **BASE_CONFIG,
            "chart_pattern_enabled": "rectangle",
            "chart_pattern_max_age_days": 25,
            "chart_pattern_exclude_today": False,
        },
        symbol="BOX.NS",
    )
    assert hits
    assert any(h.pattern_id == "rectangle" for h in hits)


def test_scan_empty_for_short_history():
    df = _ohlc([100.0] * 20)
    hits = scan_chart_patterns(df, BASE_CONFIG, symbol="SHORT.NS")
    assert hits == []


def test_scan_empty_for_none():
    hits = scan_chart_patterns(None, BASE_CONFIG, symbol="NONE.NS")
    assert hits == []


def test_scan_respects_min_confidence():
    df = _double_bottom_df()
    hits = scan_chart_patterns(
        df,
        {
            **BASE_CONFIG,
            "chart_pattern_enabled": "double_bottom",
            "chart_pattern_min_confidence": 99.9,
        },
        symbol="TEST.NS",
    )
    assert hits == []


def test_scan_rejects_stale_pattern():
    df = _double_bottom_df()
    hits = scan_chart_patterns(
        df,
        {
            **BASE_CONFIG,
            "chart_pattern_enabled": "double_bottom",
            "chart_pattern_max_age_days": 10,
        },
        symbol="TEST.NS",
    )
    assert hits == []


def test_scan_rejects_extended_breakout():
    df = _double_bottom_df()
    closes = df["Close"].tolist()
    closes[-1] = closes[-2] * 1.10
    df = _ohlc(closes)
    hits = scan_chart_patterns(
        df,
        {
            **BASE_CONFIG,
            "chart_pattern_enabled": "double_bottom",
            "chart_pattern_max_breakout_pct": 3.0,
            "chart_pattern_exclude_today": False,
        },
        symbol="TEST.NS",
    )
    assert hits == []


def test_scan_exclude_today_uses_completed_bar():
    df = _double_bottom_df()
    live = df["Close"].tolist()
    live[-1] = live[-2] * 1.12
    df_live = _ohlc(live)
    hits = scan_chart_patterns(
        df_live,
        {
            **BASE_CONFIG,
            "chart_pattern_enabled": "double_bottom",
            "chart_pattern_exclude_today": True,
            "chart_pattern_max_breakout_pct": 3.0,
        },
        symbol="TEST.NS",
    )
    assert hits
    assert any("today's bar excluded" in r for r in hits[0].reasons)


def test_scan_rejects_far_from_trigger():
    df = _double_bottom_df()
    closes = df["Close"].tolist()
    closes[-1] = 102.0
    df = _ohlc(closes)
    hits = scan_chart_patterns(
        df,
        {
            **BASE_CONFIG,
            "chart_pattern_enabled": "double_bottom",
            "chart_pattern_max_distance_to_trigger_pct": 5.0,
            "chart_pattern_exclude_today": False,
        },
        symbol="TEST.NS",
    )
    assert hits == []
