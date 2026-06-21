"""Offline unit tests for the paper-trading book.

Position opening and stats are exercised without network access. The
mark-to-market / close path hits yfinance, so it is not unit-tested here.
"""

import json

import pytest

from tradingagents.paper.book import PaperBook

pytestmark = pytest.mark.unit


def _book(tmp_path):
    return PaperBook({
        "paper_book_path": str(tmp_path / "book.json"),
        "paper_capital": 1_000_000.0,
        "paper_max_positions": 10,
        "paper_holding_days": 20,
    })


def test_open_position_sizes_equal_weight(tmp_path):
    book = _book(tmp_path)
    pos = book.open_position("HAL.NS", "Buy", 4000.0, "2026-06-01", signals=["rsi_breakout"])
    assert pos is not None
    assert pos["alloc"] == pytest.approx(100_000.0)       # capital / max_positions
    assert pos["shares"] == pytest.approx(25.0)           # alloc / entry_price
    assert book.has_open_position("HAL.NS")


def test_duplicate_open_is_blocked(tmp_path):
    book = _book(tmp_path)
    assert book.open_position("HAL.NS", "Buy", 4000.0, "2026-06-01") is not None
    assert book.open_position("HAL.NS", "Buy", 4100.0, "2026-06-02") is None


def test_invalid_price_rejected(tmp_path):
    book = _book(tmp_path)
    assert book.open_position("HAL.NS", "Buy", 0.0, "2026-06-01") is None
    assert book.open_position("HAL.NS", "Buy", None, "2026-06-01") is None


def test_persistence_across_instances(tmp_path):
    book = _book(tmp_path)
    book.open_position("TCS.NS", "Overweight", 3500.0, "2026-06-01")
    reopened = _book(tmp_path)
    assert reopened.has_open_position("TCS.NS")


def test_stats_overall_and_per_signal(tmp_path):
    path = tmp_path / "book.json"
    path.write_text(json.dumps({"positions": [
        {"ticker": "A.NS", "rating": "Buy", "signals": ["rsi_breakout", "cup_and_handle"],
         "entry_date": "2026-05-01", "entry_price": 100.0, "shares": 10.0, "alloc": 1000.0,
         "status": "closed", "exit_date": "2026-05-29", "exit_price": 110.0,
         "raw_return": 0.10, "alpha_return": 0.06, "holding_days_actual": 20},
        {"ticker": "B.NS", "rating": "Buy", "signals": ["rsi_breakout"],
         "entry_date": "2026-05-01", "entry_price": 100.0, "shares": 10.0, "alloc": 1000.0,
         "status": "closed", "exit_date": "2026-05-29", "exit_price": 90.0,
         "raw_return": -0.10, "alpha_return": -0.12, "holding_days_actual": 20},
    ]}))
    book = PaperBook({"paper_book_path": str(path)})
    stats = book.stats()

    assert stats["overall"]["trades"] == 2
    assert stats["overall"]["win_rate"] == 50.0
    assert stats["overall"]["avg_return"] == pytest.approx(0.0)
    # rsi_breakout fired on both; cup_and_handle only on the winner
    assert stats["per_signal"]["rsi_breakout"]["trades"] == 2
    assert stats["per_signal"]["cup_and_handle"]["win_rate"] == 100.0
