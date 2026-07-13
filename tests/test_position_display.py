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


def test_days_in_trade_closed_computed_when_stored_zero():
    p = {
        "status": "closed",
        "screen_date": "2026-07-04",
        "exit_date": "2026-07-09",
        "trading_days_held": 0,
    }
    # Fri 4 through Wed 9 = 4 weekdays
    assert days_in_trade(p) == 4


def test_ledger_exit_legs_single_full_exit_hidden():
    from tradingagents.paper.position_display import ledger_exit_legs

    p = {
        "partial_exits": [
            {"date": "2026-07-09", "pct": 100.0, "reason": "foreclosure", "rupee_pnl": 10.0},
        ]
    }
    assert ledger_exit_legs(p) == []


def test_ledger_exit_legs_multi_leg_shown():
    from tradingagents.paper.position_display import ledger_exit_legs

    p = {
        "partial_exits": [
            {"date": "2026-07-08", "pct": 75.0, "reason": "target_2_partial"},
            {"date": "2026-07-12", "pct": 25.0, "reason": "trail_stop"},
        ]
    }
    assert len(ledger_exit_legs(p)) == 2


def test_sale_proceeds_and_gain_single_exit():
    from tradingagents.paper.position_display import (
        realized_return_pct,
        realized_rupee_pnl,
        sale_proceeds,
    )

    p = {
        "shares": 6,
        "entry_price": 1765.1,
        "notional": 10590.6,
        "exit_price": 1786.5,
        "partial_exits": [
            {
                "date": "2026-07-12",
                "price": 1786.5,
                "pct": 100.0,
                "reason": "foreclosure",
                "rupee_pnl": 128.4,
            }
        ],
    }
    assert sale_proceeds(p) == 10719.0
    assert realized_rupee_pnl(p) == 128.4
    assert realized_return_pct(p) == 1.21


def test_sale_proceeds_blended_partial_legs():
    from tradingagents.paper.position_display import realized_rupee_pnl, sale_proceeds

    p = {
        "shares": 10,
        "entry_price": 100.0,
        "notional": 1000.0,
        "partial_exits": [
            {"price": 120.0, "pct": 75.0, "rupee_pnl": 150.0},
            {"price": 110.0, "pct": 25.0, "rupee_pnl": 25.0},
        ],
    }
    assert sale_proceeds(p) == 1175.0
    assert realized_rupee_pnl(p) == 175.0
