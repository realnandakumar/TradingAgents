"""Tests for strict paper-book JSON dumps."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from tradingagents.paper.json_store import dump_json, sanitize_for_json

pytestmark = pytest.mark.unit


def test_sanitize_replaces_nan_and_inf():
    cleaned = sanitize_for_json({"a": float("nan"), "b": [{"c": math.inf}]})
    assert cleaned == {"a": None, "b": [{"c": None}]}


def test_dump_json_is_strict(tmp_path: Path):
    path = tmp_path / "book.json"
    dump_json(path, {"exit_price": float("nan"), "pnl": 1.5})
    raw = path.read_text(encoding="utf-8")
    assert "NaN" not in raw
    data = json.loads(raw)
    assert data["exit_price"] is None
    assert data["pnl"] == 1.5


def test_aggregate_skips_nan_returns():
    from tradingagents.paper.json_store import aggregate_closed_trades

    stats = aggregate_closed_trades(
        [
            {"outcome": "success", "raw_return": 0.1, "alpha_return": 0.05, "rupee_pnl": 10},
            {"outcome": "fail", "raw_return": float("nan"), "alpha_return": float("nan"), "rupee_pnl": float("nan")},
        ]
    )
    assert stats["trades"] == 2
    assert stats["avg_return"] == 10.0
    assert stats["avg_alpha"] == 5.0
    assert stats["total_pnl"] == 10.0
