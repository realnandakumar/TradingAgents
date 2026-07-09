"""Unit tests for Pattern Forecast position book."""

import pytest

from tradingagents.screening.pattern_forecast_engine import PatternForecastSignal
from tradingagents.screening.pattern_forecast_screener import PatternForecastPick
from tradingagents.pattern_forecast.book import STRATEGY_NAME, PatternForecastPositionBook

pytestmark = pytest.mark.unit


def _make_pick(symbol: str = "TEST.NS", direction: str = "UP") -> PatternForecastPick:
    sig = PatternForecastSignal(
        symbol=symbol,
        direction=direction,
        probability=82.5,
        correlation=0.825,
        close=100.0,
        projected_close_5d=105.0,
        projected_max_high_5d=108.0,
        projected_min_low_5d=96.0,
        stop_loss=97.0,
        stop_loss_pct=-3.0,
        projected_move_pct=5.0,
        projected_max_pct=8.0,
        analogue_end_date="2025-06-01",
        remark="UP - corr 0.83",
        stock_name="Test Co",
        sector="IT",
    )
    return PatternForecastPick(signal=sig, stock_name="Test Co", sector="IT")


def test_strategy_name():
    assert STRATEGY_NAME == "pattern_forecast"


def test_open_up_position(tmp_path):
    cfg = {
        "pattern_forecast_book_path": str(tmp_path / "positions.json"),
        "pattern_forecast_max_positions": 10,
    }
    book = PatternForecastPositionBook(cfg)
    pos = book.open_position(_make_pick(), "2026-07-08")
    assert pos is not None
    assert pos["ticker"] == "TEST.NS"
    assert pos["entry_price"] == 100.0
    assert pos["stop_loss"] == 97.0
    assert pos["target_max"] == 108.0
    assert pos["probability"] == 82.5
    assert book.open_count() == 1


def test_skips_down_signals(tmp_path):
    cfg = {"pattern_forecast_book_path": str(tmp_path / "positions.json")}
    book = PatternForecastPositionBook(cfg)
    pos = book.open_position(_make_pick(direction="DOWN"), "2026-07-08")
    assert pos is None
    assert book.open_count() == 0


def test_rejects_missing_stop(tmp_path):
    cfg = {"pattern_forecast_book_path": str(tmp_path / "positions.json")}
    book = PatternForecastPositionBook(cfg)
    pick = _make_pick()
    pick.signal.stop_loss = 100.0
    assert book.open_position(pick, "2026-07-08") is None
