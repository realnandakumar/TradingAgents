"""Tests for swing portfolio manager daily run."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from tradingagents.swing.manager import PortfolioPaperTradeManager


def _pick(symbol: str, sector: str = "Information Technology"):
    p = MagicMock()
    p.symbol = symbol
    p.stock_name = symbol
    p.sector = sector
    p.entry_price = 100.0
    p.stop_loss = 90.0
    p.target_1 = 115.0
    p.target_2 = 125.0
    p.stop_loss_pct = -10.0
    p.target_1_pct = 15.0
    p.target_2_pct = 25.0
    p.risk_reward_ratio = 1.5
    p.risk_reward_ratio_2 = 2.5
    p.supertrend_status = "Buy"
    p.relative_volume = 1.5
    p.rsi = 55.0
    p.adx = 25.0
    p.volume_spike_pct = 50.0
    p.risk_pct = 5.0
    p.market_cap_cr = 10000.0
    p.avg_traded_value_cr = 50.0
    return p


class SwingManagerSectorCapTests(unittest.TestCase):
    def _cfg(self, tmp: str) -> dict:
        root = Path(tmp)
        book = root / "swing" / "positions.json"
        book.parent.mkdir(parents=True, exist_ok=True)
        book.write_text('{"positions": []}', encoding="utf-8")
        return {
            "swing_book_path": str(book),
            "swing_max_positions": 10,
            "swing_max_per_sector": 2,
            "desk_capital": 200_000,
        }

    def test_run_daily_skips_when_sector_cap_reached(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self._cfg(tmp)
            manager = PortfolioPaperTradeManager(cfg)
            manager.book._state = {
                "positions": [
                    {
                        "ticker": "AAA.NS",
                        "status": "open",
                        "sector": "Information Technology",
                        "entry_price": 100.0,
                    },
                    {
                        "ticker": "BBB.NS",
                        "status": "open",
                        "sector": "Information Technology",
                        "entry_price": 100.0,
                    },
                ]
            }

            with patch.object(
                manager.book,
                "evaluate_and_close_exits",
                return_value={"closed": []},
            ), patch.object(manager.book, "stats", return_value={}):
                report = manager.run_daily(
                    [_pick("CCC.NS", "Information Technology")],
                    screen_date="2026-07-11",
                )

            self.assertEqual(report["opened"], [])
            self.assertIn("CCC.NS", report["skipped_sector_cap"])
            self.assertEqual(manager.book.open_count(), 2)

    def test_run_daily_opens_other_sector_when_one_sector_full(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self._cfg(tmp)
            manager = PortfolioPaperTradeManager(cfg)
            manager.book._state = {
                "positions": [
                    {
                        "ticker": "AAA.NS",
                        "status": "open",
                        "sector": "Information Technology",
                        "entry_price": 100.0,
                        "shares": 10,
                    },
                    {
                        "ticker": "BBB.NS",
                        "status": "open",
                        "sector": "Information Technology",
                        "entry_price": 100.0,
                        "shares": 10,
                    },
                ]
            }

            with patch.object(
                manager.book,
                "evaluate_and_close_exits",
                return_value={"closed": []},
            ), patch.object(manager.book, "stats", return_value={}):
                report = manager.run_daily(
                    [
                        _pick("CCC.NS", "Information Technology"),
                        _pick("DDD.NS", "Financial Services"),
                    ],
                    screen_date="2026-07-11",
                )

            self.assertIn("CCC.NS", report["skipped_sector_cap"])
            self.assertIn("DDD.NS", report["opened"])
            self.assertEqual(manager.book.open_count(), 3)


if __name__ == "__main__":
    unittest.main()
