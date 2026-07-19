"""RS Desk: config overlay, Path-5 process, shared post-T1 lifecycle."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd

from tradingagents.rs_desk.config_overlay import as_tech_desk_config
from tradingagents.rs_desk.daily import run_rs_desk_daily
from tradingagents.rs_desk.process import run_rs_desk_process
from tradingagents.tech_desk.book import TechDeskPositionBook
from tradingagents.tech_desk.pending_lifecycle import (
    is_setup_exhausted,
    peak_history_start,
    post_target_entry_block_reason,
)
from tradingagents.tech_desk.plan_from_ma import trade_plan_from_pm_summary
from tradingagents.tech_desk.schemas import (
    Bias,
    EntryType,
    PlanAction,
    TechTradePlan,
)


def _rs_paths(tmp: str) -> dict:
    root = Path(tmp)
    return {
        "rs_desk_book_path": str(root / "rs_desk" / "positions.json"),
        "rs_desk_pending_path": str(root / "rs_desk" / "pending_entries.json"),
        "rs_desk_pending_dismissed_path": str(root / "rs_desk" / "pending_dismissed.json"),
        "rs_desk_closed_history_path": str(root / "rs_desk" / "closed_history.json"),
        "rs_desk_daily_dir": str(root / "rs_desk" / "daily"),
        "rs_desk_process_log_dir": str(root / "rs_desk" / "process"),
        "tech_desk_book_path": str(root / "tech_desk" / "positions.json"),
        "tech_desk_pending_path": str(root / "tech_desk" / "pending.json"),
        "desk_capital": 200_000.0,
        "rs_desk_max_positions": 20,
        "tech_analyze_reports_dir": str(root / "tech_reports"),
        "llm_provider": "openai",
        "quick_think_llm": "gpt-4o-mini",
    }


class RsDeskOverlayTests(unittest.TestCase):
    def test_overlay_points_at_rs_paths_not_tech_desk(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _rs_paths(tmp)
            overlay = as_tech_desk_config(cfg)
            self.assertEqual(overlay["tech_desk_book_path"], cfg["rs_desk_book_path"])
            self.assertNotEqual(overlay["tech_desk_book_path"], cfg["tech_desk_book_path"])
            self.assertEqual(
                overlay["tech_desk_pending_path"], cfg["rs_desk_pending_path"]
            )
            self.assertEqual(overlay["tech_desk_strategy_name"], "rs_desk")
            self.assertEqual(
                overlay["tech_analyze_reports_dir"], cfg["tech_analyze_reports_dir"]
            )

            rs_book = TechDeskPositionBook(overlay)
            tech_book = TechDeskPositionBook(
                {
                    **cfg,
                    "tech_desk_book_path": cfg["tech_desk_book_path"],
                    "tech_desk_pending_path": cfg["tech_desk_pending_path"],
                    "tech_desk_pending_dismissed_path": str(
                        Path(tmp) / "tech_desk" / "dismissed.json"
                    ),
                    "tech_desk_strategy_name": "tech_desk",
                }
            )
            self.assertEqual(rs_book.strategy_name, "rs_desk")
            self.assertEqual(tech_book.strategy_name, "tech_desk")
            self.assertNotEqual(rs_book.path, tech_book.path)
            self.assertNotEqual(rs_book.pending_path, tech_book.pending_path)

    def test_overlay_maps_t1_lookback_and_min_rr(self):
        overlay = as_tech_desk_config(
            {
                "rs_desk_t1_lookback_days": 30,
                "rs_desk_min_rr": 2.0,
                "rs_desk_target_path_skip_pct": 0.75,
                "rs_desk_pending_max_days": 7,
            }
        )
        self.assertEqual(overlay["tech_desk_t1_lookback_days"], 30)
        self.assertEqual(overlay["tech_desk_min_rr"], 2.0)
        self.assertEqual(overlay["tech_desk_target_path_skip_pct"], 0.75)
        self.assertEqual(overlay["tech_desk_pending_max_days"], 7)

    def test_peak_history_start_uses_rs_lookback(self):
        overlay = as_tech_desk_config({"rs_desk_t1_lookback_days": 10})
        start = peak_history_start(
            {"report_date": "2026-07-19", "plan_date": "2026-07-19"},
            overlay,
        )
        self.assertEqual(start, "2026-07-09")

    def test_ma_levels_still_convert_for_rs_preview(self):
        """Batch-runner MA preview only — Path-5 execution uses Trader, not this."""
        plan, reason = trade_plan_from_pm_summary(
            "ABC.NS",
            {
                "proposal": "BUY",
                "stop": 95.0,
                "target_1": 120.0,
                "entry_zone_low": 100.0,
                "entry_zone_high": 105.0,
                "confidence": 70,
                "bias": "bullish",
            },
            102.0,
        )
        self.assertIsNone(reason)
        assert plan is not None
        self.assertEqual(plan.action, PlanAction.OPEN)
        self.assertEqual(plan.entry_type, EntryType.MARKET)
        self.assertEqual(plan.stop_loss, 95.0)
        self.assertEqual(plan.zone_high, 105.0)


class RsDeskPostTargetTests(unittest.TestCase):
    """Shared pending_lifecycle via RS overlay config."""

    def test_t1_achieved_blocks_pending_on_rs_book(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = _rs_paths(tmp)
            overlay = as_tech_desk_config(cfg)
            book = TechDeskPositionBook(overlay)
            plan = TechTradePlan(
                ticker="ACC.NS",
                action=PlanAction.WAIT,
                entry_type=EntryType.LIMIT_ZONE,
                zone_low=98.0,
                zone_high=100.0,
                stop_loss=95.0,
                target_1=110.0,
                confidence=70,
                bias=Bias.BULLISH,
                invalidation="Below 95",
                rationale="Wait pullback",
            )
            hist = pd.DataFrame(
                {
                    "High": [112.0, 99.5],
                    "Low": [108.0, 98.0],
                    "Close": [110.0, 99.0],
                },
                index=pd.to_datetime(["2026-07-11", "2026-07-15"]),
            )
            err = book.validate_pending_plan(plan, current_price=99.0, hist=hist)
            self.assertEqual(err, "post_target_pullback")

            with patch.object(book, "history_for_setup_check", return_value=hist):
                row = book.add_pending_entry(
                    plan,
                    "2026-07-15",
                    report_date="2026-07-10",
                    current_price=99.0,
                    hist=hist,
                )
            self.assertIsNone(row)
            self.assertTrue(book.is_pending_dismissed("ACC.NS", "2026-07-10"))

    def test_exhaustion_hard_t1_with_rs_skip_pct(self):
        overlay = as_tech_desk_config({"rs_desk_target_path_skip_pct": 0.80})
        entry = {"zone_low": 98.0, "zone_high": 100.0, "target_1": 110.0}
        hist = pd.DataFrame(
            {
                "High": [110.5, 106.0],
                "Low": [108.0, 104.0],
                "Close": [109.0, 105.0],
            },
            index=pd.to_datetime(["2026-07-11", "2026-07-12"]),
        )
        exhausted, reason = is_setup_exhausted(entry, hist, overlay)
        self.assertTrue(exhausted)
        self.assertEqual(reason, "post_target_pullback")

    def test_post_target_helper_shared(self):
        reason = post_target_entry_block_reason(
            zone_low=98.0,
            zone_high=100.0,
            target_1=110.0,
            current_price=110.0,
            config=as_tech_desk_config({}),
        )
        self.assertEqual(reason, "post_target_pullback")


class RsDeskProcessOrchestrationTests(unittest.TestCase):
    @patch("tradingagents.rs_desk.process.resolve_rs_desk_tickers")
    def test_no_candidates(self, mock_resolve):
        mock_resolve.return_value = []
        with tempfile.TemporaryDirectory() as tmp:
            result = run_rs_desk_process(_rs_paths(tmp))
        self.assertTrue(result["skipped"])
        self.assertEqual(result["reason"], "no_candidates")

    @patch("tradingagents.rs_desk.process.create_llm_client")
    @patch("tradingagents.rs_desk.process.load_tech_reports")
    @patch("tradingagents.rs_desk.process.resolve_rs_desk_tickers")
    def test_no_reports_skips_llm(self, mock_resolve, mock_load, mock_llm):
        mock_resolve.return_value = ["ACC.NS"]
        mock_load.return_value = ([], [])
        with tempfile.TemporaryDirectory() as tmp:
            result = run_rs_desk_process(_rs_paths(tmp))
        self.assertTrue(result["skipped"])
        self.assertEqual(result["reason"], "no_reports")
        mock_llm.assert_not_called()

    @patch("tradingagents.rs_desk.process.persist_trader_reports", return_value=["ACC.NS"])
    @patch("tradingagents.rs_desk.process.TechDeskPaperTradeManager")
    @patch("tradingagents.rs_desk.process.fetch_prices", return_value={"ACC.NS": 100.0})
    @patch("tradingagents.rs_desk.process.run_tech_desk_traders")
    @patch("tradingagents.rs_desk.process.create_llm_client")
    @patch("tradingagents.rs_desk.process.partition_actionable_reports")
    @patch("tradingagents.rs_desk.process.load_tech_reports")
    @patch("tradingagents.rs_desk.process.resolve_rs_desk_tickers")
    def test_path5_trader_then_assemble_no_batch_pm(
        self,
        mock_resolve,
        mock_load,
        mock_partition,
        mock_llm,
        mock_traders,
        mock_prices,
        mock_mgr_cls,
        mock_persist,
    ):
        from tradingagents.tech_desk.report_loader import TechReportSnapshot

        snap = TechReportSnapshot(
            ticker="ACC.NS",
            report_date="2026-07-19",
            report_dir=Path("."),
            market_text="x",
            source_file="market.md",
            pm_summary={
                "proposal": "WAIT",
                "stop": 90.0,
                "target_1": 120.0,
                "entry_zone_low": 95.0,
                "entry_zone_high": 105.0,
                "confidence": 70,
                "bias": "bullish",
            },
        )
        mock_resolve.return_value = ["ACC.NS"]
        mock_load.return_value = ([snap], [])
        mock_partition.return_value = ([snap], [], [])
        mock_llm.return_value.get_llm.return_value = MagicMock()

        plan = TechTradePlan(
            ticker="ACC.NS",
            action=PlanAction.WAIT,
            entry_type=EntryType.LIMIT_ZONE,
            zone_low=95.0,
            zone_high=105.0,
            stop_loss=90.0,
            target_1=120.0,
            confidence=70,
            bias=Bias.BULLISH,
            invalidation="Below 90",
            rationale="Wait",
        )
        mock_traders.return_value = ([plan], [])

        mgr = MagicMock()
        mgr.max_positions = 20
        mgr.book.positions = []
        mgr.book.pending_path = Path("/tmp/rs_pending.json")
        mgr.book.path = Path("/tmp/rs_book.json")
        mgr.process_log_dir = Path(tempfile.mkdtemp())
        mgr.process_batch.return_value = {
            "skipped": [],
            "opened": [],
            "waits": ["ACC.NS"],
            "closes": [],
        }
        mock_mgr_cls.return_value = mgr

        with tempfile.TemporaryDirectory() as tmp:
            cfg = _rs_paths(tmp)
            cfg["rs_desk_min_rr"] = 1.8
            with patch(
                "tradingagents.rs_desk.process.assemble_decision_from_traders",
                wraps=__import__(
                    "tradingagents.tech_desk.assemble", fromlist=["assemble_decision_from_traders"]
                ).assemble_decision_from_traders,
            ) as mock_assemble:
                with patch(
                    "tradingagents.tech_desk.agents.portfolio_manager.run_tech_desk_batch_pm"
                ) as mock_pm:
                    result = run_rs_desk_process(cfg, process_date="2026-07-19")
                    mock_pm.assert_not_called()
                    mock_assemble.assert_called_once()

        mock_traders.assert_called_once()
        mock_persist.assert_called_once()
        mgr.process_batch.assert_called_once()
        self.assertFalse(result["skipped"])
        self.assertEqual(result["desk"], "rs_desk")
        self.assertEqual(result["assemble"], "script")
        self.assertEqual(result["trader_reports_saved"], ["ACC.NS"])
        self.assertEqual(result["trader_plans"], 1)
        # Overlay must pass remapped min R:R into trader config
        trader_cfg = mock_traders.call_args.args[3]
        self.assertEqual(trader_cfg.get("tech_desk_min_rr"), 1.8)


class RsDeskDailyTests(unittest.TestCase):
    @patch("tradingagents.rs_desk.daily.TechDeskPaperTradeManager")
    def test_daily_uses_overlay_manager(self, mock_mgr_cls):
        mgr = MagicMock()
        mgr.run_daily.return_value = {"closed": [], "filled": []}
        mock_mgr_cls.return_value = mgr
        with tempfile.TemporaryDirectory() as tmp:
            result = run_rs_desk_daily(_rs_paths(tmp))
        self.assertFalse(result["skipped"])
        self.assertEqual(result["desk"], "rs_desk")
        mgr.run_daily.assert_called_once()
        # Manager constructed with remapped RS paths
        call_cfg = mock_mgr_cls.call_args.args[0]
        self.assertTrue(str(call_cfg["tech_desk_book_path"]).endswith("rs_desk\\positions.json")
                        or str(call_cfg["tech_desk_book_path"]).endswith("rs_desk/positions.json"))
        self.assertEqual(call_cfg["tech_desk_strategy_name"], "rs_desk")


if __name__ == "__main__":
    unittest.main()
