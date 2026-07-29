"""Tests for the EOD manifest-stamp gate in scripts/run_eod_pipeline.py."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_eod_pipeline.py"


def _load_pipeline():
    spec = importlib.util.spec_from_file_location("run_eod_pipeline", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def pipeline():
    return _load_pipeline()


def _config(**overrides):
    cfg = {"screen_benchmark": "^NSEI", "eod_sync_failure_tolerance": 5}
    cfg.update(overrides)
    return cfg


def test_clean_sync_has_no_blockers(pipeline):
    sync = {"synced": 502, "skipped": 0, "failed": 0, "failed_symbols": []}
    assert pipeline._stamp_blockers(sync, _config()) == []


def test_skipped_sync_step_has_no_blockers(pipeline):
    """When price sync is skipped entirely there is nothing to block on."""
    sync = {"skipped": True, "reason": "eod_ran_today"}
    assert pipeline._stamp_blockers(sync, _config()) == []


def test_few_failed_symbols_still_stamp(pipeline):
    """A suspended ticker must not make the dashboard report EOD never ran."""
    sync = {"synced": 500, "failed": 2, "failed_symbols": ["DEAD.NS", "HALT.NS"]}
    assert pipeline._stamp_blockers(sync, _config()) == []


def test_failed_benchmark_blocks_stamp(pipeline):
    """The benchmark drives relative strength and alpha, so it is never optional."""
    sync = {"synced": 501, "failed": 1, "failed_symbols": ["^NSEI"]}
    blockers = pipeline._stamp_blockers(sync, _config())
    assert len(blockers) == 1
    assert "^NSEI" in blockers[0]


def test_broad_outage_blocks_stamp(pipeline):
    failed = [f"SYM{i}.NS" for i in range(40)]
    sync = {"synced": 20, "failed": len(failed), "failed_symbols": failed}
    blockers = pipeline._stamp_blockers(sync, _config())
    assert len(blockers) == 1
    assert "tolerance 5" in blockers[0]


def test_tolerance_is_configurable(pipeline):
    sync = {"synced": 500, "failed": 2, "failed_symbols": ["A.NS", "B.NS"]}
    assert pipeline._stamp_blockers(sync, _config(eod_sync_failure_tolerance=1))
    assert not pipeline._stamp_blockers(sync, _config(eod_sync_failure_tolerance=2))
