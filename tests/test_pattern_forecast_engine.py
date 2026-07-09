"""Unit tests for pattern forecast (2y analogue correlation)."""

import numpy as np
import pandas as pd
import pytest

from tradingagents.screening.pattern_forecast_engine import (
    STRATEGY_ID,
    evaluate_pattern_forecast,
    find_best_analogue,
)

pytestmark = pytest.mark.unit


def _df_from_closes(closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame({
        "Open": closes,
        "High": [c * 1.01 for c in closes],
        "Low": [c * 0.99 for c in closes],
        "Close": closes,
        "Volume": [1_000_000] * len(closes),
    })


def test_strategy_id():
    assert STRATEGY_ID == "pattern_forecast"


def test_find_best_analogue_finds_repeated_pattern():
    window, horizon = 10, 5
    rng = np.random.default_rng(42)
    base = rng.normal(0, 0.01, size=80)
    pattern = rng.normal(0, 0.02, size=window)
    # Earlier analogue at index 20, repeated at end
    returns = np.concatenate([base[:20], pattern, base[20:80 - window], pattern])
    best_i, corr = find_best_analogue(returns, window=window, horizon=horizon)
    assert best_i == 20
    assert corr == pytest.approx(1.0, abs=0.01)


def test_evaluate_rejects_short_history():
    df = _df_from_closes([100.0] * 50)
    sig = evaluate_pattern_forecast(df, {"pattern_forecast_min_bars": 126}, symbol="TEST.NS")
    assert sig.rejected
    assert "Insufficient history" in sig.reject_reason


def test_evaluate_projects_up_on_repeated_rally():
    """Replayed forward segment after best analogue should project UP."""
    window, horizon = 20, 5
    rng = np.random.default_rng(99)
    pattern = rng.normal(0, 0.015, size=window)
    filler = rng.normal(0, 0.01, size=100)
    rally = np.array([0.02, 0.02, 0.02, 0.02, 0.02])
    # [filler][pattern][rally][more filler][pattern at tail]
    returns = np.concatenate([filler, pattern, rally, filler[:40], pattern])
    closes = [100.0]
    for r in returns:
        closes.append(closes[-1] * (1.0 + r))

    df = _df_from_closes(closes)
    config = {
        "pattern_forecast_window": window,
        "pattern_forecast_horizon": horizon,
        "pattern_forecast_min_correlation": 0.5,
        "pattern_forecast_min_bars": 126,
        "pattern_forecast_require_nifty_above_ma": False,
        "pattern_forecast_min_projected_move_pct": 0.5,
        "pattern_forecast_max_projected_move_pct": 50.0,
        "pattern_forecast_min_max_touch_pct": 0.5,
        "pattern_forecast_min_risk_reward": 0.5,
        "pattern_forecast_min_hist_fwd_pct": 0.5,
        "pattern_forecast_min_correlation": 0.5,
        "pattern_forecast_use_consensus": False,
        "pattern_forecast_use_v17": False,
        "pattern_forecast_require_stock_above_ma": False,
        "pattern_forecast_require_weekly_above_ma": False,
        "pattern_forecast_correlation_method": "pearson",
    }
    sig = evaluate_pattern_forecast(df, config, symbol="TEST.NS")
    assert not sig.rejected, sig.reject_reason
    assert sig.correlation >= 0.9
    assert sig.direction == "UP"
    assert sig.projected_close_5d > sig.close


def test_evaluate_rejects_low_correlation():
    rng = np.random.default_rng(7)
    closes = 100.0 * np.cumprod(1.0 + rng.normal(0, 0.02, size=180))
    df = _df_from_closes(closes.tolist())
    sig = evaluate_pattern_forecast(
        df,
        {
            "pattern_forecast_window": 20,
            "pattern_forecast_horizon": 5,
            "pattern_forecast_min_correlation": 0.99,
            "pattern_forecast_min_bars": 126,
            "pattern_forecast_use_v17": False,
            "pattern_forecast_require_stock_above_ma": False,
            "pattern_forecast_require_weekly_above_ma": False,
        },
        symbol="NOISY.NS",
    )
    assert sig.rejected
    assert "bullish analogue" in sig.reject_reason or "below minimum" in sig.reject_reason


def test_rejects_outlier_move_above_cap():
    """Synthetic strong rally should be rejected when move cap is tight."""
    window, horizon = 20, 5
    rng = np.random.default_rng(99)
    pattern = rng.normal(0, 0.015, size=window)
    filler = rng.normal(0, 0.01, size=100)
    rally = np.array([0.04, 0.04, 0.04, 0.04, 0.04])
    returns = np.concatenate([filler, pattern, rally, filler[:40], pattern])
    closes = [100.0]
    for r in returns:
        closes.append(closes[-1] * (1.0 + r))
    df = _df_from_closes(closes)
    sig = evaluate_pattern_forecast(
        df,
        {
            "pattern_forecast_window": window,
            "pattern_forecast_horizon": horizon,
            "pattern_forecast_min_correlation": 0.5,
            "pattern_forecast_min_bars": 126,
            "pattern_forecast_require_nifty_above_ma": False,
            "pattern_forecast_max_projected_move_pct": 15.0,
            "pattern_forecast_min_projected_move_pct": 0.5,
            "pattern_forecast_min_max_touch_pct": 0.5,
            "pattern_forecast_min_risk_reward": 0.5,
            "pattern_forecast_min_hist_fwd_pct": 0.5,
            "pattern_forecast_use_consensus": False,
            "pattern_forecast_use_v17": False,
            "pattern_forecast_require_stock_above_ma": False,
            "pattern_forecast_require_weekly_above_ma": False,
            "pattern_forecast_correlation_method": "pearson",
        },
        symbol="HOT.NS",
    )
    assert sig.rejected
    assert "exceeds cap" in sig.reject_reason
