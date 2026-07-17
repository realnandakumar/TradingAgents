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


def test_open_position_respects_sector_cap(tmp_path):
    path = tmp_path / "positions.json"
    book = NSSPositionBook({
        "nss_book_path": str(path),
        "nss_max_per_sector": 2,
        "nss_max_positions": 10,
    })
    for i in range(2):
        assert book.open_position(_pick(f"IT{i}.NS"), "2026-07-01") is not None
    assert book.open_position(_pick("IT2.NS"), "2026-07-01") is None
    assert book.open_count() == 2


def test_close_legacy_runners(tmp_path):
    path = tmp_path / "positions.json"
    book = NSSPositionBook({"nss_book_path": str(path)})
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
        ]
    }
    events = book.close_legacy_runners(as_of="2026-07-16")
    assert len(events) == 1
    assert events[0]["reason"] == "legacy_runner_close"
    assert book.open_count() == 0
    assert book.positions[0]["status"] == "closed"
