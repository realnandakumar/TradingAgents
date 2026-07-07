"""Unit tests for SuperTrend + RSI engine."""

import numpy as np
import pandas as pd
import pytest

from tradingagents.screening.supertrend_rsi_engine import (
    MAX_RAW_SCORE,
    STRATEGY_ID,
    _candle_strength_points,
    _check_mandatory_buy,
    _freshness_points,
    _grade,
    _normalize_score,
    _rsi_momentum_points,
    _rsi_strength_points,
    evaluate_supertrend_rsi,
)

pytestmark = pytest.mark.unit


def test_strategy_metadata():
    assert STRATEGY_ID == "supertrend_rsi"


def test_freshness_table():
    assert _freshness_points(1) == 40.0
    assert _freshness_points(5) == 10.0
    assert _freshness_points(6) == 0.0


def test_rsi_strength_buy_bands():
    assert _rsi_strength_points(62, "BUY") == 20.0
    assert _rsi_strength_points(38, "SELL") == 20.0


def test_rsi_momentum_buy():
    series = pd.Series([50.0, 56.0])
    assert _rsi_momentum_points(series, "BUY") == 15.0


def test_candle_strength():
    assert _candle_strength_points(100, 110, 90, 114) == 15.0
    assert _candle_strength_points(100, 110, 90, 108) == 5.0


def test_normalize_and_grade():
    assert _normalize_score(170) == 100
    assert _normalize_score(85) == 50
    label, stars = _grade(93)
    assert label == "Excellent"
    assert "★" in stars


def test_max_raw_score_constant():
    assert MAX_RAW_SCORE == 170.0


def test_evaluate_insufficient_data():
    df = pd.DataFrame({
        "Open": [100] * 10,
        "High": [101] * 10,
        "Low": [99] * 10,
        "Close": [100] * 10,
        "Volume": [1000] * 10,
    })
    sig = evaluate_supertrend_rsi(df, {}, symbol="X.NS")
    assert sig.rejected
    assert sig.direction == "NONE"


def test_mandatory_buy_rejects_stale_flip():
    n = 20
    close = pd.Series([100.0] * n)
    st_line = pd.Series([99.0] * n)
    trend = pd.Series([1] * n)
    trend.iloc[5] = -1
    trend.iloc[6] = 1
    close.iloc[4] = 98.0
    close.iloc[5] = 101.0
    close.iloc[6] = 102.0
    close.iloc[-1] = 103.0
    rsi_series = pd.Series([55.0] * n)

    ok, reason, _ = _check_mandatory_buy(
        close, st_line, trend, rsi_series, {"strsi_mandatory_flip_max_age": 5}
    )
    assert not ok
    assert "flip too old" in reason
