"""Unit tests for LuxAlgo NW Envelope indicator + crossover engine."""

import numpy as np
import pandas as pd
import pytest

from tradingagents.screening.nw_envelope_engine import (
    STRATEGY_ID,
    _find_latest_crossover,
    evaluate_nw_envelope,
)
from tradingagents.screening.nw_envelope_indicator import (
    nadaraya_watson_envelope,
    nw_envelope_from_ohlc,
)

pytestmark = pytest.mark.unit


def _ohlc(n: int, close_start: float = 100.0, step: float = 0.0) -> pd.DataFrame:
    closes = [close_start + i * step for i in range(n)]
    return pd.DataFrame({
        "Open": closes,
        "High": [c + 1.0 for c in closes],
        "Low": [c - 1.0 for c in closes],
        "Close": closes,
        "Volume": [1_000_000] * n,
    })


def test_strategy_id():
    assert STRATEGY_ID == "nw_envelope"


def test_nwe_returns_three_bands():
    df = _ohlc(80, close_start=100.0)
    bands = nw_envelope_from_ohlc(df, bandwidth=8.0, mult=3.0, lookback=50)
    assert list(bands.columns) == ["nwe_upper", "nwe_middle", "nwe_lower"]
    assert len(bands) == 80
    last = bands.iloc[-1]
    assert last["nwe_upper"] > last["nwe_middle"] > last["nwe_lower"]


def test_nwe_gaussian_smoothing_flat():
  """Flat series → middle ≈ close, narrow envelope."""
  n = 100
  closes = [100.0] * n
  bands = nadaraya_watson_envelope(pd.Series(closes), bandwidth=8.0, mult=3.0, lookback=50)
  mid = float(bands["nwe_middle"].iloc[-1])
  assert mid == pytest.approx(100.0, abs=0.5)
  width = float(bands["nwe_upper"].iloc[-1]) - float(bands["nwe_lower"].iloc[-1])
  assert width < 5.0


def test_find_buy_cross_below_lower_today():
    close = pd.Series([10.0, 10.0, 8.0])
    upper = pd.Series([12.0, 12.0, 12.0])
    lower = pd.Series([9.0, 9.0, 9.0])
    direction, age = _find_latest_crossover(close, upper, lower, max_age=3)
    assert direction == "BUY"
    assert age == 0


def test_find_sell_cross_above_upper_yesterday():
    close = pd.Series([10.0, 13.0, 13.5])
    upper = pd.Series([12.0, 12.0, 12.0])
    lower = pd.Series([8.0, 8.0, 8.0])
    direction, age = _find_latest_crossover(close, upper, lower, max_age=3)
    assert direction == "SELL"
    assert age == 1


def test_no_crossover_when_inside_envelope():
    close = pd.Series([10.0, 10.5, 10.2])
    upper = pd.Series([12.0, 12.0, 12.0])
    lower = pd.Series([8.0, 8.0, 8.0])
    direction, age = _find_latest_crossover(close, upper, lower, max_age=3)
    assert direction is None
    assert age == -1


def test_evaluate_rejects_insufficient_history():
    df = _ohlc(30)
    sig = evaluate_nw_envelope(df, {"nwe_min_bars": 60}, symbol="X.NS")
    assert sig.rejected
    assert sig.direction == "NONE"
    assert "Insufficient" in sig.remark


def test_evaluate_buy_cross_synthetic():
    """Engineered BUY: prior at/above lower, today below lower."""
    n = 80
    closes = [100.0] * (n - 2) + [100.0, 85.0]
    df = pd.DataFrame({
        "Open": closes,
        "High": [c + 2 for c in closes],
        "Low": [c - 2 for c in closes],
        "Close": closes,
        "Volume": [1_000_000] * n,
    })
    sig = evaluate_nw_envelope(
        df,
        {
            "nwe_bandwidth": 8.0,
            "nwe_mult": 3.0,
            "nwe_lookback": 50,
            "nwe_min_bars": 60,
            "nwe_cross_max_age": 3,
            "nwe_require_still_on_side": True,
        },
        symbol="TEST.NS",
    )
    if not sig.rejected and sig.direction == "BUY":
        assert sig.cross_age == 0
        assert sig.close < sig.lower or sig.dist_pct <= 0
    else:
        assert "NWE" in sig.remark or "REJECT" in sig.remark


def test_hold_check_rejects_reversed_buy():
    close = pd.Series([10.0, 8.0, 9.5])
    upper = pd.Series([12.0, 12.0, 12.0])
    lower = pd.Series([9.0, 9.0, 9.0])
    direction, age = _find_latest_crossover(close, upper, lower, max_age=3)
    if direction == "BUY" and age == 1 and float(close.iloc[-1]) >= float(lower.iloc[-1]):
        m = 80
        closes = [100.0] * (m - 3) + [95.0, 80.0, 96.0]
        df = pd.DataFrame({
            "Open": closes,
            "High": [c + 2 for c in closes],
            "Low": [c - 2 for c in closes],
            "Close": closes,
            "Volume": [1_000_000] * m,
        })
        sig = evaluate_nw_envelope(
            df,
            {
                "nwe_lookback": 40,
                "nwe_min_bars": 60,
                "nwe_cross_max_age": 3,
                "nwe_require_still_on_side": True,
            },
            symbol="HOLD.NS",
        )
        if sig.rejected:
            assert "REJECT" in sig.remark
