"""Unit tests for chart pattern geometry builders."""

from __future__ import annotations

import pandas as pd
import pytest

from tradingagents.screening.chart_pattern_engine import (
    PatternMatch,
    _detect_ascending_triangle,
    detect_bull_flag,
    detect_double_bottom,
)
from tradingagents.screening.chart_pattern_geometry import build_pattern_geometry

pytestmark = pytest.mark.unit


def _ohlc(closes: list[float]) -> pd.DataFrame:
    idx = pd.date_range("2024-01-02", periods=len(closes), freq="B")
    return pd.DataFrame(
        {
            "Open": closes,
            "High": [c * 1.005 for c in closes],
            "Low": [c * 0.995 for c in closes],
            "Close": closes,
            "Volume": [1_000_000] * len(closes),
        },
        index=idx,
    )


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


def _bull_flag_df() -> pd.DataFrame:
    n = 80
    close = [100.0] * n
    pole_start = n - 27
    pole_end = n - 12
    for i in range(pole_start, pole_end):
        close[i] = 100.0 + (i - pole_start) * 1.2
    flag_base = close[pole_end - 1]
    for i in range(pole_end, n):
        close[i] = flag_base + 0.15 * ((i - pole_end) % 3 - 1)
    return _ohlc(close)


def test_double_bottom_geometry():
    df = _double_bottom_df()
    match = detect_double_bottom(df, order=5)
    assert match is not None

    geom = build_pattern_geometry("double_bottom", match, df)

    assert geom["window_start"]
    assert geom["window_end"]
    assert geom["window_start"] <= geom["window_end"]
    assert len(geom["pivots"]) == 2
    roles = {p["role"] for p in geom["pivots"]}
    assert roles == {"trough_1", "trough_2"}
    assert all(p["position"] == "belowBar" for p in geom["pivots"])

    line_ids = {line["id"] for line in geom["lines"]}
    assert f"double_bottom_troughs" in line_ids
    assert f"double_bottom_neckline" in line_ids
    assert f"double_bottom_peak_link" in line_ids


def test_ascending_triangle_geometry():
    df = _ascending_triangle_df()
    match = _detect_ascending_triangle(df, order=5)
    assert match is not None

    geom = build_pattern_geometry("ascending_triangle", match, df)

    assert geom["window_start"]
    assert geom["window_end"]
    assert len(geom["pivots"]) >= 4
    line_labels = {line["label"] for line in geom["lines"]}
    assert "flat resistance" in line_labels
    assert "rising support" in line_labels

    resistance = next(line for line in geom["lines"] if line["id"].endswith("_resistance"))
    res_values = [p["value"] for p in resistance["points"]]
    assert max(res_values) - min(res_values) < 0.01


def test_bull_flag_geometry():
    df = _bull_flag_df()
    match = detect_bull_flag(df)
    assert match is not None

    geom = build_pattern_geometry("bull_flag", match, df)

    assert geom["window_start"]
    assert geom["window_end"]
    assert geom["window_end"] >= geom["window_start"]
    assert len(geom["pivots"]) == 2
    assert {p["role"] for p in geom["pivots"]} == {"pole_start", "pole_end"}

    line_ids = {line["id"] for line in geom["lines"]}
    assert "bull_flag_pole" in line_ids
    assert "bull_flag_flag_top" in line_ids
    assert "bull_flag_flag_bottom" in line_ids


def test_generic_fallback_for_sparse_swings():
    df = _ohlc([100.0 + i * 0.1 for i in range(60)])
    match = PatternMatch(
        confidence=50.0,
        detail="minimal",
        end_idx=len(df) - 1,
        high_swing_idx=[10, 30],
        low_swing_idx=[20, 40],
    )

    geom = build_pattern_geometry("unknown_pattern", match, df)

    assert geom["window_start"]
    assert geom["window_end"]
    assert geom["lines"]
    assert geom["pivots"]
