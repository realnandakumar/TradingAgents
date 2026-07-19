"""Universe gate: new opens/waits must be in the allowed ticker set."""

from __future__ import annotations

import pytest

from tradingagents.tech_desk.schemas import (
    Bias,
    EntryType,
    PlanAction,
    SkipEntry,
    TechDeskBatchDecision,
    TechTradePlan,
)
from tradingagents.tech_desk.universe_gate import (
    assert_pending_paths_isolated,
    filter_decision_entries_to_universe,
    ticker_in_universe,
    universe_key_set,
)

pytestmark = pytest.mark.unit


def _wait(ticker: str) -> TechTradePlan:
    return TechTradePlan(
        ticker=ticker,
        action=PlanAction.WAIT,
        entry_type=EntryType.LIMIT_ZONE,
        zone_low=100.0,
        zone_high=105.0,
        stop_loss=95.0,
        target_1=120.0,
        confidence=70,
        bias=Bias.BULLISH,
        invalidation="Close below stop",
        rationale="test",
    )


def test_universe_keys_match_ns_and_bare():
    keys = universe_key_set(["NUVOCO.NS"])
    assert "NUVOCO.NS" in keys
    assert "NUVOCO" in keys
    assert ticker_in_universe("NUVOCO", keys)
    assert ticker_in_universe("NUVOCO.NS", keys)


def test_filter_drops_non_watchlist_waits_and_opens():
    decision = TechDeskBatchDecision(
        opens=[_wait("TCS.NS").model_copy(update={"action": PlanAction.OPEN, "entry_type": EntryType.MARKET})],
        waits=[_wait("DEEPAKNTR.NS"), _wait("INFY.NS")],
        skips=[SkipEntry(ticker="ITC.NS", reason="bearish")],
        closes=["SWIGGY.NS"],
    )
    filtered = filter_decision_entries_to_universe(
        decision,
        ["INFY.NS", "TCS.NS"],
        reason="not on current Tech Desk watchlist",
    )
    assert [p.ticker for p in filtered.opens] == ["TCS.NS"]
    assert [p.ticker for p in filtered.waits] == ["INFY.NS"]
    assert filtered.closes == ["SWIGGY.NS"]  # closes not gated
    reasons = {s.ticker: s.reason for s in filtered.skips}
    assert reasons["DEEPAKNTR.NS"] == "not on current Tech Desk watchlist"
    assert reasons["ITC.NS"] == "bearish"


def test_pending_paths_must_differ():
    assert_pending_paths_isolated(
        r"C:\a\tech_desk\pending_entries.json",
        r"C:\a\rs_desk\pending_entries.json",
    )
    with pytest.raises(ValueError):
        assert_pending_paths_isolated(
            r"C:\a\tech_desk\pending.json",
            r"C:\a\tech_desk\pending.json",
        )
