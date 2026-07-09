"""Unit tests for shared paper position sizing."""

import pytest

from tradingagents.paper.sizing import (
    clear_closed_and_resize_open,
    compute_position_size,
    leg_rupee_pnl,
    skip_exit_for_entry_day,
    total_rupee_pnl_from_legs,
)

pytestmark = pytest.mark.unit


def test_compute_position_size_whole_shares():
    # ₹1L / 20 slots = ₹5,000 per slot; at ₹4000 → round(1.25) = 1 share
    s = compute_position_size(100_000, 20, 4000.0)
    assert s["alloc"] == pytest.approx(5000.0)
    assert s["shares"] == 1
    assert s["notional"] == pytest.approx(4000.0)


def test_compute_position_size_exact_lot():
    s = compute_position_size(100_000, 10, 400.0)
    assert s["shares"] == 25
    assert s["notional"] == pytest.approx(10_000.0)


def test_compute_position_size_rounds_half_up():
    s = compute_position_size(100_000, 10, 4000.0)
    assert s["shares"] == 3  # 10000/4000 = 2.5 -> 3


def test_compute_position_size_minimum_one_share():
    s = compute_position_size(100_000, 20, 50_000.0)
    assert s["shares"] == 1


def test_skip_exit_for_entry_day():
    assert skip_exit_for_entry_day("2026-07-09", "2026-07-09") is True
    assert skip_exit_for_entry_day("2026-07-08", "2026-07-09") is False


def test_leg_rupee_pnl_partial():
    assert leg_rupee_pnl(10, 100.0, 110.0, 75.0) == pytest.approx(75.0)


def test_total_rupee_pnl_from_legs():
    legs = [{"rupee_pnl": 75.0}, {"rupee_pnl": 25.0}]
    assert total_rupee_pnl_from_legs(legs) == pytest.approx(100.0)


def test_clear_closed_and_resize_open():
    positions = [
        {"status": "closed", "entry_price": 100.0},
        {"status": "open", "entry_price": 4000.0},
    ]
    cleared, resized = clear_closed_and_resize_open(positions, 100_000, 20)
    assert cleared == 1
    assert resized == 1
    assert len(positions) == 1
    assert positions[0]["shares"] == 1
