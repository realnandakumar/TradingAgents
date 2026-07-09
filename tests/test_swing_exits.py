"""Tests for swing exit rules (partial T2 + trail)."""

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
        "target_2": 120,
        "phase": "initial",
        "remaining_pct": 100.0,
        "t2_partial_done": False,
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


def test_t2_partial_exit():
    hist = _hist([100, 105, 115], highs=[100, 105, 121])
    bar = hist.iloc[-1]
    bd = hist.index[-1].strftime("%Y-%m-%d")
    acts = evaluate_bar_exits(_pos(), bar, bd, 20, hist, t2_exit_pct=75.0)
    assert len(acts) == 1
    assert acts[0].reason == ExitReason.TARGET_2_PARTIAL
    assert acts[0].partial is True
    assert acts[0].exit_pct == 75.0


def test_runner_trail_stop():
    hist = _hist([100, 110, 108], lows=[100, 110, 104], highs=[100, 110, 108])
    bar = hist.iloc[-1]
    bd = hist.index[-1].strftime("%Y-%m-%d")
    acts = evaluate_bar_exits(
        _pos(phase="runner", remaining_pct=25.0, t2_partial_done=True, trailing_stop=105),
        bar, bd, 20, hist,
    )
    assert len(acts) == 1
    assert acts[0].reason == ExitReason.TRAIL_STOP


def test_risk_pct():
    assert risk_pct(100, 95) == 5.0
    assert risk_pct(100, 98) == 2.0
