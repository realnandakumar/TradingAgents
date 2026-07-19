"""Tech Desk PM / render guards (None decision must not crash process)."""

from __future__ import annotations

import pytest

from tradingagents.tech_desk.schemas import TechDeskBatchDecision, render_batch_decision

pytestmark = pytest.mark.unit


def test_render_batch_decision_none_safe():
    text = render_batch_decision(None)
    assert "no decision" in text.lower()
    assert text.startswith("# Tech Desk Batch Decision")


def test_render_batch_decision_empty():
    text = render_batch_decision(TechDeskBatchDecision())
    assert "Tech Desk Batch Decision" in text
