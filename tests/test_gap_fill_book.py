"""Unit tests for Gap Fill position book."""

import pytest

from tradingagents.gap_fill.book import STRATEGY_NAME, GapFillPositionBook
from tradingagents.screening.gap_fill_engine import GapFillSignal
from tradingagents.screening.gap_fill_screener import GapFillPick

pytestmark = pytest.mark.unit


def _make_pick(symbol: str = "TEST.NS", direction: str = "BUY") -> GapFillPick:
    sig = GapFillSignal(
        symbol=symbol,
        direction=direction,
        gap_age=1,
        gap_pct=-2.5,
        gap_low=90.0,
        gap_high=98.0,
        fill_target=100.0,
        fill_pct=50.0,
        close=95.0,
        score=12.5,
        remark="BUY - gap down 1 day ago - fill 50% toward 100.00",
        stock_name="Test Co",
        sector="IT",
    )
    return GapFillPick(signal=sig, stock_name="Test Co", sector="IT")


def test_strategy_name():
    assert STRATEGY_NAME == "gap_fill"


def test_open_buy_position(tmp_path):
    cfg = {
        "gap_fill_book_path": str(tmp_path / "positions.json"),
        "gap_fill_max_positions": 10,
        "desk_capital": 100_000.0,
    }
    book = GapFillPositionBook(cfg)
    pos = book.open_position(_make_pick(), "2026-07-08")
    assert pos is not None
    assert pos["ticker"] == "TEST.NS"
    assert pos["entry_price"] == 95.0
    assert pos["target_1"] == 100.0
    assert pos["gap_low"] == 90.0
    assert pos["fill_pct"] == 50.0
    assert book.open_count() == 1


def test_skips_sell_signals(tmp_path):
    cfg = {"gap_fill_book_path": str(tmp_path / "positions.json")}
    book = GapFillPositionBook(cfg)
    pos = book.open_position(_make_pick(direction="SELL"), "2026-07-08")
    assert pos is None
    assert book.open_count() == 0


def test_save_picks_only_buy(tmp_path):
    cfg = {"gap_fill_book_path": str(tmp_path / "positions.json"), "gap_fill_max_positions": 10}
    book = GapFillPositionBook(cfg)
    saved = book.save_picks([
        _make_pick("AAA.NS", "BUY"),
        _make_pick("BBB.NS", "SELL"),
        _make_pick("CCC.NS", "BUY"),
    ])
    assert len(saved) == 2
    assert book.open_count() == 2
