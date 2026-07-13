"""Tests for pattern-specific trade levels."""

from __future__ import annotations

import pytest

from tradingagents.screening.chart_pattern_levels import (
    classify_forward_outcome,
    compute_pattern_trade_levels,
)

pytestmark = pytest.mark.unit


def test_bull_flag_uses_pole_projection():
    levels = compute_pattern_trade_levels(
        "bull_flag",
        "BULLISH",
        "APPROACHING",
        trigger=110.0,
        support=105.0,
        resistance=110.0,
        close=108.0,
        pole_height=20.0,
    )
    assert levels is not None
    assert levels.target_1 == pytest.approx(130.0)
    assert levels.target_2 == pytest.approx(150.0)
    assert levels.risk_reward == pytest.approx(4.0)


def test_head_shoulders_uses_shoulder_stop():
    levels = compute_pattern_trade_levels(
        "head_shoulders",
        "BEARISH",
        "AT_TRIGGER",
        trigger=95.0,
        support=95.0,
        resistance=120.0,
        close=96.0,
        shoulder_stop=108.0,
    )
    assert levels is not None
    assert levels.stop == pytest.approx(108.0)
    assert levels.target_1 == pytest.approx(70.0)


def test_outcome_labels_t1():
    outcome = classify_forward_outcome(
        "BULLISH",
        entry=100.0,
        stop=95.0,
        target_1=110.0,
        target_2=120.0,
        highs=[101, 105, 111],
        lows=[99, 98, 100],
        closes=[100, 104, 109],
    )
    assert outcome == "WIN_T1"
