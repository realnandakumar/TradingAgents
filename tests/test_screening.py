"""Offline unit tests for the India RS screener + pattern engine.

All tests inject synthetic price data, so they make no network calls.
"""

import numpy as np
import pandas as pd
import pytest

from tradingagents.screening.patterns import (
    PatternScore,
    rsi,
    rsi_breakout,
    score_patterns,
)
from tradingagents.screening.relative_strength import rank_by_relative_strength
from tradingagents.screening.universe import _normalise_symbol, _parse_symbol_column


def _frame(closes):
    idx = pd.date_range("2024-01-01", periods=len(closes), freq="D")
    c = pd.Series(closes, index=idx, dtype=float)
    return pd.DataFrame({"Open": c, "High": c * 1.01, "Low": c * 0.99,
                         "Close": c, "Volume": 1000})


pytestmark = pytest.mark.unit


# --- universe normalisation ------------------------------------------------

def test_normalise_symbol_adds_ns_suffix():
    assert _normalise_symbol("reliance") == "RELIANCE.NS"
    assert _normalise_symbol("TCS.NS") == "TCS.NS"     # already suffixed
    assert _normalise_symbol("0700.HK") == "0700.HK"   # other exchange untouched
    assert _normalise_symbol("  ") == ""


def test_parse_symbol_column_handles_both_layouts():
    nse = "Company Name,Industry,Symbol,Series\nReliance,Energy,RELIANCE,EQ\n"
    ours = "symbol,name\nTCS.NS,Tata\n"
    assert _parse_symbol_column(nse) == ["RELIANCE.NS"]
    assert _parse_symbol_column(ours) == ["TCS.NS"]


# --- relative strength -----------------------------------------------------

def test_relative_strength_ranks_strongest_first():
    n = 260
    strong = _frame(list(np.linspace(100, 200, n)))   # +100%
    weak = _frame(list(np.linspace(100, 110, n)))      # +10%
    bench = _frame(list(np.linspace(100, 105, n)))     # +5%
    price_data = {"STRONG.NS": strong, "WEAK.NS": weak, "^NSEI": bench}

    ranked = rank_by_relative_strength(
        ["STRONG.NS", "WEAK.NS"], benchmark="^NSEI", price_data=price_data
    )
    assert [r.symbol for r in ranked] == ["STRONG.NS", "WEAK.NS"]
    assert ranked[0].rs_rank == 1
    assert ranked[0].rs_score > ranked[1].rs_score
    assert ranked[0].rs_percentile == 100.0


# --- pattern detectors -----------------------------------------------------

def test_rsi_is_bounded_and_high_on_uptrend():
    up = _frame(list(np.linspace(100, 200, 120)))
    r = rsi(up["Close"])
    assert (r.dropna() >= 0).all() and (r.dropna() <= 100).all()
    assert r.iloc[-1] > 60  # steady uptrend -> high RSI


def test_rsi_breakout_fires_on_cross_up():
    # A decline drives RSI low, then a rally pushes it up through 60 within
    # the lookback window -> the breakout should fire.
    closes = list(np.linspace(130, 95, 35)) + list(np.linspace(96, 125, 7))
    sig = rsi_breakout(_frame(closes))
    assert sig.fired is True
    assert "RSI" in sig.detail


def test_rsi_breakout_quiet_on_steady_uptrend():
    # A long steady climb keeps RSI high throughout -- no upward *cross*.
    sig = rsi_breakout(_frame(list(np.linspace(100, 200, 120))))
    assert sig.fired is False


def test_score_patterns_returns_structured_result():
    ps = score_patterns("X.NS", _frame(list(np.linspace(100, 160, 260))))
    assert isinstance(ps, PatternScore)
    assert ps.score >= 0
    # fired names must all be known detectors
    assert set(ps.fired) <= set(ps.signals.keys())


def test_score_patterns_survives_short_history():
    ps = score_patterns("X.NS", _frame([100, 101, 102]))
    assert ps.score == 0.0 and ps.fired == []
