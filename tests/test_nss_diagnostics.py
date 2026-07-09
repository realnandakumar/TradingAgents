"""Unit tests for NSS scanner diagnostics (v1.1)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from tradingagents.screening.nss_diagnostics import (
    EXPANDED_WATERFALL_ORDER,
    TickerDiagnostic,
    _build_waterfall,
    _count_stage,
    _near_misses,
    diagnose_nss,
)
from tradingagents.screening.nss_pipeline import StageResult

pytestmark = pytest.mark.unit


def _ohlcv(closes, volumes=None, spread=0.01):
    idx = pd.date_range("2023-01-01", periods=len(closes), freq="B")
    c = pd.Series(closes, index=idx, dtype=float)
    if volumes is None:
        volumes = [1_000_000] * len(closes)
    vol = pd.Series(volumes, index=idx, dtype=float)
    return pd.DataFrame({
        "Open": c,
        "High": c * (1 + spread),
        "Low": c * (1 - spread),
        "Close": c,
        "Volume": vol,
    })


def _default_config():
    return {
        "nss_ema_fast": 50,
        "nss_ema_slow": 200,
        "nss_consolidation_lookback": 15,
        "nss_breakout_lookback": 20,
        "nss_min_score": 50.0,
        "nss_exclude_swing_overlap": False,
        "nss_exclude_momentum_overlap": False,
        "nss_min_avg_traded_value_cr": 0.01,
    }


def test_diagnose_short_history_fails_at_history():
    df = _ohlcv(list(np.linspace(100, 110, 100)))
    diag = diagnose_nss(df, _default_config(), symbol="SHORT.NS")
    assert diag.failure_stage == "history"
    assert "history" in diag.modules


def test_diagnose_downtrend_fails_at_trend():
    closes = list(np.linspace(200, 100, 280))
    diag = diagnose_nss(_ohlcv(closes), _default_config(), symbol="DOWN.NS")
    assert diag.failure_stage == "trend"
    assert diag.modules["trend"].confidence == "low"


def test_diagnose_has_consolidation_submodules_on_uptrend():
    closes = list(np.linspace(80, 160, 280))
    diag = diagnose_nss(_ohlcv(closes), _default_config(), symbol="UP.NS")
    cons = diag.modules.get("consolidation")
    if cons:
        assert "trading_range" in cons.submodules


def test_waterfall_v11_has_expanded_stages():
    assert "volume_dryup" in EXPANDED_WATERFALL_ORDER
    assert "breakout_freshness" in EXPANDED_WATERFALL_ORDER


def test_waterfall_counts_granular_passed():
    diagnostics = [
        TickerDiagnostic(
            symbol="A",
            failure_stage="no_data",
            granular_passed={"has_data": False},
        ),
        TickerDiagnostic(
            symbol="B",
            granular_passed={
                "has_data": True, "history": True, "liquidity": True, "trend": True,
            },
        ),
        TickerDiagnostic(
            symbol="C",
            status="picked",
            granular_passed={
                "has_data": True, "history": True, "liquidity": True, "trend": True,
                "picked": True,
            },
        ),
    ]
    assert _count_stage(diagnostics, "has_data", 3) == 2
    assert _count_stage(diagnostics, "trend", 3) == 2
    assert _count_stage(diagnostics, "picked", 3) == 1
    wf = _build_waterfall(diagnostics, 3)
    assert wf[0].output_count == 3
    assert wf[-1].output_count == 1


def test_near_misses_include_threshold_fields():
    diagnostics = [
        TickerDiagnostic(
            symbol="X.NS",
            failure_stage="volume",
            granular_failure_stage="volume_expansion",
            failure_reason="rel_vol=1.17x",
            partial_score=58.0,
            granular_passed={"trend": True, "consolidation": True},
            score_components={"composite": 58.0},
            modules={},
        ),
    ]
    near = _near_misses(diagnostics, _default_config(), limit=5)
    assert near[0].threshold_required is not None
    assert near[0].watch_action
