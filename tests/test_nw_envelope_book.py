"""Unit tests for NW Envelope position book."""

import pytest

from tradingagents.screening.nw_envelope_engine import NwEnvelopeSignal
from tradingagents.screening.nw_envelope_screener import NwEnvelopePick
from tradingagents.nw_envelope.book import STRATEGY_NAME, NwEnvelopePositionBook

pytestmark = pytest.mark.unit


def _make_pick(symbol: str = "TEST.NS", direction: str = "BUY") -> NwEnvelopePick:
    sig = NwEnvelopeSignal(
        symbol=symbol,
        direction=direction,
        cross_age=1,
        close=100.0,
        middle=98.0,
        upper=105.0,
        lower=95.0,
        dist_pct=-5.26,
        remark="BUY - crossover 1 day ago - close crossed below lower band",
        stock_name="Test Co",
        sector="IT",
    )
    return NwEnvelopePick(signal=sig, stock_name="Test Co", sector="IT")


def test_strategy_name():
    assert STRATEGY_NAME == "nw_envelope"


def test_open_buy_position(tmp_path):
    cfg = {
        "nwe_book_path": str(tmp_path / "positions.json"),
        "nwe_max_positions": 10,
        "desk_capital": 100_000.0,
    }
    book = NwEnvelopePositionBook(cfg)
    pos = book.open_position(_make_pick(), "2026-07-08")
    assert pos is not None
    assert pos["ticker"] == "TEST.NS"
    assert pos["entry_price"] == 100.0
    assert pos["shares"] == 100
    assert pos["notional"] == pytest.approx(10_000.0)
    assert pos["stop_loss"] == 95.0
    assert pos["cross_age"] == 1
    assert pos["dist_pct"] == -5.26
    assert pos["nwe_lower"] == 95.0
    assert book.open_count() == 1


def test_open_buy_below_lower_band_stop(tmp_path):
    """When close pierces below lower band, stop mirrors distance below entry."""
    sig = NwEnvelopeSignal(
        symbol="MAHA.NS",
        direction="BUY",
        cross_age=2,
        close=82.01,
        middle=84.0,
        upper=87.0,
        lower=82.52,
        dist_pct=-0.62,
        remark="BUY below lower",
    )
    pick = NwEnvelopePick(signal=sig)
    book = NwEnvelopePositionBook({
        "nwe_book_path": str(tmp_path / "positions.json"),
        "nwe_max_positions": 10,
        "desk_capital": 100_000.0,
    })
    pos = book.open_position(pick, "2026-07-09")
    assert pos is not None
    assert pos["stop_loss"] == pytest.approx(81.50, abs=0.01)


def test_same_day_exit_skipped(tmp_path, monkeypatch):
    cfg = {"nwe_book_path": str(tmp_path / "positions.json"), "nwe_max_positions": 10}
    book = NwEnvelopePositionBook(cfg)
    book.open_position(_make_pick(), "2026-07-09")

    import pandas as pd

    def fake_history(symbol, start, end):
        idx = pd.to_datetime(["2026-07-09"])
        return pd.DataFrame(
            {"Open": [90.0], "High": [101.0], "Low": [89.0], "Close": [90.0], "Volume": [1e6]},
            index=idx,
        )

    monkeypatch.setattr(book, "_history", fake_history)
    monkeypatch.setattr(book, "_update_trailing_stop", lambda p, h: None)

    summary = book.evaluate_and_close_exits(as_of="2026-07-09")
    assert summary["closed"] == []
    assert book.open_count() == 1


def test_skips_sell_signals(tmp_path):
    cfg = {"nwe_book_path": str(tmp_path / "positions.json")}
    book = NwEnvelopePositionBook(cfg)
    pos = book.open_position(_make_pick(direction="SELL"), "2026-07-08")
    assert pos is None
    assert book.open_count() == 0


def test_save_picks_only_buy(tmp_path):
    cfg = {"nwe_book_path": str(tmp_path / "positions.json"), "nwe_max_positions": 10}
    book = NwEnvelopePositionBook(cfg)
    saved = book.save_picks([
        _make_pick("AAA.NS", "BUY"),
        _make_pick("BBB.NS", "SELL"),
        _make_pick("CCC.NS", "BUY"),
    ])
    assert len(saved) == 2
    assert book.open_count() == 2
