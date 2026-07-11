"""Tests for tradingagents.paper.position_display helpers."""

from tradingagents.paper.position_display import (
    budget_ok_label,
    days_in_trade,
    entry_date_from_position,
    partial_exit_legs,
    position_shares,
    purchase_notional,
    slot_alloc,
    trading_days_between_calendar,
    within_budget,
)


def test_entry_date_prefers_entry_date():
    p = {"entry_date": "2026-01-10", "screen_date": "2026-01-08"}
    assert entry_date_from_position(p) == "2026-01-10"


def test_entry_date_falls_back_to_screen_date():
    p = {"screen_date": "2026-01-08"}
    assert entry_date_from_position(p) == "2026-01-08"


def test_purchase_notional_from_stored_value():
    p = {"notional": 125000, "shares": 100, "entry_price": 1000}
    assert purchase_notional(p) == 125000


def test_purchase_notional_computed_from_shares_and_entry():
    p = {"shares": 50, "entry_price": 123.45}
    assert purchase_notional(p) == 6172.5


def test_within_budget_ok_when_notional_le_alloc():
    p = {"notional": 99000, "alloc": 100000}
    assert within_budget(p) is True
    assert budget_ok_label(p) == "OK"


def test_within_budget_over_when_notional_exceeds_alloc():
    p = {"notional": 105000, "alloc": 100000}
    assert within_budget(p) is False
    assert budget_ok_label(p) == "OVER"


def test_within_budget_ok_when_no_alloc():
    p = {"notional": 50000}
    assert within_budget(p) is True


def test_trading_days_between_calendar_weekdays_only():
    # Mon 2026-01-05 through Fri 2026-01-09 = 5 weekdays
    assert trading_days_between_calendar("2026-01-05", "2026-01-09") == 5
    # Spanning a weekend: Fri 2026-01-09 to Mon 2026-01-12 = 2 weekdays
    assert trading_days_between_calendar("2026-01-09", "2026-01-12") == 2


def test_days_in_trade_open_position():
    p = {"status": "open", "screen_date": "2026-01-05"}
    assert days_in_trade(p, as_of="2026-01-09") == 5


def test_days_in_trade_closed_uses_stored():
    p = {
        "status": "closed",
        "screen_date": "2026-01-05",
        "exit_date": "2026-01-20",
        "trading_days_held": 12,
    }
    assert days_in_trade(p) == 12


def test_days_in_trade_closed_computed_from_exit_date():
    p = {
        "status": "closed",
        "screen_date": "2026-01-05",
        "exit_date": "2026-01-09",
    }
    assert days_in_trade(p) == 5


def test_partial_exit_legs_filters_non_dicts():
    p = {
        "partial_exits": [
            {"date": "2026-01-10", "pct": 50, "price": 110},
            "bad",
            {"date": "2026-01-15", "pct": 50, "price": 115},
        ]
    }
    legs = partial_exit_legs(p)
    assert len(legs) == 2
    assert legs[0]["pct"] == 50


def test_position_shares_and_slot_alloc_defaults():
    assert position_shares({}) == 0
    assert slot_alloc({}) == 0
