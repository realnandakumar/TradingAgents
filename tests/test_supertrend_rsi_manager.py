"""Tests for SuperTrend+RSI portfolio manager daily run."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tradingagents.screening.supertrend_rsi_engine import SuperTrendRSISignal
from tradingagents.screening.supertrend_rsi_screener import SuperTrendRSIPick
from tradingagents.supertrend_rsi.manager import SuperTrendRSIPaperTradeManager


def _pick(symbol: str, direction: str = "BUY", sector: str = "Healthcare"):
    sig = SuperTrendRSISignal(
        symbol=symbol,
        direction=direction,
        score=70,
        grade="Good",
        grade_stars="★★★",
        close=100.0,
        supertrend_value=92.0,
        rsi=58.0,
        flip_age=2,
        stock_name=symbol,
        sector=sector,
    )
    return SuperTrendRSIPick(signal=sig, market_cap_cr=1000.0, avg_traded_value_cr=5.0)


class StrsiManagerTests(unittest.TestCase):
    def _cfg(self, tmp: str) -> dict:
        root = Path(tmp)
        book = root / "supertrend_rsi" / "positions.json"
        book.parent.mkdir(parents=True, exist_ok=True)
        book.write_text('{"positions": [], "sell_signals": []}', encoding="utf-8")
        return {
            "strsi_book_path": str(book),
            "strsi_max_positions": 10,
            "strsi_max_per_sector": 2,
            "desk_capital": 200_000,
        }

    def test_run_daily_skips_sector_cap(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self._cfg(tmp)
            manager = SuperTrendRSIPaperTradeManager(cfg)
            manager.book._state = {
                "positions": [
                    {
                        "ticker": "AAA.NS",
                        "status": "open",
                        "sector": "Healthcare",
                        "entry_price": 100.0,
                        "remaining_pct": 100.0,
                        "phase": "initial",
                        "screen_date": "2026-07-01",
                    },
                    {
                        "ticker": "BBB.NS",
                        "status": "open",
                        "sector": "Healthcare",
                        "entry_price": 100.0,
                        "remaining_pct": 100.0,
                        "phase": "initial",
                        "screen_date": "2026-07-01",
                    },
                ],
                "sell_signals": [],
            }

            with patch.object(
                manager.book,
                "evaluate_and_close_exits",
                return_value={"closed": []},
            ), patch.object(
                manager.book,
                "close_on_sell_signals",
                return_value=[],
            ), patch.object(manager.book, "stats", return_value={}):
                report = manager.run_daily(
                    [_pick("CCC.NS", "BUY", "Healthcare")],
                    screen_date="2026-07-11",
                )

            self.assertEqual(report["opened"], [])
            self.assertIn("CCC.NS", report["skipped_sector_cap"])

    def test_run_daily_stores_sell_and_closes(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = self._cfg(tmp)
            manager = SuperTrendRSIPaperTradeManager(cfg)
            manager.book.open_position(_pick("TEST.NS", "BUY"), "2026-07-01")

            with patch.object(
                manager.book,
                "evaluate_and_close_exits",
                return_value={"closed": []},
            ), patch.object(manager.book, "stats", return_value={}):
                report = manager.run_daily(
                    [_pick("TEST.NS", "SELL")],
                    screen_date="2026-07-11",
                )

            self.assertIn("TEST.NS", report["signal_sell_closes"])
            self.assertEqual(manager.book.open_count(), 0)
            self.assertTrue(any(s["ticker"] == "TEST.NS" for s in manager.book.sell_signals))


if __name__ == "__main__":
    unittest.main()
