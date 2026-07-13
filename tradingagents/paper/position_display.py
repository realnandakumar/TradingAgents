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


def sale_proceeds(p: dict) -> float:
    """Total rupees received on exit (all legs), using qty × leg price × leg %."""
    shares = position_shares(p)
    legs = partial_exit_legs(p)
    if legs and shares > 0:
        total = sum(
            shares * float(leg.get("price") or 0) * float(leg.get("pct") or 0) / 100.0
            for leg in legs
        )
        return round(total, 2)
    exit_p = float(p.get("exit_price") or 0)
    if shares > 0 and exit_p > 0:
        return round(shares * exit_p, 2)
    return 0.0


def average_exit_price(p: dict) -> Optional[float]:
    shares = position_shares(p)
    sale = sale_proceeds(p)
    if shares <= 0 or sale <= 0:
        exit_p = p.get("exit_price")
        return float(exit_p) if exit_p is not None else None
    return round(sale / shares, 2)


def realized_rupee_pnl(p: dict) -> Optional[float]:
    """Gain in ₹ = sale proceeds − purchase cost (qty × entry)."""
    purchase = purchase_notional(p)
    if purchase <= 0:
        stored = p.get("rupee_pnl")
        return float(stored) if stored is not None else None
    sale = sale_proceeds(p)
    if sale <= 0:
        stored = p.get("rupee_pnl")
        return float(stored) if stored is not None else None
    return round(sale - purchase, 2)


def realized_return_pct(p: dict) -> Optional[float]:
    """Gain % on capital deployed (purchase notional), not per-share price move."""
    purchase = purchase_notional(p)
    pnl = realized_rupee_pnl(p)
    if purchase <= 0 or pnl is None:
        return None
    return round(100.0 * pnl / purchase, 2)


def leg_sale_proceeds(p: dict, leg: dict) -> float:
    shares = position_shares(p)
    return round(
        shares * float(leg.get("price") or 0) * float(leg.get("pct") or 0) / 100.0,
        2,
    )


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
        if stored is not None and (int(stored) > 0 or not p.get("exit_date")):
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


def ledger_exit_legs(p: dict) -> list[dict[str, Any]]:
    """Leg breakdown for closed-trade ledger — only when there were multiple exits."""
    legs = partial_exit_legs(p)
    if len(legs) <= 1:
        return []
    return legs


def fmt_inr(value: float, *, use_rupee: bool = False) -> str:
    sym = "\u20b9" if use_rupee else "Rs"
    return f"{sym}{value:,.0f}"


def budget_ok_label(p: dict) -> str:
    return "OK" if within_budget(p) else "OVER"
