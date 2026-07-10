"""Tests for grounded portfolio review facts and tables."""

from __future__ import annotations

from tradingagents.portfolio_review.facts import _position_facts, _risk_flags
from tradingagents.portfolio_review.grounding import (
    build_grounding_sheet,
    validate_narrative,
)
from tradingagents.portfolio_review.tables import open_positions_table, render_tables


def test_position_facts_open_unrealized():
    p = {
        "ticker": "TEST.NS",
        "stock_name": "Test Co",
        "status": "open",
        "screen_date": "2026-07-01",
        "entry_price": 100.0,
        "shares": 10,
        "notional": 1000.0,
        "stop_loss": 95.0,
        "trailing_stop": 95.0,
        "rsi": 55.0,
        "remaining_pct": 100.0,
    }
    row = _position_facts("swing", "Swing", p, as_of="2026-07-09", price=110.0)
    assert row["unrealized_inr"] == 100.0
    assert row["return_pct"] == 10.0
    assert row["market_value_inr"] == 1100.0
    assert row["stop_cushion_pct"] is not None


def test_risk_flag_stop_tight():
    positions = [{
        "id": "swing|X.NS|open",
        "desk": "swing",
        "ticker": "X.NS",
        "symbol": "X",
        "status": "open",
        "stop_cushion_pct": 1.5,
        "stop_loss": 99.0,
        "current_price": 100.0,
        "return_pct": -1.0,
    }]
    desks = [{
        "id": "swing",
        "label": "Swing",
        "cli_prefix": "swing",
        "open_count": 5,
        "max_positions": 20,
        "pending_replacements": 0,
    }]
    flags = _risk_flags(positions, desks)
    assert any(f["severity"] == "high" for f in flags)


def test_open_positions_table_has_ltp_and_pnl():
    facts = {
        "positions": [{
            "status": "open",
            "desk": "swing",
            "desk_label": "Swing",
            "symbol": "ABC",
            "shares": 10,
            "entry_price": 100,
            "current_price": 105,
            "market_value_inr": 1050,
            "return_pct": 5.0,
            "unrealized_inr": 50,
            "stop_cushion_pct": 4.0,
            "signal_summary": "RSI=55",
        }],
    }
    md = open_positions_table(facts)
    assert "LTP" in md
    assert "Mkt value" in md
    assert "P&L %" in md
    assert "105" in md
    assert "₹50" in md or "50" in md


def test_tables_render():
    facts = {
        "summary": {
            "desks_tracked": 1,
            "open_positions": 1,
            "closed_positions": 0,
            "total_realized_inr": 0,
            "total_unrealized_inr": 50,
            "total_pnl_inr": 50,
            "desk_capital_inr": 100_000,
        },
        "as_of_date": "2026-07-10",
        "desks": [{
            "label": "Swing",
            "open_count": 1,
            "closed_count": 0,
            "realized_inr": 0,
            "unrealized_inr": 50,
            "total_inr": 50,
            "win_rate_pct": None,
            "utilization_pct": 5.0,
        }],
        "positions": [{
            "status": "open",
            "desk": "swing",
            "desk_label": "Swing",
            "symbol": "ABC",
            "shares": 5,
            "entry_price": 100,
            "current_price": 105,
            "market_value_inr": 525,
            "return_pct": 5.0,
            "unrealized_inr": 50,
            "stop_cushion_pct": 4.0,
            "signal_summary": "RSI=55",
        }],
        "risk_flags": [],
    }
    md = render_tables(facts)
    assert "Desk summary" in md
    assert "ABC" in md


def test_grounding_sheet_and_validate():
    facts = {
        "as_of_date": "2026-07-10",
        "summary": {
            "total_pnl_inr": 6834,
            "total_realized_inr": 1444,
            "total_unrealized_inr": 5390,
            "open_positions": 64,
            "closed_positions": 11,
            "desk_capital_inr": 100_000,
        },
        "desks": [],
        "positions": [{
            "status": "open",
            "desk": "swing",
            "ticker": "MAPMYINDIA.NS",
            "symbol": "MAPMYINDIA",
            "entry_price": 938.35,
            "current_price": 1071.7,
            "shares": 5,
            "market_value_inr": 5358.5,
            "unrealized_inr": 678,
            "return_pct": 14.5,
            "realized_inr": 0,
            "total_inr": 678,
        }],
        "risk_flags": [],
        "top_contributors": [],
        "top_detractors": [],
    }
    sheet = build_grounding_sheet(facts)
    assert "6834" in sheet
    assert "MAPMYINDIA" in sheet
    ok, issues = validate_narrative(
        "Portfolio P&L is 6834 INR. [swing:MAPMYINDIA.NS] contributes 678.",
        facts,
        "| Swing | MAPMYINDIA | 678 | +14.5% |",
    )
    assert ok, issues
