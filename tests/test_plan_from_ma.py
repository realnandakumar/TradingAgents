"""Tests: Market Analyst pm_summary → TechTradePlan (SL / T1 / buying zone)."""

from __future__ import annotations

import unittest

from tradingagents.tech_desk.plan_from_ma import (
    batch_decision_from_ma_snapshots,
    trade_plan_from_pm_summary,
)
from tradingagents.tech_desk.report_loader import TechReportSnapshot
from tradingagents.tech_desk.schemas import EntryType, PlanAction
from pathlib import Path


def _buy_summary(**overrides):
    base = {
        "proposal": "BUY",
        "bias": "bullish",
        "confidence": 72,
        "entry_zone_low": 100.0,
        "entry_zone_high": 105.0,
        "stop": 95.0,
        "target_1": 120.0,
        "target_2": 130.0,
        "invalidation": "Close below 95",
    }
    base.update(overrides)
    return base


class PlanFromMaTests(unittest.TestCase):
    def test_buy_in_zone_opens_market_with_sl_t1_zone(self):
        plan, reason = trade_plan_from_pm_summary(
            "ABC.NS", _buy_summary(), current_price=102.0
        )
        self.assertIsNone(reason)
        assert plan is not None
        self.assertEqual(plan.action, PlanAction.OPEN)
        self.assertEqual(plan.entry_type, EntryType.MARKET)
        self.assertEqual(plan.stop_loss, 95.0)
        self.assertEqual(plan.target_1, 120.0)
        self.assertEqual(plan.target_2, 130.0)
        self.assertEqual(plan.zone_low, 100.0)
        self.assertEqual(plan.zone_high, 105.0)
        self.assertEqual(plan.confidence, 72)

    def test_buy_above_zone_waits_limit_zone_anti_chase(self):
        plan, reason = trade_plan_from_pm_summary(
            "ABC.NS", _buy_summary(), current_price=112.0
        )
        self.assertIsNone(reason)
        assert plan is not None
        self.assertEqual(plan.action, PlanAction.WAIT)
        self.assertEqual(plan.entry_type, EntryType.LIMIT_ZONE)
        self.assertEqual(plan.stop_loss, 95.0)
        self.assertEqual(plan.target_1, 120.0)
        self.assertEqual(plan.zone_low, 100.0)
        self.assertEqual(plan.zone_high, 105.0)

    def test_hold_with_zone_waits(self):
        plan, reason = trade_plan_from_pm_summary(
            "ABC.NS",
            _buy_summary(proposal="HOLD"),
            current_price=110.0,
        )
        self.assertIsNone(reason)
        assert plan is not None
        self.assertEqual(plan.action, PlanAction.WAIT)
        self.assertEqual(plan.entry_type, EntryType.LIMIT_ZONE)

    def test_wait_proposal_same_as_hold(self):
        plan, reason = trade_plan_from_pm_summary(
            "ABC.NS",
            _buy_summary(proposal="WAIT"),
            current_price=110.0,
        )
        self.assertIsNone(reason)
        assert plan is not None
        self.assertEqual(plan.action, PlanAction.WAIT)

    def test_sell_skipped(self):
        plan, reason = trade_plan_from_pm_summary(
            "ABC.NS", _buy_summary(proposal="SELL"), current_price=102.0
        )
        self.assertIsNone(plan)
        self.assertIn("SELL", reason or "")

    def test_missing_stop_or_target_skipped(self):
        # zeros become None via _num
        plan, reason = trade_plan_from_pm_summary(
            "ABC.NS",
            _buy_summary(stop=0, target_1=0),
            current_price=102.0,
        )
        self.assertIsNone(plan)
        self.assertIn("missing stop", reason or "")

    def test_hold_without_zone_skipped(self):
        plan, reason = trade_plan_from_pm_summary(
            "ABC.NS",
            {
                "proposal": "HOLD",
                "stop": 95.0,
                "target_1": 120.0,
                "confidence": 70,
            },
            current_price=102.0,
        )
        self.assertIsNone(plan)
        self.assertIn("without entry zone", reason or "")

    def test_invalid_levels_buy_skipped(self):
        plan, reason = trade_plan_from_pm_summary(
            "ABC.NS",
            _buy_summary(stop=110.0, target_1=105.0, entry_zone_low=None, entry_zone_high=None),
            current_price=102.0,
        )
        self.assertIsNone(plan)
        self.assertIn("invalid", (reason or "").lower())

    def test_batch_decision_splits_open_wait_skip(self):
        snaps = [
            TechReportSnapshot(
                ticker="OPEN.NS",
                report_date="2026-07-16",
                report_dir=Path("."),
                market_text="",
                source_file="market.md",
                pm_summary=_buy_summary(),
            ),
            TechReportSnapshot(
                ticker="WAIT.NS",
                report_date="2026-07-16",
                report_dir=Path("."),
                market_text="",
                source_file="market.md",
                pm_summary=_buy_summary(proposal="HOLD"),
            ),
            TechReportSnapshot(
                ticker="SKIP.NS",
                report_date="2026-07-16",
                report_dir=Path("."),
                market_text="",
                source_file="market.md",
                pm_summary=_buy_summary(proposal="SELL"),
            ),
        ]
        decision = batch_decision_from_ma_snapshots(
            snaps,
            {"OPEN.NS": 102.0, "WAIT.NS": 110.0, "SKIP.NS": 102.0},
        )
        self.assertEqual([p.ticker for p in decision.opens], ["OPEN.NS"])
        self.assertEqual([p.ticker for p in decision.waits], ["WAIT.NS"])
        self.assertEqual([s.ticker for s in decision.skips], ["SKIP.NS"])
        open_plan = decision.opens[0]
        self.assertEqual(open_plan.stop_loss, 95.0)
        self.assertEqual(open_plan.target_1, 120.0)
        self.assertEqual(open_plan.zone_low, 100.0)


if __name__ == "__main__":
    unittest.main()
