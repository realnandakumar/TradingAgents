"""Render markdown tables from portfolio facts (no LLM)."""

from __future__ import annotations

from typing import List


def _inr(v) -> str:
    if v is None:
        return "—"
    return f"₹{float(v):,.0f}"


def _pct(v) -> str:
    if v is None:
        return "—"
    return f"{float(v):+.1f}%"


def desk_summary_table(facts: dict) -> str:
    lines = [
        "## Desk summary",
        "",
        "| Desk | Open | Closed | Realized | Unrealized | Total | Win% | Util% |",
        "|------|-----:|-------:|---------:|-----------:|------:|-----:|------:|",
    ]
    for d in facts["desks"]:
        wr = d.get("win_rate_pct")
        wr_s = f"{wr:.1f}" if wr is not None else "—"
        lines.append(
            f"| {d['label']} | {d['open_count']} | {d['closed_count']} | "
            f"{_inr(d['realized_inr'])} | {_inr(d['unrealized_inr'])} | "
            f"{_inr(d['total_inr'])} | {wr_s} | {d['utilization_pct']:.0f}% |"
        )
    s = facts["summary"]
    lines.extend([
        "",
        f"**Portfolio total:** realized {_inr(s['total_realized_inr'])}, "
        f"unrealized {_inr(s['total_unrealized_inr'])}, "
        f"**combined {_inr(s['total_pnl_inr'])}** "
        f"({s['open_positions']} open, {s['closed_positions']} closed).",
        "",
    ])
    return "\n".join(lines)


def open_positions_table(facts: dict, limit: int = 80) -> str:
    open_pos = [p for p in facts["positions"] if p["status"] == "open"]
    open_pos.sort(key=lambda x: (x.get("desk") or x.get("desk_label", ""), x.get("symbol", "")))
    lines = [
        "## Open positions (live)",
        "",
        "LTP = last traded price from Yahoo (delayed). P&L = unrealized on remaining shares.",
        "",
        "| Desk | Ticker | Sh | Entry | LTP | Mkt value | P&L | P&L % | Stop% | Signal |",
        "|------|--------|---:|------:|----:|----------:|----:|------:|------:|--------|",
    ]
    for p in open_pos[:limit]:
        lines.append(
            f"| {p['desk_label']} | {p['symbol']} | {p.get('shares', 0)} | "
            f"{p['entry_price'] or '—'} | {p['current_price'] or '—'} | "
            f"{_inr(p.get('market_value_inr'))} | {_inr(p['unrealized_inr'])} | "
            f"{_pct(p['return_pct'])} | {_pct(p['stop_cushion_pct'])} | "
            f"{p['signal_summary'][:40]} |"
        )
    if len(open_pos) > limit:
        lines.append(f"\n*({len(open_pos) - limit} more open positions omitted)*")
    lines.append("")
    return "\n".join(lines)


def closed_trades_table(facts: dict) -> str:
    closed = [p for p in facts["positions"] if p["status"] == "closed"]
    if not closed:
        return "## Closed trades\n\n*No closed positions in books.*\n"
    closed.sort(key=lambda x: x.get("exit_date") or "", reverse=True)
    lines = [
        "## Closed trades",
        "",
        "| Desk | Ticker | Exit | Realized | Return | Reason | Outcome |",
        "|------|--------|------|---------:|-------:|--------|---------|",
    ]
    for p in closed:
        lines.append(
            f"| {p['desk_label']} | {p['symbol']} | {p.get('exit_date') or '—'} | "
            f"{_inr(p['realized_inr'])} | {_pct(p['return_pct'])} | "
            f"{p.get('exit_reason') or '—'} | {p.get('outcome') or '—'} |"
        )
    lines.append("")
    return "\n".join(lines)


def risk_flags_table(facts: dict) -> str:
    flags: List[dict] = facts.get("risk_flags") or []
    if not flags:
        return "## Risk flags\n\n*No automated risk flags.*\n"
    lines = [
        "## Risk flags (rule-based)",
        "",
        "| Severity | Desk | Ticker | Fact | Suggested action |",
        "|----------|------|--------|------|------------------|",
    ]
    for f in flags:
        lines.append(
            f"| {f['severity']} | {f['desk']} | {f.get('ticker') or '—'} | "
            f"{f['fact']} | {f['suggested_action']} |"
        )
    lines.append("")
    return "\n".join(lines)


def render_tables(facts: dict) -> str:
    parts = [
        desk_summary_table(facts),
        risk_flags_table(facts),
        open_positions_table(facts),
        closed_trades_table(facts),
    ]
    return "\n".join(parts)
