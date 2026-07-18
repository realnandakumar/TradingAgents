"""Parity checks for shared candle rule thresholds (Python ↔ dashboard)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tradingagents.screening.candle_engine import load_candle_rules

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[1]
PY_RULES = REPO_ROOT / "tradingagents" / "screening" / "candle_rules.json"
TS_RULES = REPO_ROOT / "dashboard" / "lib" / "candle_rules.json"


def test_candle_rules_files_match():
    py = json.loads(PY_RULES.read_text(encoding="utf-8"))
    ts = json.loads(TS_RULES.read_text(encoding="utf-8"))
    assert py == ts


def test_load_candle_rules_matches_file():
    assert load_candle_rules() == json.loads(PY_RULES.read_text(encoding="utf-8"))
