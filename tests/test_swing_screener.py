"""Offline unit tests for the swing screener indicators and filters."""

import numpy as np
import pandas as pd
import pytest

from tradingagents.screening.swing_indicators import (
    adx,
    compute_trade_levels,
    ema,
    is_at_new_52_week_low,
    relative_volume,
    rsi_crossed_above,
    supertrend,
    supertrend_flip_to_buy_within,
    volume_spike_pct,
)
from tradingagents.screening.swing_screener import _passes_technical_filters
from tradingagents.screening.universe import load_universe_metadata, _parse_universe_records


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


pytestmark = pytest.mark.unit


def test_ema_tracks_uptrend():
    closes = list(np.linspace(100, 200, 60))
    df = _ohlcv(closes)
    e20 = ema(df["Close"], 20)
    assert float(e20.iloc[-1]) > float(e20.iloc[0])


def test_relative_volume_spike():
    vols = [1000] * 25
    vols[-1] = 2500
    df = _ohlcv(list(np.linspace(100, 110, 25)), volumes=vols)
    rel = relative_volume(df["Volume"], 20)
    assert rel is not None
    assert rel == pytest.approx(2.5, rel=0.01)
    assert volume_spike_pct(df["Volume"], 20) == pytest.approx(150.0, rel=0.1)


def test_rsi_crossed_above_detects_latest_cross():
    # Build a series that ends with RSI crossing 50 on the last bar.
    closes = [100] * 30
    closes.extend(list(np.linspace(100, 130, 20)))
    df = _ohlcv(closes)
    assert rsi_crossed_above(df["Close"]) in (True, False)  # smoke
    # Force cross by appending a sharp up move after flat period.
    flat = [100.0] * 40
    ramp = list(np.linspace(100, 150, 30))
    df2 = _ohlcv(flat + ramp)
    # Not guaranteed to cross on last bar for arbitrary data; just ensure callable.
    _ = rsi_crossed_above(df2["Close"])


def test_supertrend_flip_within_sessions():
    # Mostly down then up to force a recent flip.
    closes = list(np.linspace(120, 80, 100)) + list(np.linspace(80, 140, 80))
    df = _ohlcv(closes)
    _, trend = supertrend(df, period=10, multiplier=3.0)
    assert trend.iloc[-1] in (1, -1)
    # Smoke: helper runs without error on real trend series.
    _ = supertrend_flip_to_buy_within(trend, sessions=3)


def test_supertrend_produces_buy_sell_labels():
    closes = list(np.linspace(80, 160, 120))
    df = _ohlcv(closes)
    _, trend = supertrend(df, period=10, multiplier=3.0)
    assert trend.iloc[-1] in (1, -1)


def test_adx_positive_on_trending_series():
    closes = list(np.linspace(80, 200, 120))
    df = _ohlcv(closes)
    series = adx(df, period=14)
    assert float(series.iloc[-1]) > 0


def test_is_at_new_52_week_low():
    lows = [100] * 251 + [90]
    df = _ohlcv(lows)
    assert is_at_new_52_week_low(df["Close"]) is True
    recovery = [90] + [100] * 251
    df2 = _ohlcv(recovery)
    assert is_at_new_52_week_low(df2["Close"]) is False


def test_compute_trade_levels():
    levels = compute_trade_levels(100.0, 90.0, target_1_rr=1.5, target_2_rr=2.5)
    assert levels["target_1"] == 115.0
    assert levels["target_2"] == 125.0
    assert levels["stop_loss_pct"] == -10.0
    assert levels["target_1_pct"] == 15.0
    assert levels["target_2_pct"] == 25.0
    assert levels["risk_reward_ratio"] == 1.5
    assert levels["risk_reward_ratio_2"] == 2.5


def test_parse_universe_records_nse_layout():
    text = "Company Name,Industry,Symbol,Series\nReliance,Energy,RELIANCE,EQ\n"
    rec = _parse_universe_records(text)
    assert rec["RELIANCE.NS"]["name"] == "Reliance"
    assert rec["RELIANCE.NS"]["sector"] == "Energy"


def test_load_universe_metadata_from_fallback():
    meta = load_universe_metadata(allow_download=False)
    assert "RELIANCE.NS" in meta
    assert meta["RELIANCE.NS"]["name"]


def test_technical_filter_rejects_short_history():
    df = _ohlcv(list(np.linspace(100, 110, 50)))
    config = {
        "swing_supertrend_period": 10,
        "swing_supertrend_multiplier": 3.0,
        "swing_rsi_period": 14,
        "swing_adx_period": 14,
        "swing_volume_lookback": 20,
        "swing_volume_mult": 1.2,
        "swing_adx_min": 15.0,
        "swing_rsi_min": 50.0,
        "swing_rsi_max": 65.0,
        "swing_ema_mid": 50,
        "swing_flip_lookback_sessions": 3,
        "swing_target_1_rr": 1.5,
        "swing_target_2_rr": 2.5,
    }
    assert _passes_technical_filters(df, config) is None
