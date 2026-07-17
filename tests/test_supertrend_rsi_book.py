"""Unit tests for SuperTrend+RSI position book."""

from dataclasses import dataclass

import pytest

from tradingagents.screening.supertrend_rsi_engine import ScoreComponents, SuperTrendRSISignal
from tradingagents.screening.supertrend_rsi_screener import SuperTrendRSIPick
from tradingagents.supertrend_rsi.book import STRATEGY_NAME, SuperTrendRSIPositionBook

pytestmark = pytest.mark.unit


def _make_pick(symbol: str = "TEST.NS", direction: str = "BUY") -> SuperTrendRSIPick:
    sig = SuperTrendRSISignal(
        symbol=symbol,
        direction=direction,
        score=55,
        grade="Ignore",
        grade_stars="★",
        close=100.0,
        supertrend_value=92.0,
        rsi=58.0,
        flip_age=2,
        stock_name="Test Co",
        sector="IT",
    )
    return SuperTrendRSIPick(signal=sig, market_cap_cr=1000.0, avg_traded_value_cr=5.0)


def test_strategy_name():
    assert STRATEGY_NAME == "supertrend_rsi"


def test_open_buy_position(tmp_path):
    cfg = {"strsi_book_path": str(tmp_path / "positions.json"), "strsi_max_positions": 20}
    book = SuperTrendRSIPositionBook(cfg)
    pos = book.open_position(_make_pick(), "2026-07-04")
    assert pos is not None
    assert pos["ticker"] == "TEST.NS"
    assert pos["entry_price"] == 100.0
    assert pos["stop_loss"] == 92.0
    assert pos["signal_score"] == 55
    assert book.open_count() == 1


def test_skips_sell_signals(tmp_path):
    cfg = {"strsi_book_path": str(tmp_path / "positions.json")}
    book = SuperTrendRSIPositionBook(cfg)
    pos = book.open_position(_make_pick(direction="SELL"), "2026-07-04")
    assert pos is None
    assert book.open_count() == 0


def test_save_picks_only_buy(tmp_path):
    cfg = {"strsi_book_path": str(tmp_path / "positions.json"), "strsi_max_positions": 20}
    book = SuperTrendRSIPositionBook(cfg)
    saved = book.save_picks([
        _make_pick("AAA.NS", "BUY"),
        _make_pick("BBB.NS", "SELL"),
        _make_pick("CCC.NS", "BUY"),
    ])
    assert len(saved) == 2
    assert book.open_count() == 2
    assert any(s["ticker"] == "BBB.NS" for s in book.sell_signals)


def test_open_position_respects_sector_cap(tmp_path):
    cfg = {
        "strsi_book_path": str(tmp_path / "positions.json"),
        "strsi_max_per_sector": 2,
        "strsi_max_positions": 10,
    }
    book = SuperTrendRSIPositionBook(cfg)
    for i in range(2):
        assert book.open_position(_make_pick(f"IT{i}.NS"), "2026-07-01") is not None
    assert book.open_position(_make_pick("IT2.NS"), "2026-07-01") is None
    assert book.open_count() == 2


def test_close_on_sell_signal(tmp_path):
    cfg = {"strsi_book_path": str(tmp_path / "positions.json"), "strsi_max_positions": 20}
    book = SuperTrendRSIPositionBook(cfg)
    assert book.open_position(_make_pick("TEST.NS", "BUY"), "2026-07-01") is not None
    events = book.close_on_sell_signals(
        [_make_pick("TEST.NS", "SELL")],
        as_of="2026-07-04",
    )
    assert len(events) == 1
    assert events[0]["reason"] == "signal_sell"
    assert book.open_count() == 0
    assert book.positions[0]["status"] == "closed"
