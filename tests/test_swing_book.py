"""Tests for swing_trade_positional book."""

import json
from pathlib import Path

import pandas as pd
import pytest

from tradingagents.swing import STRATEGY_NAME, SwingPositionBook
from tradingagents.screening.swing_screener import SwingPick

pytestmark = pytest.mark.unit


def _pick(symbol="TEST.NS"):
    return SwingPick(
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
        adx=18.0,
        volume_spike_pct=50.0,
        relative_volume=1.5,
        risk_pct=5.0,
        market_cap_cr=10000.0,
        avg_traded_value_cr=50.0,
    )


def test_save_picks_writes_swing_trade_positional(tmp_path):
    path = tmp_path / "positions.json"
    book = SwingPositionBook({"swing_book_path": str(path)})
    saved = book.save_picks([_pick()], screen_date="2026-07-03")
    assert len(saved) == 1
    assert saved[0]["strategy"] == STRATEGY_NAME
    assert saved[0]["status"] == "open"
    assert saved[0]["stop_loss_pct"] == -10.0

    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["strategy"] == STRATEGY_NAME
    assert len(raw["positions"]) == 1


def test_save_picks_upserts_open_position(tmp_path):
    path = tmp_path / "positions.json"
    book = SwingPositionBook({"swing_book_path": str(path)})
    book.save_picks([_pick()], screen_date="2026-07-01")
    book.touch_screen_date("TEST.NS", "2026-07-03")
    assert len(book.positions) == 1
    assert book.positions[0]["screen_date"] == "2026-07-01"
    assert book.positions[0]["last_screen_date"] == "2026-07-03"


def test_open_position_respects_sector_cap(tmp_path):
    path = tmp_path / "positions.json"
    book = SwingPositionBook({
        "swing_book_path": str(path),
        "swing_max_per_sector": 2,
        "swing_max_positions": 10,
    })
    for i in range(2):
        assert book.open_position(_pick(f"IT{i}.NS"), "2026-07-01") is not None
    blocked = book.open_position(_pick("IT2.NS"), "2026-07-01")
    assert blocked is None
    assert book.open_count() == 2
    other = book.open_position(
        SwingPick(
            symbol="FIN.NS",
            stock_name="Fin Co",
            sector="Financial Services",
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
            adx=18.0,
            volume_spike_pct=50.0,
            relative_volume=1.5,
            risk_pct=5.0,
            market_cap_cr=10000.0,
            avg_traded_value_cr=50.0,
        ),
        "2026-07-01",
    )
    assert other is not None
    assert book.open_count() == 3


def test_exit_scan_closes_on_first_intermediate_target_hit(tmp_path, monkeypatch):
    book = SwingPositionBook({"swing_book_path": str(tmp_path / "positions.json")})
    book.open_position(_pick(), "2026-07-01")
    hist = pd.DataFrame(
        {
            "Open": [100.0, 108.0, 110.0],
            "High": [102.0, 116.0, 112.0],
            "Low": [98.0, 106.0, 108.0],
            "Close": [101.0, 110.0, 111.0],
            "Volume": [1000, 1000, 1000],
        },
        index=pd.to_datetime(["2026-07-01", "2026-07-02", "2026-07-03"]),
    )
    monkeypatch.setattr(book, "_history", lambda *_args, **_kwargs: hist)
    monkeypatch.setattr(book, "_update_trailing_stop", lambda *_args, **_kwargs: None)

    summary = book.evaluate_and_close_exits(as_of="2026-07-03")

    assert summary["closed"][0]["reason"] == "target_1"
    assert summary["closed"][0]["exit_date"] == "2026-07-02"
