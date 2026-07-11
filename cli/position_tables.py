"""Rich tables for paper desk positions (shared meta columns + closed ledger)."""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Optional

from rich.console import Console
from rich.table import Table
from rich import box

from tradingagents.paper.position_display import (
    budget_ok_label,
    days_in_trade,
    entry_date_from_position,
    fmt_inr,
    partial_exit_legs,
    position_shares,
    purchase_notional,
    slot_alloc,
    within_budget,
)


def add_open_meta_columns(t: Table) -> None:
    t.add_column("Entry", justify="right")
    t.add_column("Days", justify="right")
    t.add_column("Qty", justify="right")
    t.add_column("Purchase", justify="right")
    t.add_column("Budget", justify="right")
    t.add_column("OK", justify="center")


def open_meta_cells(p: dict, as_of: Optional[str] = None) -> list[str]:
    as_of = as_of or datetime.now().strftime("%Y-%m-%d")
    ok = budget_ok_label(p)
    ok_style = ok if ok == "OK" else f"[red]{ok}[/red]"
    return [
        entry_date_from_position(p),
        str(days_in_trade(p, as_of)),
        str(int(position_shares(p))) if position_shares(p) else "—",
        fmt_inr(purchase_notional(p)),
        fmt_inr(slot_alloc(p)) if slot_alloc(p) else "—",
        ok_style,
    ]


def print_closed_positions_ledger(
    console: Console,
    closed: list,
    *,
    title: str = "Closed positions",
    limit: int = 20,
    show_alpha: bool = True,
) -> None:
    if not closed:
        return
    t = Table(box=box.SIMPLE_HEAD, title=title)
    t.add_column("Ticker", style="bold")
    t.add_column("Entry", justify="right")
    t.add_column("Exit", justify="right")
    t.add_column("Days", justify="right")
    t.add_column("Qty", justify="right")
    t.add_column("Purchase", justify="right")
    t.add_column("Budget", justify="right")
    t.add_column("OK", justify="center")
    t.add_column("Return", justify="right")
    if show_alpha:
        t.add_column("Alpha", justify="right")
    t.add_column("P&L", justify="right")
    t.add_column("Reason")

    for p in closed[-limit:]:
        ret = p.get("raw_return")
        alpha = p.get("alpha_return")
        rc = "green" if (ret or 0) > 0 else "red"
        ac = "green" if (alpha or 0) > 0 else "red"
        pnl = p.get("rupee_pnl")
        ok = budget_ok_label(p)
        row = [
            p["ticker"].replace(".NS", ""),
            entry_date_from_position(p),
            p.get("exit_date", ""),
            str(days_in_trade(p)),
            str(int(position_shares(p))) if position_shares(p) else "—",
            fmt_inr(purchase_notional(p)),
            fmt_inr(slot_alloc(p)) if slot_alloc(p) else "—",
            f"[red]{ok}[/red]" if ok != "OK" else ok,
            f"[{rc}]{(ret or 0) * 100:+.1f}%[/{rc}]" if ret is not None else "—",
        ]
        if show_alpha:
            row.append(
                f"[{ac}]{(alpha or 0) * 100:+.1f}%[/{ac}]" if alpha is not None else "n/a"
            )
        row.append(fmt_inr(float(pnl)) if pnl is not None else "—")
        row.append(str(p.get("exit_reason") or ""))
        t.add_row(*row)

        for i, leg in enumerate(partial_exit_legs(p)):
            leg_pnl = leg.get("rupee_pnl")
            prefix = "  └" if i == len(partial_exit_legs(p)) - 1 else "  ├"
            leg_row = [
                f"[dim]{prefix} {leg.get('reason', 'leg')}[/dim]",
                "",
                str(leg.get("date", "")),
                "",
                f"{leg.get('pct', 0):.0f}%",
                fmt_inr(float(leg.get("price") or 0)),
                "",
                "",
                f"{(leg.get('return') or 0) * 100:+.1f}%" if leg.get("return") is not None else "—",
            ]
            if show_alpha:
                leg_row.append("")
            leg_row.append(fmt_inr(float(leg_pnl)) if leg_pnl is not None else "—")
            leg_row.append("[dim]partial[/dim]")
            t.add_row(*leg_row)

    console.print(t)


def print_rs_paper_open(console: Console, open_positions: list) -> None:
    as_of = datetime.now().strftime("%Y-%m-%d")
    t = Table(box=box.SIMPLE_HEAD, title="Open paper positions")
    t.add_column("Ticker", style="bold")
    t.add_column("Rating")
    add_open_meta_columns(t)
    t.add_column("Entry Rs", justify="right")
    t.add_column("Signals")
    for p in open_positions:
        t.add_row(
            p["ticker"],
            p["rating"],
            *open_meta_cells(p, as_of),
            f"{p['entry_price']:.2f}",
            ", ".join(p.get("signals", [])) or "-",
        )
    console.print(t)


def print_rs_paper_closed(console: Console, closed: list) -> None:
    print_closed_positions_ledger(console, closed, title="Closed paper trades", show_alpha=True)
