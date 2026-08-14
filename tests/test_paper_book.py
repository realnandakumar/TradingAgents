"""Offline unit tests for the paper-trading book."""

import json

import pytest

from tradingagents.paper.book import PaperBook
from tradingagents.paper.exits import ExitReason, evaluate_bar_exits

pytestmark = pytest.mark.unit


def _book(tmp_path, **overrides):
    cfg = {
        "paper_book_path": str(tmp_path / "book.json"),
        "desk_capital": 200_000.0,
        "paper_max_positions": 20,
        "paper_max_per_sector": 4,
        "paper_holding_days": 20,
    }
    cfg.update(overrides)
    return PaperBook(cfg)


def _levels(entry=100.0, stop=95.0, target=110.0):
    return {
        "stoploss": stop,
        "target": target,
        "stop_pct": round(-100.0 * (entry - stop) / entry, 2),
        "target_pct": round(100.0 * (target - entry) / entry, 2),
    }


def test_open_position_sizes_equal_weight(tmp_path):
    book = _book(tmp_path)
    pos = book.open_position(
        "HAL.NS", "BUY", 4000.0, "2026-06-01",
        signals=["rsi_breakout"],
        levels=_levels(4000, 3800, 4400),
        sector="Capital Goods",
    )
    assert pos is not None
    assert pos["alloc"] == pytest.approx(10_000.0)
    assert pos["shares"] == 2  # floor(10000/4000); notional ≤ slot
    assert pos["notional"] == pytest.approx(8_000.0)
    assert pos["target"] == 4400.0
    assert pos["sector"] == "Capital Goods"
    assert book.has_open_position("HAL.NS")


def test_duplicate_open_is_blocked(tmp_path):
    book = _book(tmp_path)
    lv = _levels(4000, 3800, 4400)
    assert book.open_position("HAL.NS", "BUY", 4000.0, "2026-06-01", levels=lv, sector="IT") is not None
    assert book.open_position("HAL.NS", "BUY", 4100.0, "2026-06-02", levels=lv, sector="IT") is None


def test_invalid_levels_rejected(tmp_path):
    book = _book(tmp_path)
    assert book.open_position("HAL.NS", "BUY", 4000.0, "2026-06-01", levels=None) is None
    assert book.open_position(
        "HAL.NS", "BUY", 4000.0, "2026-06-01",
        levels={"stoploss": 4100, "target": 4200},
    ) is None


def test_sector_cap_blocks_fifth(tmp_path):
    book = _book(tmp_path)
    for i in range(4):
        assert book.open_position(
            f"T{i}.NS", "BUY", 100.0, "2026-06-01",
            levels=_levels(),
            sector="IT",
        ) is not None
    assert book.open_position(
        "T4.NS", "BUY", 100.0, "2026-06-01",
        levels=_levels(),
        sector="IT",
    ) is None
    assert book.open_count() == 4


def test_hard_max_positions(tmp_path):
    book = _book(tmp_path, paper_max_positions=2, desk_capital=20_000.0)
    assert book.open_position("A.NS", "BUY", 100.0, "2026-06-01", levels=_levels(), sector="A") is not None
    assert book.open_position("B.NS", "BUY", 100.0, "2026-06-01", levels=_levels(), sector="B") is not None
    assert book.open_position("C.NS", "BUY", 100.0, "2026-06-01", levels=_levels(), sector="C") is None


def test_persistence_across_instances(tmp_path):
    book = _book(tmp_path)
    book.open_position(
        "TCS.NS", "BUY", 3500.0, "2026-06-01",
        levels=_levels(3500, 3300, 3800),
        sector="IT",
    )
    reopened = _book(tmp_path)
    assert reopened.has_open_position("TCS.NS")


def test_evaluate_bar_stop_and_target():
    import pandas as pd

    pos = {
        "entry_date": "2026-06-01",
        "stoploss": 95.0,
        "target": 110.0,
    }
    idx = pd.to_datetime(["2026-06-01", "2026-06-02"])
    hist = pd.DataFrame(
        {"Open": [100, 100], "High": [101, 112], "Low": [99, 98], "Close": [100, 111]},
        index=idx,
    )
    action = evaluate_bar_exits(pos, hist.iloc[1], "2026-06-02", 20, hist)
    assert action is not None
    assert action.reason == ExitReason.TARGET
    assert action.exit_price == 110.0

    hist2 = pd.DataFrame(
        {"Open": [100, 100], "High": [101, 100], "Low": [99, 94], "Close": [100, 96]},
        index=idx,
    )
    action2 = evaluate_bar_exits(pos, hist2.iloc[1], "2026-06-02", 20, hist2)
    assert action2 is not None
    assert action2.reason == ExitReason.STOP


def test_nan_ohlc_does_not_time_exit():
    import pandas as pd

    pos = {
        "entry_date": "2026-06-01",
        "stoploss": 95.0,
        "target": 110.0,
    }
    idx = pd.to_datetime(["2026-06-01", "2026-06-02"])
    hist = pd.DataFrame(
        {"Open": [100, float("nan")], "High": [101, float("nan")], "Low": [99, float("nan")], "Close": [100, float("nan")]},
        index=idx,
    )
    assert evaluate_bar_exits(pos, hist.iloc[1], "2026-06-02", 1, hist) is None


def test_stats_overall_and_per_signal(tmp_path):
    path = tmp_path / "book.json"
    path.write_text(json.dumps({"positions": [
        {"ticker": "A.NS", "rating": "BUY", "signals": ["rsi_breakout", "cup_and_handle"],
         "entry_date": "2026-05-01", "entry_price": 100.0, "shares": 10.0, "alloc": 1000.0,
         "status": "closed", "exit_date": "2026-05-29", "exit_price": 110.0,
         "raw_return": 0.10, "alpha_return": 0.06, "holding_days_actual": 20,
         "exit_reason": "target", "rupee_pnl": 100.0},
        {"ticker": "B.NS", "rating": "BUY", "signals": ["rsi_breakout"],
         "entry_date": "2026-05-01", "entry_price": 100.0, "shares": 10.0, "alloc": 1000.0,
         "status": "closed", "exit_date": "2026-05-29", "exit_price": 90.0,
         "raw_return": -0.10, "alpha_return": -0.12, "holding_days_actual": 20,
         "exit_reason": "stop_loss", "rupee_pnl": -100.0},
    ]}))
    book = PaperBook({"paper_book_path": str(path), "desk_capital": 200_000.0})
    stats = book.stats()

    assert stats["overall"]["trades"] == 2
    assert stats["overall"]["win_rate"] == 50.0
    assert stats["overall"]["avg_return"] == pytest.approx(0.0)
    assert stats["per_signal"]["rsi_breakout"]["trades"] == 2
    assert stats["per_signal"]["cup_and_handle"]["win_rate"] == 100.0
    assert "target" in stats["by_exit_reason"]
