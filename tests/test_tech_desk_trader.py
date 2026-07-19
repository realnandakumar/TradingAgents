"""Tests for Tech Desk Path-5 Trader validation."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tradingagents.tech_desk.agents.trader import run_tech_desk_trader
from tradingagents.tech_desk.report_loader import TechReportSnapshot
from tradingagents.tech_desk.schemas import (
    Bias,
    EntryType,
    PlanAction,
    TechDeskTraderDecision,
    TechDeskTraderDisposition,
)
from tradingagents.tech_desk.trader_validation import (
    reward_risk_from_levels,
    validate_trader_decision,
)


class RewardRiskTests(unittest.TestCase):
    def test_rr_from_zone_mid(self):
        # mid=100, stop=90, t1=120 → risk 10, reward 20 → 2.0
        rr = reward_risk_from_levels(90, 120, zone_low=95, zone_high=105)
        self.assertAlmostEqual(rr, 2.0)

    def test_rr_below_bar(self):
        # mid=100, stop=90, t1=110 → 1.0
        rr = reward_risk_from_levels(90, 110, zone_low=95, zone_high=105)
        self.assertAlmostEqual(rr, 1.0)


class ValidateTraderDecisionTests(unittest.TestCase):
    def _wait(self, **overrides) -> TechDeskTraderDecision:
        # mid=100, stop=90, t1=120 → R:R 2.0
        base = dict(
            ticker="ACC.NS",
            disposition=TechDeskTraderDisposition.WAIT,
            entry_type=EntryType.LIMIT_ZONE,
            zone_low=95.0,
            zone_high=105.0,
            stop_loss=90.0,
            target_1=120.0,
            confidence=70,
            bias=Bias.BULLISH,
            invalidation="Below 90",
            rationale="Pullback wait with 2:1 R:R.",
        )
        base.update(overrides)
        return TechDeskTraderDecision(**base)

    def test_accepts_good_rr(self):
        plan, reason = validate_trader_decision(self._wait(), min_rr=1.5)
        self.assertIsNone(reason)
        assert plan is not None
        self.assertEqual(plan.action, PlanAction.WAIT)
        self.assertEqual(plan.stop_loss, 90.0)
        self.assertEqual(plan.target_1, 120.0)

    def test_rejects_low_rr(self):
        plan, reason = validate_trader_decision(
            self._wait(target_1=110.0), min_rr=1.5
        )
        self.assertIsNone(plan)
        self.assertIn("R:R", reason or "")

    def test_rejects_bearish_long(self):
        plan, reason = validate_trader_decision(
            self._wait(bias=Bias.BEARISH), min_rr=1.5
        )
        self.assertIsNone(plan)
        self.assertIn("bearish", reason or "")

    def test_skip_disposition(self):
        d = TechDeskTraderDecision(
            ticker="ITC.NS",
            disposition=TechDeskTraderDisposition.SKIP,
            confidence=70,
            bias=Bias.BEARISH,
            rationale="No long edge.",
            skip_reason="stand aside",
        )
        plan, reason = validate_trader_decision(d, min_rr=1.5)
        self.assertIsNone(plan)
        self.assertEqual(reason, "stand aside")

    def test_rejects_when_price_already_at_t1(self):
        plan, reason = validate_trader_decision(
            self._wait(),
            min_rr=1.5,
            current_price=120.0,
        )
        self.assertIsNone(plan)
        self.assertEqual(reason, "post_target_pullback")


class RunTraderTests(unittest.TestCase):
    def test_run_trader_validates_structured_output(self):
        snap = TechReportSnapshot(
            ticker="ACC.NS",
            report_date="2026-07-19",
            report_dir=Path("."),
            market_text="## Technical Analysis\nFINAL TRANSACTION PROPOSAL: **WAIT**",
            source_file="market.md",
            pm_summary={
                "proposal": "WAIT",
                "bias": "bullish",
                "entry_zone_low": 100,
                "entry_zone_high": 105,
                "stop": 90,
                "target_1": 110,
                "confidence": 65,
            },
        )
        # Trader raises T1 to clear 1.5 R:R
        decision = TechDeskTraderDecision(
            ticker="ACC.NS",
            disposition=TechDeskTraderDisposition.WAIT,
            entry_type=EntryType.LIMIT_ZONE,
            zone_low=95.0,
            zone_high=105.0,
            stop_loss=90.0,
            target_1=120.0,
            confidence=70,
            bias=Bias.BULLISH,
            invalidation="Below 90",
            rationale="Raised T1 for R:R.",
        )
        structured = MagicMock()
        structured.invoke.return_value = decision
        llm = MagicMock()

        with patch(
            "tradingagents.tech_desk.agents.trader.bind_structured",
            return_value=structured,
        ):
            plan, skip = run_tech_desk_trader(
                llm, snap, current_price=110.0, config={"tech_desk_min_rr": 1.5}
            )

        self.assertIsNone(skip)
        assert plan is not None
        self.assertEqual(plan.target_1, 120.0)

    def test_run_trader_skips_when_validation_fails(self):
        snap = TechReportSnapshot(
            ticker="ATGL.NS",
            report_date="2026-07-19",
            report_dir=Path("."),
            market_text="report",
            source_file="market.md",
            pm_summary={"proposal": "WAIT", "bias": "bullish", "stop": 90, "target_1": 100},
        )
        decision = TechDeskTraderDecision(
            ticker="ATGL.NS",
            disposition=TechDeskTraderDisposition.WAIT,
            entry_type=EntryType.LIMIT_ZONE,
            zone_low=100.0,
            zone_high=105.0,
            stop_loss=90.0,
            target_1=110.0,  # R:R = 1.0
            confidence=70,
            bias=Bias.BULLISH,
            rationale="Weak R:R.",
        )
        structured = MagicMock()
        structured.invoke.return_value = decision
        llm = MagicMock()

        with patch(
            "tradingagents.tech_desk.agents.trader.bind_structured",
            return_value=structured,
        ):
            plan, skip = run_tech_desk_trader(
                llm, snap, current_price=108.0, config={"tech_desk_min_rr": 1.5}
            )

        self.assertIsNone(plan)
        assert skip is not None
        self.assertIn("R:R", skip.reason)


if __name__ == "__main__":
    unittest.main()
