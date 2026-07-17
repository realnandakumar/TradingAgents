"""Unit tests for TRAMA position book."""

import json
import math

import pytest

from tradingagents.screening.trama_engine import TramaSignal
from tradingagents.screening.trama_screener import TramaPick
from tradingagents.trama.book import STRATEGY_NAME, TramaPositionBook, _finite_price, _sanitize_for_json

pytestmark = pytest.mark.unit


def _make_pick(symbol: str = "TEST.NS", direction: str = "BUY") -> TramaPick:
    sig = TramaSignal(
        symbol=symbol,
        direction=direction,
        cross_age=1,
        close=100.0,
        trama=95.0,
        dist_pct=5.26,
        remark="BUY - crossover 1 day ago - close crossed above TRAMA",
        stock_name="Test Co",
        sector="IT",
    )
    return TramaPick(signal=sig, stock_name="Test Co", sector="IT")


def test_strategy_name():
    assert STRATEGY_NAME == "trama_crossover"


def test_open_buy_position(tmp_path):
    cfg = {
        "trama_book_path": str(tmp_path / "positions.json"),
        "trama_max_positions": 20,
        "desk_capital": 100_000.0,
    }
    book = TramaPositionBook(cfg)
    pos = book.open_position(_make_pick(), "2026-07-08")
    assert pos is not None
    assert pos["ticker"] == "TEST.NS"
    assert pos["entry_price"] == 100.0
    assert pos["shares"] == 50  # ₹5k slot (100k/20) / ₹100
    assert pos["notional"] == pytest.approx(5_000.0)
    assert pos["stop_loss"] == 95.0
    assert pos["cross_age"] == 1
    assert pos["dist_pct"] == 5.26
    assert book.open_count() == 1


def test_same_day_exit_skipped(tmp_path, monkeypatch):
    cfg = {"trama_book_path": str(tmp_path / "positions.json"), "trama_max_positions": 20}
    book = TramaPositionBook(cfg)
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
    cfg = {"trama_book_path": str(tmp_path / "positions.json")}
    book = TramaPositionBook(cfg)
    pos = book.open_position(_make_pick(direction="SELL"), "2026-07-08")
    assert pos is None
    assert book.open_count() == 0


def test_save_picks_only_buy(tmp_path):
    cfg = {"trama_book_path": str(tmp_path / "positions.json"), "trama_max_positions": 20}
    book = TramaPositionBook(cfg)
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
        "trama_book_path": str(tmp_path / "positions.json"),
        "trama_max_per_sector": 2,
        "trama_max_positions": 10,
        "desk_capital": 100_000.0,
    }
    book = TramaPositionBook(cfg)
    for i in range(2):
        assert book.open_position(_make_pick(f"IT{i}.NS"), "2026-07-01") is not None
    assert book.open_position(_make_pick("IT2.NS"), "2026-07-01") is None
    assert book.open_count() == 2


def test_close_on_sell_signal(tmp_path):
    cfg = {"trama_book_path": str(tmp_path / "positions.json"), "trama_max_positions": 20, "desk_capital": 100_000.0}
    book = TramaPositionBook(cfg)
    assert book.open_position(_make_pick("TEST.NS", "BUY"), "2026-07-01") is not None
    events = book.close_on_sell_signals(
        [_make_pick("TEST.NS", "SELL")],
        as_of="2026-07-04",
    )
    assert len(events) == 1
    assert events[0]["reason"] == "signal_sell"
    assert book.open_count() == 0


def test_close_legacy_runners(tmp_path):
    cfg = {"trama_book_path": str(tmp_path / "positions.json")}
    book = TramaPositionBook(cfg)
    book._state = {
        "positions": [
            {
                "ticker": "RUN.NS",
                "stock_name": "Runner",
                "sector": "IT",
                "screen_date": "2026-07-01",
                "entry_price": 100.0,
                "shares": 10,
                "stop_loss": 90.0,
                "trailing_stop": 90.0,
                "target_1": 115.0,
                "status": "open",
                "phase": "runner",
                "remaining_pct": 25.0,
                "t2_partial_done": True,
                "partial_exits": [
                    {
                        "date": "2026-07-05",
                        "price": 125.0,
                        "pct": 75.0,
                        "reason": "target_2_partial",
                        "return": 0.25,
                        "rupee_pnl": 187.5,
                    }
                ],
            }
        ],
        "sell_signals": [],
    }
    events = book.close_legacy_runners(as_of="2026-07-16")
    assert len(events) == 1
    assert events[0]["reason"] == "legacy_runner_close"
    assert book.open_count() == 0


def test_finite_price_rejects_nan():
    assert _finite_price(float("nan")) is None
    assert _finite_price(float("inf")) is None
    assert _finite_price(123.45) == 123.45


def test_save_writes_strict_json_without_nan(tmp_path):
    cfg = {"trama_book_path": str(tmp_path / "positions.json"), "trama_max_positions": 20}
    book = TramaPositionBook(cfg)
    book.open_position(_make_pick(), "2026-07-08")
    book.positions[0]["exit_price"] = float("nan")
    book.positions[0]["partial_exits"] = [{"price": float("nan"), "return": float("nan")}]
    book._save()

    raw = (tmp_path / "positions.json").read_text(encoding="utf-8")
    assert "NaN" not in raw
    parsed = json.loads(raw)
    assert parsed["positions"][0]["exit_price"] is None


def test_latest_price_rejects_nan_close(tmp_path, monkeypatch):
    cfg = {"trama_book_path": str(tmp_path / "positions.json")}
    book = TramaPositionBook(cfg)

    import pandas as pd

    def fake_history(symbol, start, end):
        idx = pd.to_datetime(["2026-07-12"])
        return pd.DataFrame(
            {"Open": [1.0], "High": [1.0], "Low": [1.0], "Close": [float("nan")], "Volume": [1.0]},
            index=idx,
        )

    monkeypatch.setattr(book, "_history", fake_history)
    assert book.latest_price("TEST.NS") is None


def test_sanitize_for_json_nested():
    cleaned = _sanitize_for_json({"a": float("nan"), "b": [{"c": math.inf}]})
    assert cleaned == {"a": None, "b": [{"c": None}]}
