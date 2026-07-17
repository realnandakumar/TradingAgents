"""Tests for momentum_trade_positional book."""

import json

import pytest

from tradingagents.momentum import STRATEGY_NAME, MomentumPositionBook
from tradingagents.screening.momentum_screener import MomentumPick

pytestmark = pytest.mark.unit


def _pick(symbol="TEST.NS"):
    return MomentumPick(
        symbol=symbol,
        stock_name="Test Co",
        sector="IT",
        entry_price=100.0,
        stop_loss=90.0,
        target_1=115.0,
        target_2=125.0,
        stop_loss_pct=-10.0,
        target_1_pct=15.0,
        target_2_pct=25.0,
        risk_reward_ratio=1.5,
        risk_reward_ratio_2=2.5,
        supertrend_status="Buy",
        rsi=58.0,
        adx=22.0,
        macd=1.5,
        macd_signal=1.0,
        volume_ratio_5_20=1.2,
        extension_pct=5.0,
        adx_rising=True,
        risk_pct=10.0,
        market_cap_cr=10000.0,
        avg_traded_value_cr=50.0,
    )


def test_save_picks_writes_momentum_trade_positional(tmp_path):
    path = tmp_path / "positions.json"
    book = MomentumPositionBook({"momentum_book_path": str(path)})
    saved = book.save_picks([_pick()], screen_date="2026-07-04")
    assert len(saved) == 1
    assert saved[0]["strategy"] == STRATEGY_NAME
    assert saved[0]["status"] == "open"
    assert saved[0]["macd"] == 1.5

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["strategy"] == STRATEGY_NAME
    assert len(raw["positions"]) == 1


def test_save_picks_keeps_first_entry_date(tmp_path):
    path = tmp_path / "positions.json"
    book = MomentumPositionBook({"momentum_book_path": str(path)})
    book.save_picks([_pick()], screen_date="2026-07-01")
    book.touch_screen_date("TEST.NS", "2026-07-04")
    assert len(book.positions) == 1
    assert book.positions[0]["screen_date"] == "2026-07-01"
    assert book.positions[0]["last_screen_date"] == "2026-07-04"


def test_open_position_respects_sector_cap(tmp_path):
    path = tmp_path / "positions.json"
    book = MomentumPositionBook({
        "momentum_book_path": str(path),
        "momentum_max_per_sector": 2,
        "momentum_max_positions": 10,
    })
    for i in range(2):
        assert book.open_position(_pick(f"IT{i}.NS"), "2026-07-01") is not None
    assert book.open_position(_pick("IT2.NS"), "2026-07-01") is None
    assert book.open_count() == 2
