"""Tests for swing exit rules (full T1, stop, time)."""

import pandas as pd
import pytest

from tradingagents.swing.exits import ExitReason, evaluate_bar_exits, risk_pct

pytestmark = pytest.mark.unit


def _hist(closes, lows=None, highs=None):
    idx = pd.date_range("2026-01-01", periods=len(closes), freq="B")
    c = pd.Series(closes, index=idx, dtype=float)
    lo = pd.Series(lows if lows is not None else closes, index=idx, dtype=float)
    hi = pd.Series(highs if highs is not None else closes, index=idx, dtype=float)
    return pd.DataFrame({"Open": c, "High": hi, "Low": lo, "Close": c})


def _pos(**kwargs):
    base = {
        "ticker": "T.NS",
        "screen_date": "2026-01-01",
        "entry_price": 100,
        "stop_loss": 95,
        "trailing_stop": 95,
        "target_1": 115,
        "target_2": 120,
        "remaining_pct": 100.0,
    }
    base.update(kwargs)
    return base


def test_stop_full_exit():
    hist = _hist([100, 99, 98], lows=[100, 99, 94], highs=[100, 99, 98])
    bar = hist.iloc[-1]
    bd = hist.index[-1].strftime("%Y-%m-%d")
    acts = evaluate_bar_exits(_pos(), bar, bd, 20, hist)
    assert len(acts) == 1
    assert acts[0].reason == ExitReason.STOP
    assert acts[0].exit_pct == 100.0


def test_t1_full_exit():
    hist = _hist([100, 105, 115], highs=[100, 105, 116])
    bar = hist.iloc[-1]
    bd = hist.index[-1].strftime("%Y-%m-%d")
    acts = evaluate_bar_exits(_pos(), bar, bd, 20, hist)
    assert len(acts) == 1
    assert acts[0].reason == ExitReason.TARGET_1
    assert acts[0].partial is False
    assert acts[0].exit_pct == 100.0


def test_stop_wins_over_t1_same_bar():
    """Ambiguous close (between stop and T1) → conservative stop."""
    hist = _hist([100, 110, 108], lows=[100, 110, 94], highs=[100, 110, 116])
    bar = hist.iloc[-1]
    bd = hist.index[-1].strftime("%Y-%m-%d")
    acts = evaluate_bar_exits(_pos(), bar, bd, 20, hist)
    assert len(acts) == 1
    assert acts[0].reason == ExitReason.STOP


def test_t1_wins_same_bar_when_close_at_target():
    """Same-bar stop+T1 with close at/through T1 → credit target."""
    hist = _hist([100, 110, 116], lows=[100, 110, 94], highs=[100, 110, 116])
    bar = hist.iloc[-1]
    bd = hist.index[-1].strftime("%Y-%m-%d")
    acts = evaluate_bar_exits(_pos(), bar, bd, 20, hist)
    assert len(acts) == 1
    assert acts[0].reason == ExitReason.TARGET_1


def test_risk_pct():
    assert risk_pct(100, 95) == 5.0
    assert risk_pct(100, 98) == 2.0


def test_nan_ohlc_does_not_time_exit():
    hist = _hist([100, 101, float("nan")])
    bar = hist.iloc[-1]
    bd = hist.index[-1].strftime("%Y-%m-%d")
    acts = evaluate_bar_exits(_pos(), bar, bd, 2, hist)
    assert acts == []
