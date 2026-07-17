"""Foreclosure disabled on strategy paper desks."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tradingagents.replacements.approve import approve_portfolio_replacements
from tradingagents.swing.manager import PortfolioPaperTradeManager


def _pick(symbol: str):
    p = MagicMock()
    p.symbol = symbol
    p.stock_name = symbol
    p.relative_volume = 1.5
    p.rsi = 55.0
    p.adx = 25.0
    return p


class ForeclosureDisabledTests(unittest.TestCase):
    def _cfg(self, tmp: str) -> dict:
        root = Path(tmp)
        book = root / "swing" / "positions.json"
        book.parent.mkdir(parents=True, exist_ok=True)
        book.write_text('{"positions": []}', encoding="utf-8")
        return {
            "swing_book_path": str(book),
            "swing_max_positions": 2,
            "desk_capital": 200_000,
        }

    def test_full_portfolio_skips_without_proposals(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self._cfg(tmp)
            manager = PortfolioPaperTradeManager(cfg)
            manager.book._state = {
                "positions": [
                    {"ticker": "AAA.NS", "status": "open", "entry_price": 100.0},
                    {"ticker": "BBB.NS", "status": "open", "entry_price": 100.0},
                ]
            }

            with patch.object(
                manager.book,
                "evaluate_and_close_exits",
                return_value={"closed": []},
            ), patch.object(manager.book, "touch_screen_date"), patch.object(
                manager.book, "stats", return_value={}
            ):
                report = manager.run_daily([_pick("CCC.NS")], screen_date="2026-07-11")

            self.assertEqual(report["proposals"], [])
            self.assertEqual(report["approved_replacements"], [])
            self.assertIn("CCC.NS", report.get("skipped_full", []))
            self.assertEqual(manager._load_pending(), [])

    def test_approve_hub_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self._cfg(tmp)
            manager = PortfolioPaperTradeManager(cfg)
            manager._save_pending(
                [
                    {
                        "id": "1",
                        "close_ticker": "AAA.NS",
                        "new_ticker": "CCC.NS",
                        "close_stock_name": "A",
                        "new_stock_name": "C",
                        "close_reason": "weakest",
                        "close_score": 0,
                        "proposed_at": "2026-07-11T00:00:00",
                        "new_relative_volume": 1.0,
                        "new_rsi": 50.0,
                        "new_adx": 20.0,
                    }
                ]
            )
            result = approve_portfolio_replacements("swing", config=cfg, yes=True)
            self.assertEqual(result["approved"], 0)
            self.assertTrue(any("disabled" in m.lower() for m in result["messages"]))
            self.assertEqual(manager._load_pending(), [])


if __name__ == "__main__":
    unittest.main()
