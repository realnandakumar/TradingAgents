"""Tests for NSS v1.1 scoring helpers."""

import pytest

from tradingagents.screening.nss_scoring import (
    ThresholdMode,
    breakout_hard_gate_pass,
    freshness_score,
    get_threshold_mode,
    graduated_volume_score,
    overall_rating,
    volume_hard_gate_pass,
)

pytestmark = pytest.mark.unit


def test_graduated_volume_tiers():
    cfg = {}
    score, _ = graduated_volume_score(1.17, cfg)
    assert score == 4.0
    score2, _ = graduated_volume_score(2.1, cfg)
    assert score2 == 10.0


def test_volume_hard_gate_unchanged():
    cfg = {"nss_volume_mult": 1.5}
    assert volume_hard_gate_pass(1.49, cfg) is False
    assert volume_hard_gate_pass(1.50, cfg) is True


def test_freshness_scores():
    cfg = {}
    pts, expl = freshness_score(0, cfg)
    assert pts == 25.0
    assert "today" in expl
    pts_old, _ = freshness_score(6, cfg)
    assert pts_old == 0.0


def test_breakout_hard_gate():
    cfg = {"nss_breakout_fresh_sessions": 3}
    assert breakout_hard_gate_pass(2, cfg) is True
    assert breakout_hard_gate_pass(4, cfg) is False


def test_threshold_mode_fixed_default():
    assert get_threshold_mode({}) == ThresholdMode.FIXED


def test_overall_rating():
    assert overall_rating(80, "high") == "Strong"
    assert overall_rating(40, "low") == "Weak"
