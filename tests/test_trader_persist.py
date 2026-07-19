"""Tests for trader.json persist helpers."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tradingagents.tech_desk.report_loader import TechReportSnapshot
from tradingagents.tech_desk.schemas import (
    Bias,
    EntryType,
    PlanAction,
    SkipEntry,
    TechTradePlan,
)
from tradingagents.tech_desk.trader_persist import (
    persist_trader_reports,
    render_trader_markdown,
    trader_payload_from_plan,
)


class TraderPersistTests(unittest.TestCase):
    def test_writes_json_and_md(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp) / "ACC.NS" / "2026-07-19"
            report_dir.mkdir(parents=True)
            snap = TechReportSnapshot(
                ticker="ACC.NS",
                report_date="2026-07-19",
                report_dir=report_dir,
                market_text="x",
                source_file="market.md",
                pm_summary={"stop": 1},
            )
            plan = TechTradePlan(
                ticker="ACC.NS",
                action=PlanAction.WAIT,
                entry_type=EntryType.LIMIT_ZONE,
                zone_low=95,
                zone_high=105,
                stop_loss=90,
                target_1=120,
                confidence=70,
                bias=Bias.BULLISH,
                invalidation="Below 90",
                rationale="Good R:R wait.",
            )
            saved = persist_trader_reports(
                snapshots_by_ticker={"ACC.NS": snap},
                plans=[plan],
                skips=[],
                process_date="2026-07-19",
            )
            self.assertEqual(saved, ["ACC.NS"])
            data = json.loads((report_dir / "trader.json").read_text(encoding="utf-8"))
            self.assertEqual(data["disposition"], "wait")
            self.assertEqual(data["target_1"], 120)
            self.assertIn("Tech Desk Trader", (report_dir / "trader.md").read_text(encoding="utf-8"))

    def test_skip_payload_markdown(self):
        skip = SkipEntry(ticker="TRENT.NS", reason="bearish bias")
        from tradingagents.tech_desk.trader_persist import trader_payload_from_skip

        payload = trader_payload_from_skip(skip, process_date="2026-07-19")
        md = render_trader_markdown(payload)
        self.assertIn("SKIP", md)
        self.assertIn("bearish", md)

    def test_plan_rr_in_payload(self):
        plan = TechTradePlan(
            ticker="X.NS",
            action=PlanAction.WAIT,
            entry_type=EntryType.LIMIT_ZONE,
            zone_low=95,
            zone_high=105,
            stop_loss=90,
            target_1=120,
            confidence=70,
            bias=Bias.BULLISH,
            invalidation="x",
            rationale="y",
        )
        payload = trader_payload_from_plan(plan, process_date="2026-07-19")
        self.assertAlmostEqual(payload["reward_risk"], 2.0)


if __name__ == "__main__":
    unittest.main()
