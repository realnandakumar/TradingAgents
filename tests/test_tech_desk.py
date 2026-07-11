"""Tests for Tech Desk paper trading."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

from tradingagents.analysis.tech_analyze import strip_market_report_preamble
from tradingagents.paper.sizing import compute_position_size
from tradingagents.tech_desk.book import TechDeskPositionBook
from tradingagents.tech_desk.exits import zone_fill_price
from tradingagents.tech_desk.manager import TechDeskPaperTradeManager
from tradingagents.tech_desk.report_loader import load_tech_reports
from tradingagents.tech_desk.schemas import (
    Bias,
    EntryType,
    PlanAction,
    PositionReviewAction,
    PositionReviewItem,
    SkipEntry,
    TechDeskBatchDecision,
    TechDeskPositionReview,
    TechTradePlan,
)


def _sample_plan(
    ticker: str = "RELIANCE.NS",
    confidence: int = 75,
    entry: float = 2500.0,
) -> TechTradePlan:
    return TechTradePlan(
        ticker=ticker,
        action=PlanAction.OPEN,
        entry_type=EntryType.MARKET,
        stop_loss=round(entry * 0.96, 2),
        target_1=round(entry * 1.08, 2),
        target_2=round(entry * 1.12, 2),
        holding_days=15,
        confidence=confidence,
        bias=Bias.BULLISH,
        invalidation="Close below stop",
        rationale="Uptrend pullback complete.",
    )


class ReportLoaderTests(unittest.TestCase):
    def test_latest_per_ticker_dedup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = root / "RELIANCE.NS" / "2026-07-01"
            new = root / "RELIANCE.NS" / "2026-07-10"
            old.mkdir(parents=True)
            new.mkdir(parents=True)
            (old / "market.md").write_text("old report", encoding="utf-8")
            (new / "market.md").write_text("new report", encoding="utf-8")

            tcs = root / "TCS.NS" / "2026-07-05"
            tcs.mkdir(parents=True)
            (tcs / "complete_report.md").write_text("tcs report", encoding="utf-8")

            snaps, stale = load_tech_reports(root)
            by_ticker = {s.ticker: s for s in snaps}
            self.assertEqual(len(snaps), 2)
            self.assertEqual(stale, [])
            self.assertEqual(by_ticker["RELIANCE.NS"].market_text, "new report")
            self.assertEqual(by_ticker["RELIANCE.NS"].report_date, "2026-07-10")
            self.assertEqual(by_ticker["TCS.NS"].market_text, "tcs report")

    def test_stale_reports_excluded(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = root / "RELIANCE.NS" / "2026-06-01"
            old.mkdir(parents=True)
            (old / "market.md").write_text("stale", encoding="utf-8")

            snaps, stale = load_tech_reports(
                root, max_report_age_days=14, as_of="2026-07-10"
            )
            self.assertEqual(snaps, [])
            self.assertIn("RELIANCE.NS", stale)

    def test_report_path_property(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            d = root / "TCS.NS" / "2026-07-10"
            d.mkdir(parents=True)
            (d / "market.md").write_text("body", encoding="utf-8")
            snaps, _ = load_tech_reports(root)
            self.assertTrue(snaps[0].report_path.endswith("market.md"))


class MetaStripTests(unittest.TestCase):
    def test_strip_preamble_before_heading(self):
        raw = (
            "Now I have all the data I need.\n\n"
            "## Technical Analysis\n\n"
            "RSI is bullish."
        )
        cleaned = strip_market_report_preamble(raw)
        self.assertTrue(cleaned.startswith("## Technical Analysis"))
        self.assertNotIn("Now I have all the data", cleaned)

    def test_strip_leading_non_heading_lines(self):
        raw = "Let me analyze the chart.\n\n# RELIANCE\n\nBullish."
        cleaned = strip_market_report_preamble(raw)
        self.assertTrue(cleaned.startswith("# RELIANCE"))


class TechDeskBookTests(unittest.TestCase):
    def _config(self, tmp: str) -> dict:
        base = Path(tmp) / "tech_desk"
        return {
            "desk_capital": 100_000.0,
            "tech_desk_max_positions": 10,
            "tech_desk_min_confidence": 60,
            "tech_desk_holding_days": 20,
            "tech_desk_book_path": str(base / "positions.json"),
            "tech_desk_pending_path": str(base / "pending.json"),
        }

    def test_open_whole_share_sizing(self):
        with tempfile.TemporaryDirectory() as tmp:
            book = TechDeskPositionBook(self._config(tmp))
            plan = _sample_plan()
            pos = book.open_from_plan(plan, entry_price=2500.0, screen_date="2026-07-10")
            self.assertIsNotNone(pos)
            assert pos is not None
            expected = compute_position_size(100_000.0, 10, 2500.0)
            self.assertEqual(pos["shares"], expected["shares"])
            self.assertIsInstance(pos["shares"], int)
            self.assertEqual(pos["shares"], max(1, round(10_000 / 2500)))

    def test_rejects_low_confidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            book = TechDeskPositionBook(self._config(tmp))
            plan = _sample_plan(confidence=40)
            pos = book.open_from_plan(plan, entry_price=2500.0, screen_date="2026-07-10")
            self.assertIsNone(pos)

    def test_open_stores_report_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            book = TechDeskPositionBook(self._config(tmp))
            plan = _sample_plan()
            pos = book.open_from_plan(
                plan,
                entry_price=2500.0,
                screen_date="2026-07-10",
                report_path="/tmp/TCS/market.md",
                report_date="2026-07-10",
            )
            self.assertIsNotNone(pos)
            assert pos is not None
            self.assertEqual(pos["report_path"], "/tmp/TCS/market.md")
            self.assertEqual(pos["report_date"], "2026-07-10")

    def test_open_stores_report_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            book = TechDeskPositionBook(self._config(tmp))
            plan = _sample_plan()
            pos = book.open_from_plan(
                plan,
                entry_price=2500.0,
                screen_date="2026-07-10",
                report_path="/tmp/TCS/market.md",
                report_date="2026-07-10",
            )
            self.assertIsNotNone(pos)
            assert pos is not None
            self.assertEqual(pos["report_path"], "/tmp/TCS/market.md")
            self.assertEqual(pos["report_date"], "2026-07-10")


class ZoneFillTests(unittest.TestCase):
    def test_zone_fill_when_bar_overlaps(self):
        bar = pd.Series({"Low": 99.0, "High": 101.0, "Close": 100.0})
        self.assertEqual(zone_fill_price(bar, 98.0, 102.0), 100.0)

    def test_no_fill_when_bar_misses_zone(self):
        bar = pd.Series({"Low": 110.0, "High": 115.0, "Close": 112.0})
        self.assertIsNone(zone_fill_price(bar, 98.0, 102.0))

    def test_pending_zone_fill_opens_position(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = {
                "desk_capital": 100_000.0,
                "tech_desk_max_positions": 10,
                "tech_desk_min_confidence": 60,
                "tech_desk_book_path": str(Path(tmp) / "positions.json"),
                "tech_desk_pending_path": str(Path(tmp) / "pending.json"),
            }
            book = TechDeskPositionBook(cfg)
            plan = _sample_plan("TCS.NS", entry=100.0)
            plan = plan.model_copy(
                update={
                    "entry_type": EntryType.LIMIT_ZONE,
                    "zone_low": 98.0,
                    "zone_high": 102.0,
                    "stop_loss": 95.0,
                    "target_1": 110.0,
                }
            )
            book.add_pending_entry(plan, "2026-07-10")

            bar = pd.Series({"Low": 99.0, "High": 101.0, "Close": 100.0})

            with patch.object(TechDeskPositionBook, "_history") as mock_hist:
                mock_hist.return_value = pd.DataFrame(
                    [bar],
                    index=pd.to_datetime(["2026-07-10"]),
                )
                fills = book.evaluate_pending_fills(as_of="2026-07-10")

            self.assertEqual(len(fills), 1)
            self.assertTrue(book.has_open_position("TCS.NS"))
            self.assertEqual(book.pending_entries(), [])


class ProcessBatchTests(unittest.TestCase):
    def test_process_batch_mock_pm(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = {
                "desk_capital": 100_000.0,
                "tech_desk_max_positions": 2,
                "tech_desk_min_confidence": 60,
                "tech_desk_book_path": str(Path(tmp) / "positions.json"),
                "tech_desk_pending_path": str(Path(tmp) / "pending.json"),
                "tech_desk_process_log_dir": str(Path(tmp) / "process"),
            }
            manager = TechDeskPaperTradeManager(cfg)

            decision = TechDeskBatchDecision(
                opens=[
                    _sample_plan("RELIANCE.NS", entry=2500.0),
                    _sample_plan("TCS.NS", entry=3500.0),
                ],
                waits=[],
                skips=[SkipEntry(ticker="INFY.NS", reason="extended")],
                closes=[],
            )
            prices = {"RELIANCE.NS": 2500.0, "TCS.NS": 3500.0}

            report = manager.process_batch(decision, prices, process_date="2026-07-10")
            self.assertEqual(len(report["opened"]), 2)
            self.assertEqual(manager.book.open_count(), 2)

            # Third open should foreclose weakest when full
            decision2 = TechDeskBatchDecision(
                opens=[_sample_plan("HDFCBANK.NS", entry=1600.0)],
                waits=[],
                skips=[],
                closes=[],
            )
            with patch.object(TechDeskPaperTradeManager, "_weakest_open") as mock_weak:
                mock_weak.return_value = manager.book.positions[0]
                with patch.object(
                    TechDeskPositionBook, "latest_price", return_value=2480.0
                ):
                    report2 = manager.process_batch(
                        decision2,
                        {"HDFCBANK.NS": 1600.0},
                        process_date="2026-07-11",
                    )
            self.assertEqual(len(report2["foreclosures"]), 1)
            self.assertIn("HDFCBANK.NS", report2["opened"])


class ProcessOrchestrationTests(unittest.TestCase):
    @patch("tradingagents.tech_desk.process.create_llm_client")
    @patch("tradingagents.tech_desk.process.load_tech_reports")
    def test_run_process_no_reports(self, mock_load, mock_llm):
        from tradingagents.tech_desk.process import run_tech_desk_process

        mock_load.return_value = ([], [])
        result = run_tech_desk_process({"tech_analyze_reports_dir": "/tmp"})
        self.assertTrue(result["skipped"])
        self.assertEqual(result["reason"], "no_reports")
        mock_llm.assert_not_called()


class ApplyReviewTests(unittest.TestCase):
    def test_apply_review_closes_and_raises_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = {
                "desk_capital": 100_000.0,
                "tech_desk_max_positions": 10,
                "tech_desk_min_confidence": 60,
                "tech_desk_book_path": str(Path(tmp) / "positions.json"),
                "tech_desk_pending_path": str(Path(tmp) / "pending.json"),
            }
            manager = TechDeskPaperTradeManager(cfg)
            plan = _sample_plan("RELIANCE.NS", entry=100.0)
            manager.book.open_from_plan(plan, 100.0, "2026-07-01")

            review = TechDeskPositionReview(
                summary="Rotate weak name.",
                reviews=[
                    PositionReviewItem(
                        ticker="RELIANCE.NS",
                        action=PositionReviewAction.CLOSE,
                        rationale="Thesis broken.",
                    ),
                ],
            )
            with patch.object(TechDeskPositionBook, "latest_price", return_value=98.0):
                applied = manager.apply_review(review, as_of="2026-07-10")
            self.assertIn("RELIANCE.NS", applied["closed"])
            self.assertFalse(manager.book.has_open_position("RELIANCE.NS"))


if __name__ == "__main__":
    unittest.main()
