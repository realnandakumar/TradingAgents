"""Shared position metadata for CLI and dashboards (dates, qty, notional, days held)."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Optional


def entry_date_from_position(p: dict) -> str:
    return str(p.get("entry_date") or p.get("screen_date") or "")


def position_shares(p: dict) -> float:
    return float(p.get("shares") or 0)


def purchase_notional(p: dict) -> float:
    if p.get("notional") is not None:
        return float(p["notional"])
    entry = float(p.get("entry_price") or 0)
    return round(position_shares(p) * entry, 2)


def slot_alloc(p: dict) -> float:
    return float(p.get("alloc") or 0)


def within_budget(p: dict, tolerance: float = 0.01) -> bool:
    alloc = slot_alloc(p)
    if alloc <= 0:
        return True
    return purchase_notional(p) <= alloc * (1 + tolerance)


def _parse_day(s: str) -> date:
    return datetime.strptime(s[:10], "%Y-%m-%d").date()


def trading_days_between_calendar(start: str, end: str) -> int:
    """Weekday count inclusive (Mon–Fri proxy for NSE sessions)."""
    if not start or not end:
        return 0
    s, e = _parse_day(start), _parse_day(end)
    if e < s:
        return 0
    count = 0
    d = s
    while d <= e:
        if d.weekday() < 5:
            count += 1
        d += timedelta(days=1)
    return count


def as_of_trading_day(as_of: Optional[str] = None) -> str:
    as_of = as_of or datetime.now().strftime("%Y-%m-%d")
    d = _parse_day(as_of)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.strftime("%Y-%m-%d")


def days_in_trade(p: dict, as_of: Optional[str] = None) -> int:
    entry = entry_date_from_position(p)
    if not entry:
        return 0
    if p.get("status") == "closed":
        stored = p.get("trading_days_held")
        if stored is not None:
            return int(stored)
        stored = p.get("holding_days_actual")
        if stored is not None:
            return int(stored)
        exit_d = p.get("exit_date")
        if exit_d:
            return trading_days_between_calendar(entry, str(exit_d))
        return 0
    end = as_of_trading_day(as_of)
    return trading_days_between_calendar(entry, end)


def partial_exit_legs(p: dict) -> list[dict[str, Any]]:
    legs = p.get("partial_exits") or []
    return [leg for leg in legs if isinstance(leg, dict)]


def fmt_inr(value: float, *, use_rupee: bool = False) -> str:
    sym = "\u20b9" if use_rupee else "Rs"
    return f"{sym}{value:,.0f}"


def budget_ok_label(p: dict) -> str:
    return "OK" if within_budget(p) else "OVER"
