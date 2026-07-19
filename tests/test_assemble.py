"""Tests for script portfolio assemble (daily PM replacement)."""

from __future__ import annotations

import unittest

from tradingagents.tech_desk.assemble import assemble_decision_from_traders
from tradingagents.tech_desk.schemas import (
    Bias,
    EntryType,
    PlanAction,
    SkipEntry,
    TechTradePlan,
)


def _plan(
    ticker: str,
    *,
    action: PlanAction = PlanAction.OPEN,
    conf: int = 70,
    zone: bool = True,
) -> TechTradePlan:
    return TechTradePlan(
        ticker=ticker,
        action=action,
        entry_type=EntryType.LIMIT_ZONE if zone else EntryType.MARKET,
        zone_low=95.0 if zone else None,
        zone_high=105.0 if zone else None,
        stop_loss=90.0,
        target_1=120.0,
        confidence=conf,
        bias=Bias.BULLISH,
        invalidation="Below 90",
        rationale="test",
    )


class AssembleDecisionTests(unittest.TestCase):
    def test_ranks_opens_and_caps_slots(self):
        plans = [
            _plan("A.NS", conf=60),
            _plan("B.NS", conf=80),
            _plan("C.NS", conf=70),
        ]
        decision = assemble_decision_from_traders(plans, [], slots_available=2)
        self.assertEqual([p.ticker for p in decision.opens], ["B.NS", "C.NS"])
        # A demoted to wait (has zone)
        self.assertEqual(len(decision.waits), 1)
        self.assertEqual(decision.waits[0].ticker, "A.NS")
        self.assertEqual(decision.waits[0].action, PlanAction.WAIT)
        self.assertEqual(decision.closes, [])

    def test_overflow_without_zone_is_skipped(self):
        plans = [
            _plan("A.NS", conf=90, zone=False),
            _plan("B.NS", conf=80, zone=False),
        ]
        decision = assemble_decision_from_traders(plans, [], slots_available=1)
        self.assertEqual([p.ticker for p in decision.opens], ["A.NS"])
        self.assertEqual(len(decision.waits), 0)
        self.assertTrue(any(s.ticker == "B.NS" for s in decision.skips))

    def test_keeps_trader_waits_and_skips(self):
        plans = [
            _plan("W.NS", action=PlanAction.WAIT, conf=65),
            _plan("O.NS", action=PlanAction.OPEN, conf=75),
        ]
        skips = [SkipEntry(ticker="S.NS", reason="low R:R")]
        decision = assemble_decision_from_traders(
            plans, skips, slots_available=5, extra_skips=[]
        )
        self.assertEqual(len(decision.opens), 1)
        self.assertEqual(decision.opens[0].ticker, "O.NS")
        self.assertEqual(len(decision.waits), 1)
        self.assertEqual(decision.waits[0].ticker, "W.NS")
        self.assertTrue(any(s.ticker == "S.NS" for s in decision.skips))

    def test_no_closes_from_script_pm(self):
        decision = assemble_decision_from_traders(
            [_plan("X.NS")], [], slots_available=0
        )
        self.assertEqual(decision.closes, [])
        self.assertEqual(decision.opens, [])
        self.assertEqual(decision.waits[0].ticker, "X.NS")


if __name__ == "__main__":
    unittest.main()
