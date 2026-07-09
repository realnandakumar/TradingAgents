"""Unit tests for momentum screener indicators."""

import numpy as np
import pandas as pd
import pytest

from tradingagents.screening.momentum_indicators import (
    adx_rising,
    higher_high_after_pullback,
    macd,
    pct_above_ema,
    volume_short_above_long,
)
from tradingagents.screening.swing_indicators import ema

pytestmark = pytest.mark.unit


def _ohlcv(closes, volumes=None, spread=0.01):
    idx = pd.date_range("2023-01-01", periods=len(closes), freq="B")
    c = pd.Series(closes, index=idx, dtype=float)
    if volumes is None:
        volumes = [1000] * len(closes)
    vol = pd.Series(volumes, index=idx, dtype=float)
    return pd.DataFrame({
        "Open": c,
        "High": c * (1 + spread),
        "Low": c * (1 - spread),
        "Close": c,
        "Volume": vol,
    })


def test_macd_bullish_on_uptrend():
    closes = list(np.linspace(100, 200, 80))
    df = _ohlcv(closes)
    line, sig, _ = macd(df["Close"])
    assert float(line.iloc[-1]) > float(sig.iloc[-1])


def test_volume_short_above_long():
    vols = [1000] * 25
    vols[-5:] = [2000] * 5
    df = _ohlcv(list(np.linspace(100, 120, 25)), volumes=vols)
    ratio = volume_short_above_long(df["Volume"], 5, 20, min_ratio=1.0)
    assert ratio is not None
    assert ratio >= 1.0


def test_pct_above_ema():
    assert pct_above_ema(110, 100) == pytest.approx(10.0)


def test_adx_rising_smoke():
    adx_vals = pd.Series([20, 22, 24, 26, 28], index=pd.date_range("2024-01-01", periods=5, freq="B"))
    assert adx_rising(adx_vals, sessions=3) is True


def test_higher_high_after_pullback():
    # Uptrend with dip then new high
    base = list(np.linspace(100, 130, 30))
    dip = list(np.linspace(130, 118, 5))
    rally = list(np.linspace(118, 145, 15))
    closes = base + dip + rally
    df = _ohlcv(closes)
    ema50 = ema(df["Close"], 50)
    result = higher_high_after_pullback(df, ema50, pullback_sessions=10, hh_lookback=10)
    assert isinstance(result, bool)
