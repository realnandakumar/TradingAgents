"""RS Desk config overlay keeps books separate while sharing tech_reports."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tradingagents.rs_desk.config_overlay import as_tech_desk_config
from tradingagents.tech_desk.book import TechDeskPositionBook
from tradingagents.tech_desk.plan_from_ma import trade_plan_from_pm_summary
from tradingagents.tech_desk.schemas import EntryType, PlanAction


class RsDeskOverlayTests(unittest.TestCase):
    def test_overlay_points_at_rs_paths_not_tech_desk(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cfg = {
                "rs_desk_book_path": str(root / "rs_desk" / "positions.json"),
                "rs_desk_pending_path": str(root / "rs_desk" / "pending_entries.json"),
                "rs_desk_pending_dismissed_path": str(root / "rs_desk" / "pending_dismissed.json"),
                "rs_desk_closed_history_path": str(root / "rs_desk" / "closed_history.json"),
                "tech_desk_book_path": str(root / "tech_desk" / "positions.json"),
                "desk_capital": 200_000.0,
                "rs_desk_max_positions": 20,
                "tech_analyze_reports_dir": str(root / "tech_reports"),
            }
            overlay = as_tech_desk_config(cfg)
            self.assertEqual(overlay["tech_desk_book_path"], cfg["rs_desk_book_path"])
            self.assertNotEqual(overlay["tech_desk_book_path"], cfg["tech_desk_book_path"])
            self.assertEqual(overlay["tech_desk_strategy_name"], "rs_desk")
            self.assertEqual(overlay["tech_analyze_reports_dir"], cfg["tech_analyze_reports_dir"])

            rs_book = TechDeskPositionBook(overlay)
            tech_book = TechDeskPositionBook(
                {
                    **cfg,
                    "tech_desk_book_path": cfg["tech_desk_book_path"],
                    "tech_desk_pending_path": str(root / "tech_desk" / "pending.json"),
                    "tech_desk_pending_dismissed_path": str(
                        root / "tech_desk" / "dismissed.json"
                    ),
                    "tech_desk_strategy_name": "tech_desk",
                }
            )
            self.assertEqual(rs_book.strategy_name, "rs_desk")
            self.assertEqual(tech_book.strategy_name, "tech_desk")
            self.assertNotEqual(rs_book.path, tech_book.path)

    def test_ma_levels_still_convert_for_rs_preview(self):
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


if __name__ == "__main__":
    unittest.main()
