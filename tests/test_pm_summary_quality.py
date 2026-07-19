"""Tests for pm_summary quality helpers and Process thin-report gating."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tradingagents.analysis.tech_analyze import enforce_pm_summary, save_tech_report
from tradingagents.tech_desk.process import partition_actionable_reports
from tradingagents.tech_desk.report_excerpt import (
    ensure_pm_summary_fence,
    extract_final_proposal,
    extract_pm_summary,
    is_actionable_pm_summary,
    is_stand_aside_pm_summary,
    needs_reanalyze_pm_summary,
    pm_summary_thin_reason,
)
from tradingagents.tech_desk.report_loader import TechReportSnapshot


def _rich(**overrides):
    base = {
        "proposal": "WAIT",
        "bias": "bullish",
        "confidence": 70,
        "entry_zone_low": 100.0,
        "entry_zone_high": 105.0,
        "stop": 95.0,
        "target_1": 120.0,
        "target_2": 130.0,
        "atr": 3.5,
        "sma_50": 102.0,
        "sma_200": 110.0,
        "key_support": "100",
        "key_resistance": "120",
        "invalidation": "Close below 95",
    }
    base.update(overrides)
    return base


class PmSummaryQualityTests(unittest.TestCase):
    def test_actionable_rich_summary(self):
        self.assertTrue(is_actionable_pm_summary(_rich()))
        self.assertIsNone(pm_summary_thin_reason(_rich()))

    def test_zeros_are_stand_aside_when_structured(self):
        zeros = _rich(
            entry_zone_low=0,
            entry_zone_high=0,
            stop=0,
            target_1=0,
            target_2=0,
        )
        self.assertFalse(is_actionable_pm_summary(zeros))
        self.assertTrue(is_stand_aside_pm_summary(zeros))
        self.assertIn("stand_aside", pm_summary_thin_reason(zeros) or "")

    def test_atr_only_needs_reanalyze(self):
        thin = {"atr": 10.0, "sma_50": 100.0, "sma_200": 110.0}
        self.assertFalse(is_actionable_pm_summary(thin))
        self.assertTrue(needs_reanalyze_pm_summary(thin))
        self.assertEqual(pm_summary_thin_reason(thin), "missing stop or target_1")

    def test_hold_without_zone_is_stand_aside(self):
        hold = _rich(proposal="HOLD", entry_zone_low=0, entry_zone_high=0)
        self.assertFalse(is_actionable_pm_summary(hold))
        self.assertTrue(is_stand_aside_pm_summary(hold))
        self.assertFalse(needs_reanalyze_pm_summary(hold))
        self.assertIn("stand_aside", pm_summary_thin_reason(hold) or "")

    def test_itc_style_zeros_are_stand_aside_not_reanalyze(self):
        itc = {
            "proposal": "WAIT",
            "bias": "bearish",
            "confidence": 70,
            "entry_zone_low": 0.0,
            "entry_zone_high": 0.0,
            "stop": 0.0,
            "target_1": 0.0,
            "atr": 4.01,
            "sma_50": 288.45,
        }
        self.assertTrue(is_stand_aside_pm_summary(itc))
        self.assertFalse(needs_reanalyze_pm_summary(itc))

    def test_buy_without_zone_still_actionable(self):
        buy = _rich(proposal="BUY", entry_zone_low=0, entry_zone_high=0)
        self.assertTrue(is_actionable_pm_summary(buy))

    def test_proposal_bold_styles(self):
        self.assertEqual(
            extract_final_proposal("FINAL TRANSACTION PROPOSAL: **HOLD**"),
            "HOLD",
        )
        self.assertEqual(
            extract_final_proposal("**FINAL TRANSACTION PROPOSAL: WAIT**"),
            "WAIT",
        )

    def test_ensure_fence_appends_and_replaces(self):
        body = "## Technical Analysis\n\nSome prose."
        with_fence = ensure_pm_summary_fence(body, _rich())
        self.assertIn("```json pm_summary", with_fence)
        self.assertIn('"stop": 95.0', with_fence)
        replaced = ensure_pm_summary_fence(with_fence, _rich(stop=90.0))
        self.assertEqual(replaced.count("```json pm_summary"), 1)
        self.assertIn('"stop": 90.0', replaced)
        summary = extract_pm_summary(replaced)
        self.assertEqual(summary["stop"], 90.0)


class EnforcePmSummaryTests(unittest.TestCase):
    def test_enforce_skips_llm_when_already_actionable(self):
        report = (
            "## Technical Analysis\n\n"
            "FINAL TRANSACTION PROPOSAL: **WAIT**\n\n"
            + ensure_pm_summary_fence("", _rich())
        )
        llm = MagicMock()
        out, summary, thin = enforce_pm_summary(report, llm=llm, ticker="TCS.NS")
        self.assertIsNone(thin)
        self.assertTrue(is_actionable_pm_summary(summary))
        llm.invoke.assert_not_called()
        self.assertIn("pm_summary", out)

    def test_enforce_fills_from_structured_llm(self):
        from tradingagents.tech_desk.schemas import PmSummary

        thin_report = (
            "## Technical Analysis\n\n"
            "Pullback zone 100-105, stop 95, target 120.\n"
            "FINAL TRANSACTION PROPOSAL: **WAIT**\n"
        )
        filled = PmSummary(
            proposal="WAIT",
            bias="bullish",
            confidence=70,
            entry_zone_low=100.0,
            entry_zone_high=105.0,
            stop=95.0,
            target_1=120.0,
            target_2=130.0,
            atr=3.5,
            sma_50=102.0,
            sma_200=110.0,
            key_support="100",
            key_resistance="120",
            invalidation="Close below 95",
        )
        structured = MagicMock()
        structured.invoke.return_value = filled
        llm = MagicMock()

        with patch(
            "tradingagents.analysis.tech_analyze.bind_structured",
            return_value=structured,
        ):
            out, summary, thin = enforce_pm_summary(
                thin_report, llm=llm, ticker="ACC.NS"
            )

        self.assertIsNone(thin)
        self.assertEqual(summary["stop"], 95.0)
        self.assertIn('"stop": 95.0', out)
        structured.invoke.assert_called_once()

    def test_save_writes_pm_summary_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            save_path = Path(tmp) / "TCS.NS" / "2026-07-19"
            result = {
                "ticker": "TCS.NS",
                "trade_date": "2026-07-19",
                "market_report": ensure_pm_summary_fence("## Report", _rich()),
                "pm_summary": _rich(),
            }
            save_tech_report(result, save_path)
            self.assertTrue((save_path / "pm_summary.json").exists())
            text = (save_path / "pm_summary.json").read_text(encoding="utf-8")
            self.assertIn('"stop": 95.0', text)


class PartitionActionableTests(unittest.TestCase):
    def test_partition_splits_thin_and_rich(self):
        rich = TechReportSnapshot(
            ticker="TCS.NS",
            report_date="2026-07-16",
            report_dir=Path("."),
            market_text="x",
            source_file="market.md",
            pm_summary=_rich(),
        )
        thin = TechReportSnapshot(
            ticker="ACC.NS",
            report_date="2026-07-12",
            report_dir=Path("."),
            market_text="x",
            source_file="market.md",
            pm_summary={"atr": 10.0, "sma_50": 1.0},
        )
        aside = TechReportSnapshot(
            ticker="ITC.NS",
            report_date="2026-07-19",
            report_dir=Path("."),
            market_text="x",
            source_file="market.md",
            pm_summary={
                "proposal": "WAIT",
                "bias": "bearish",
                "atr": 4.0,
                "stop": 0,
                "target_1": 0,
            },
        )
        actionable, stand_aside, thin_list = partition_actionable_reports(
            [rich, thin, aside]
        )
        self.assertEqual([s.ticker for s in actionable], ["TCS.NS"])
        self.assertEqual(len(thin_list), 1)
        self.assertEqual(thin_list[0]["ticker"], "ACC.NS")
        self.assertIn("stop", thin_list[0]["reason"])
        self.assertEqual(len(stand_aside), 1)
        self.assertEqual(stand_aside[0]["ticker"], "ITC.NS")


class ProcessThinGateTests(unittest.TestCase):
    @patch("tradingagents.tech_desk.process.load_watchlist")
    @patch("tradingagents.tech_desk.process.create_llm_client")
    @patch("tradingagents.tech_desk.process.load_tech_reports")
    @patch("tradingagents.tech_desk.process.TechDeskPaperTradeManager")
    def test_process_skips_all_thin_without_opens(
        self, mock_mgr_cls, mock_load, mock_llm, mock_wl
    ):
        from tradingagents.tech_desk.process import run_tech_desk_process

        mock_wl.return_value = ["ACC.NS"]
        mock_load.return_value = (
            [
                TechReportSnapshot(
                    ticker="ACC.NS",
                    report_date="2026-07-12",
                    report_dir=Path("."),
                    market_text="thin",
                    source_file="market.md",
                    pm_summary={"atr": 1.0},
                )
            ],
            [],
        )
        book = MagicMock()
        book.positions = []
        book.pending_path = Path("/tmp/pending.json")
        mgr = MagicMock()
        mgr.book = book
        mgr.max_positions = 10
        mock_mgr_cls.return_value = mgr

        with tempfile.TemporaryDirectory() as tmp:
            result = run_tech_desk_process(
                {
                    "tech_analyze_reports_dir": "/tmp",
                    "tech_desk_book_path": str(Path(tmp) / "positions.json"),
                    "tech_desk_pending_path": str(Path(tmp) / "pending.json"),
                    "llm_provider": "openai",
                    "quick_think_llm": "gpt-test",
                }
            )

        self.assertTrue(result["skipped"])
        self.assertEqual(result["reason"], "no_actionable_reports")
        self.assertEqual(len(result["thin_reports"]), 1)
        mock_llm.assert_not_called()


if __name__ == "__main__":
    unittest.main()
