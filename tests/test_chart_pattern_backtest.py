"""Tests for chart pattern backtest (next-day open fill)."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import pytest

from tradingagents.screening.chart_pattern_audit import audit_symbol

pytestmark = pytest.mark.unit


@dataclass
class _FakeHit:
    pattern_id: str = "double_bottom"
    bias: str = "BULLISH"
    setup_status: str = "APPROACHING"
    confidence: float = 70.0
    actionability_score: float = 80.0
    trigger_level: float = 110.0
    support_level: float = 100.0
    resistance_level: float = 110.0
    close: float = 108.0
    levels_valid: bool = True
    entry_level: float = 110.0
    stop_loss: float = 99.0
    target_1: float = 120.0
    target_2: float = 130.0
    risk_reward_ratio: float = 2.0


def _df(n: int = 120) -> pd.DataFrame:
    idx = pd.bdate_range("2020-01-01", periods=n)
    return pd.DataFrame(
        {
            "Open": [100.0 + i * 0.1 for i in range(n)],
            "High": [101.0 + i * 0.1 for i in range(n)],
            "Low": [99.0 + i * 0.1 for i in range(n)],
            "Close": [100.5 + i * 0.1 for i in range(n)],
            "Volume": [1_000_000] * n,
        },
        index=idx,
    )


def test_next_open_fill_uses_following_day_open(monkeypatch):
    df = _df()
    signal_idx = 70

    def _scan(hist, config, symbol=""):
        if len(hist) - 1 == signal_idx:
            return [_FakeHit(close=float(hist["Close"].iloc[-1]))]
        return []

    monkeypatch.setattr(
        "tradingagents.screening.chart_pattern_audit.scan_chart_patterns",
        _scan,
    )
    config = {"chart_pattern_min_bars": 60}
    trades = audit_symbol(
        df,
        config,
        symbol="TEST.NS",
        step=signal_idx - 60,
        horizon=10,
        fill_mode="next_open",
    )
    assert len(trades) == 1
    expected_open = float(df.iloc[signal_idx + 1]["Open"])
    assert trades[0].entry_fill == pytest.approx(expected_open)
    assert trades[0].fill_mode == "next_open"
    assert trades[0].close == pytest.approx(float(df.iloc[signal_idx]["Close"]))


def test_close_fill_uses_signal_day_close(monkeypatch):
    df = _df()
    signal_idx = 70

    def _scan(hist, config, symbol=""):
        if len(hist) - 1 == signal_idx:
            hit = _FakeHit()
            hit.close = float(hist["Close"].iloc[-1])
            return [hit]
        return []

    monkeypatch.setattr(
        "tradingagents.screening.chart_pattern_audit.scan_chart_patterns",
        _scan,
    )
    config = {"chart_pattern_min_bars": 60}
    trades = audit_symbol(
        df,
        config,
        symbol="TEST.NS",
        step=signal_idx - 60,
        horizon=10,
        fill_mode="close",
    )
    assert len(trades) == 1
    assert trades[0].entry_fill == pytest.approx(float(df.iloc[signal_idx]["Close"]))
