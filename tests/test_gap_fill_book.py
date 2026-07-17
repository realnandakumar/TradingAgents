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
        gap_pct=-6.0,
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


def test_open_down_gap_position(tmp_path):
    cfg = {
        "gap_fill_book_path": str(tmp_path / "positions.json"),
        "gap_fill_max_positions": 10,
        "desk_capital": 100_000.0,
    }
    book = GapFillPositionBook(cfg)
    pos = book.open_position(_make_pick(direction="DOWN"), "2026-07-08")
    assert pos is not None
    assert pos["direction"] == "BUY"
    assert pos["gap_direction"] == "DOWN"
    assert book.open_count() == 1


def test_pick_passes_long_entry_down_gap():
    from tradingagents.screening.gap_fill_engine import GapFillSignal, pick_passes_long_entry

    sig = GapFillSignal(
        symbol="TEST.NS",
        direction="DOWN",
        gap_age=2,
        gap_pct=-6.0,
        gap_low=90.0,
        gap_high=98.0,
        fill_target=100.0,
        fill_pct=25.0,
        close=95.0,
        rejected=False,
    )
    ok, reason = pick_passes_long_entry(sig, {"gap_fill_min_pct": 5.0, "gap_fill_max_progress": 50})
    assert ok, reason


def test_pick_passes_long_entry_rejects_up_gap():
    from tradingagents.screening.gap_fill_engine import GapFillSignal, pick_passes_long_entry

    sig = GapFillSignal(symbol="TEST.NS", direction="UP", gap_pct=6.0, fill_pct=30.0, rejected=False)
    ok, reason = pick_passes_long_entry(sig)
    assert not ok
    assert "long" in reason.lower()


def test_pick_passes_long_entry_rejects_fill_too_high():
    from tradingagents.screening.gap_fill_engine import GapFillSignal, pick_passes_long_entry

    sig = GapFillSignal(
        symbol="TEST.NS",
        direction="DOWN",
        gap_pct=-6.0,
        gap_age=1,
        fill_pct=75.0,
        close=95.0,
        fill_target=100.0,
        rejected=False,
    )
    ok, _ = pick_passes_long_entry(sig, {"gap_fill_max_progress": 50})
    assert not ok


def test_reset_book(tmp_path):
    cfg = {"gap_fill_book_path": str(tmp_path / "positions.json"), "gap_fill_max_positions": 10}
    book = GapFillPositionBook(cfg)
    book.open_position(_make_pick(), "2026-07-08")
    assert book.open_count() == 1
    book.reset_book()
    assert book.open_count() == 0
    assert book.positions == []


def test_skips_up_gap_signals(tmp_path):
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
    assert len(book.sell_signals) == 1
    assert book.sell_signals[0]["ticker"] == "BBB.NS"


def test_sector_cap_blocks_fifth(tmp_path):
    cfg = {
        "gap_fill_book_path": str(tmp_path / "positions.json"),
        "gap_fill_max_positions": 20,
        "gap_fill_max_per_sector": 4,
        "desk_capital": 100_000.0,
    }
    book = GapFillPositionBook(cfg)
    for i in range(4):
        pick = _make_pick(f"T{i}.NS", "DOWN")
        pick.sector = "IT"
        pick.signal.sector = "IT"
        assert book.open_position(pick, "2026-07-08") is not None
    fifth = _make_pick("T4.NS", "DOWN")
    fifth.sector = "IT"
    fifth.signal.sector = "IT"
    assert book.open_position(fifth, "2026-07-08") is None
    assert book.open_count() == 4


def test_close_on_up_gap_signal(tmp_path):
    cfg = {
        "gap_fill_book_path": str(tmp_path / "positions.json"),
        "gap_fill_max_positions": 10,
        "desk_capital": 100_000.0,
    }
    book = GapFillPositionBook(cfg)
    assert book.open_position(_make_pick("TEST.NS", "DOWN"), "2026-07-01") is not None
    up = _make_pick("TEST.NS", "UP")
    up.signal.close = 98.0
    events = book.close_on_sell_signals([up], as_of="2026-07-08")
    assert len(events) == 1
    assert events[0]["reason"] == "signal_sell"
    assert book.open_count() == 0


def test_reset_portfolio_via_manager(tmp_path):
    from tradingagents.gap_fill.manager import GapFillPaperTradeManager

    cfg = {
        "gap_fill_book_path": str(tmp_path / "positions.json"),
        "gap_fill_pending_path": str(tmp_path / "pending.json"),
        "gap_fill_daily_dir": str(tmp_path / "daily"),
        "gap_fill_max_positions": 10,
    }
    mgr = GapFillPaperTradeManager(cfg)
    mgr.book.open_position(_make_pick(), "2026-07-08")
    assert mgr.book.open_count() == 1
    mgr.reset_portfolio()
    assert mgr.book.open_count() == 0
