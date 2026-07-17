"""Unit tests for momentum exit rules."""

import pandas as pd
import pytest

from tradingagents.momentum.exits import evaluate_momentum_bar_exits
from tradingagents.swing.exits import ExitReason

pytestmark = pytest.mark.unit


def _bar(low, high, close):
    return pd.Series({"Low": low, "High": high, "Close": close})


def _history(dates):
    idx = pd.to_datetime(dates)
    return pd.DataFrame({"Close": [100] * len(dates)}, index=idx)


def test_time_exit_at_max_holding_days():
    pos = {
        "ticker": "TEST.NS",
        "screen_date": "2026-01-01",
        "phase": "initial",
        "remaining_pct": 100.0,
        "trailing_stop": 90.0,
        "stop_loss": 90.0,
        "target_1": 115.0,
        "target_2": 120.0,
        "t2_partial_done": False,
    }
    dates = pd.bdate_range("2026-01-01", periods=25)
    hist = pd.DataFrame({"Close": [100] * 25}, index=dates)
    actions = evaluate_momentum_bar_exits(
        pos, _bar(99, 101, 100), "2026-01-30", max_holding_days=20, history=hist
    )
    assert len(actions) == 1
    assert actions[0].reason.value == "time_exit"


def test_no_time_exit_before_max():
    pos = {
        "ticker": "TEST.NS",
        "screen_date": "2026-01-01",
        "phase": "initial",
        "remaining_pct": 100.0,
        "trailing_stop": 80.0,
        "stop_loss": 80.0,
        "target_1": 115.0,
        "target_2": 120.0,
        "t2_partial_done": False,
    }
    dates = pd.bdate_range("2026-01-01", periods=15)
    hist = pd.DataFrame({"Close": [100] * 15}, index=dates)
    actions = evaluate_momentum_bar_exits(
        pos, _bar(99, 101, 100), "2026-01-20", max_holding_days=20, history=hist
    )
    assert actions == []


def test_target_1_full_exit():
    pos = {
        "ticker": "TEST.NS",
        "screen_date": "2026-01-01",
        "phase": "initial",
        "remaining_pct": 100.0,
        "trailing_stop": 90.0,
        "stop_loss": 90.0,
        "target_1": 115.0,
        "target_2": 120.0,
        "t2_partial_done": False,
    }
    dates = pd.bdate_range("2026-01-01", periods=10)
    hist = pd.DataFrame({"Close": [100] * 10}, index=dates)
    actions = evaluate_momentum_bar_exits(
        pos, _bar(99, 116, 114), "2026-01-10", max_holding_days=20, history=hist
    )
    assert len(actions) == 1
    assert actions[0].reason == ExitReason.TARGET_1
    assert actions[0].exit_pct == 100.0
    assert not actions[0].partial


def test_target_2_partial_enum_exists():
    assert ExitReason.TARGET_2_PARTIAL.value == "target_2_partial"
