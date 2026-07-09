"""Tests for nanda_swing_scanner book."""

import json

import pytest

from tradingagents.nss import STRATEGY_NAME, NSSPositionBook
from tradingagents.screening.nss_screener import NSSPick

pytestmark = pytest.mark.unit


def _pick(symbol="TEST.NS"):
    return NSSPick(
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
        composite_score=72.0,
        confidence="high",
        primary_reason="tight consolidation breakout",
        rsi=55.0,
        adx=18.0,
        relative_volume=1.8,
        range_pct=5.5,
        atr_ratio=0.88,
        risk_pct=10.0,
        market_cap_cr=10000.0,
        avg_traded_value_cr=50.0,
    )


def test_save_picks_writes_nanda_swing_scanner(tmp_path):
    path = tmp_path / "positions.json"
    book = NSSPositionBook({"nss_book_path": str(path)})
    saved = book.save_picks([_pick()], screen_date="2026-07-04")
    assert len(saved) == 1
    assert saved[0]["strategy"] == STRATEGY_NAME
    assert saved[0]["status"] == "open"
    assert saved[0]["composite_score"] == 72.0

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["strategy"] == STRATEGY_NAME
    assert len(raw["positions"]) == 1


def test_save_picks_keeps_first_entry_date(tmp_path):
    path = tmp_path / "positions.json"
    book = NSSPositionBook({"nss_book_path": str(path)})
    book.save_picks([_pick()], screen_date="2026-07-01")
    book.touch_screen_date("TEST.NS", "2026-07-04")
    assert len(book.positions) == 1
    assert book.positions[0]["screen_date"] == "2026-07-01"
    assert book.positions[0]["last_screen_date"] == "2026-07-04"
