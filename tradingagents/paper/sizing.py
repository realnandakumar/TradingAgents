"""Shared position sizing and rupee P&L helpers for paper strategy books."""

from __future__ import annotations

import math
from typing import List


def compute_position_size(
    desk_capital: float,
    max_positions: int,
    entry_price: float,
) -> dict:
    """Equal-weight slot sizing with whole-share rounding.

    ``alloc_per_slot = desk_capital / max_positions``
    ``shares = max(1, round_half_up(alloc_per_slot / entry_price))``
    """
    if entry_price <= 0:
        return {"shares": 0, "alloc": 0.0, "notional": 0.0}
    alloc = desk_capital / max(max_positions, 1)
    shares = max(1, math.floor(alloc / entry_price + 0.5))
    notional = round(shares * entry_price, 2)
    return {"shares": shares, "alloc": round(alloc, 2), "notional": notional}


def skip_exit_for_entry_day(screen_date: str, as_of: str) -> bool:
    """Positions opened on ``as_of`` cannot exit on the same calendar day."""
    return screen_date == as_of


def leg_rupee_pnl(
    shares: float,
    entry_price: float,
    exit_price: float,
    exit_pct: float,
) -> float:
    """Rupee P&L for one exit leg (partial or full remainder)."""
    return round(shares * (exit_price - entry_price) * (exit_pct / 100.0), 2)


def total_rupee_pnl_from_legs(partial_exits: List[dict]) -> float:
    return round(sum(float(leg.get("rupee_pnl") or 0) for leg in partial_exits), 2)


def ensure_sizing_fields(
    p: dict,
    desk_capital: float,
    max_positions: int,
) -> bool:
    """Backfill shares/alloc/notional on legacy open positions."""
    if p.get("status") != "open":
        return False
    entry = float(p.get("entry_price") or 0)
    if entry <= 0:
        return False
    sizing = compute_position_size(desk_capital, max_positions, entry)
    changed = False
    for key in ("shares", "alloc", "notional"):
        if p.get(key) is None:
            p[key] = sizing[key]
            changed = True
    return changed


def resize_open_position(
    p: dict,
    desk_capital: float,
    max_positions: int,
) -> bool:
    """Recompute shares for an open position from its entry price."""
    if p.get("status") != "open":
        return False
    entry = float(p.get("entry_price") or 0)
    if entry <= 0:
        return False
    sizing = compute_position_size(desk_capital, max_positions, entry)
    p["shares"] = sizing["shares"]
    p["alloc"] = sizing["alloc"]
    p["notional"] = sizing["notional"]
    return True


def clear_closed_and_resize_open(
    positions: List[dict],
    desk_capital: float,
    max_positions: int,
) -> tuple[int, int]:
    """Drop closed history and resize open positions. Returns (cleared, resized)."""
    closed = sum(1 for p in positions if p.get("status") == "closed")
    kept = [p for p in positions if p.get("status") == "open"]
    resized = 0
    for p in kept:
        if resize_open_position(p, desk_capital, max_positions):
            resized += 1
    positions[:] = kept
    return closed, resized
