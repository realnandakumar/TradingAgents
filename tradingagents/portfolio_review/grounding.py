"""Grounding index and narrative validation for portfolio review."""

from __future__ import annotations

import json
import math
import re
from typing import Iterable, List, Set, Tuple


def _num_variants(v: float | int) -> Set[str]:
    """All string forms we accept for a numeric fact."""
    out: Set[str] = set()
    if v is None:
        return out
    f = float(v)
    if math.isnan(f) or math.isinf(f):
        return out
    for fmt in (".0f", ".1f", ".2f"):
        s = format(f, fmt)
        out.add(s)
        out.add(s.lstrip("-"))
    if f == int(f):
        out.add(str(int(f)))
        out.add(str(abs(int(f))))
    # Comma-grouped rupee style (678 -> matches 678 in 1,678 only via full token)
    if abs(f) >= 1000:
        out.add(f"{int(f):,}")
        out.add(f"{abs(int(f)):,}")
    return out


def _walk_numbers(obj, sink: Set[str]) -> None:
    if isinstance(obj, dict):
        for val in obj.values():
            _walk_numbers(val, sink)
    elif isinstance(obj, list):
        for item in obj:
            _walk_numbers(item, sink)
    elif isinstance(obj, (int, float)):
        sink.update(_num_variants(obj))


def _numbers_from_markdown_tables(md: str) -> Set[str]:
    """Pull numeric cells from markdown tables (authoritative rendered output)."""
    found: Set[str] = set()
    for cell in re.findall(r"\|([^|\n]+)\|", md):
        cell = cell.strip()
        if not cell or cell.startswith("-"):
            continue
        # Strip currency and percent symbols
        cleaned = cell.replace("₹", "").replace("Rs", "").replace("%", "").replace(",", "").strip()
        for part in re.findall(r"-?\d+(?:\.\d+)?", cleaned):
            found.add(part)
            try:
                found.update(_num_variants(float(part)))
            except ValueError:
                pass
    return found


def build_grounding_sheet(facts: dict) -> str:
    """Human-readable canonical facts the LLM must not contradict."""
    s = facts["summary"]
    lines = [
        f"- As-of date: {facts['as_of_date']}",
        f"- Portfolio total P&L (INR): {int(round(s['total_pnl_inr']))}",
        f"- Realized P&L (INR): {int(round(s['total_realized_inr']))}",
        f"- Unrealized P&L (INR): {int(round(s['total_unrealized_inr']))}",
        f"- Open positions: {s['open_positions']}",
        f"- Closed positions: {s['closed_positions']}",
        f"- Desk capital each (INR): {int(s['desk_capital_inr'])}",
    ]
    for d in facts["desks"]:
        lines.append(
            f"- Desk {d['label']}: open={d['open_count']}, closed={d['closed_count']}, "
            f"realized_inr={int(round(d['realized_inr']))}, "
            f"unrealized_inr={int(round(d['unrealized_inr']))}, "
            f"total_inr={int(round(d['total_inr']))}"
        )
    for p in facts.get("positions", []):
        if p.get("status") != "open":
            continue
        ltp = p.get("current_price")
        lines.append(
            f"- [{p['desk']}:{p['ticker']}] entry={p.get('entry_price')}, ltp={ltp}, "
            f"shares={p.get('shares')}, market_value_inr={int(round(p.get('market_value_inr') or 0))}, "
            f"pnl_inr={int(round(p.get('unrealized_inr') or 0))}, pnl_pct={p.get('return_pct')}"
        )
    for p in facts.get("positions", []):
        if p.get("status") != "closed":
            continue
        lines.append(
            f"- [{p['desk']}:{p['ticker']}] closed pnl_inr={int(round(p.get('realized_inr') or 0))}, "
            f"return_pct={p.get('return_pct')}"
        )
    for f in facts.get("risk_flags", []):
        lines.append(f"- Risk flag ({f['severity']}): {f['fact']}")
    return "\n".join(lines)


def build_allowed_tokens(facts: dict, tables_md: str = "") -> Set[str]:
    allowed: Set[str] = set()
    _walk_numbers(facts, allowed)
    if tables_md:
        allowed.update(_numbers_from_markdown_tables(tables_md))
    # Dates YYYY, day counts 0-365
    if facts.get("as_of_date"):
        allowed.add(facts["as_of_date"][:4])
        allowed.add(facts["as_of_date"][5:7])
        allowed.add(facts["as_of_date"][8:10])
    for i in range(0, 101):
        allowed.add(str(i))
    return allowed


def _matches_allowed(token: str, allowed: Set[str]) -> bool:
    if token in allowed:
        return True
    try:
        val = float(token)
    except ValueError:
        return False
    # Allow rounding: narrative integer within ±2 of any allowed float
    for a in allowed:
        try:
            if abs(val - float(a)) <= 2.0:
                return True
            if val != 0 and abs(val - float(a)) / max(abs(val), 1) <= 0.02:
                return True
        except ValueError:
            continue
    return False


_CITATION_RE = re.compile(r"\[[^\]]+\]")
_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


def validate_narrative(
    narrative: str,
    facts: dict,
    tables_md: str = "",
) -> Tuple[bool, List[str]]:
    """Flag numeric tokens in narrative not grounded in facts or tables."""
    allowed = build_allowed_tokens(facts, tables_md)
    # Narrative prose only — strip citations and markdown headings
    text = _CITATION_RE.sub("", narrative)
    issues: List[str] = []
    seen: Set[str] = set()

    for match in _NUMBER_RE.finditer(text):
        token = match.group()
        if token in seen:
            continue
        seen.add(token)
        if _matches_allowed(token, allowed):
            continue
        # Section ordinals / list indices 1-20
        if token.lstrip("-").isdigit() and abs(int(token)) <= 20:
            continue
        issues.append(f"Unverified number: {token}")

    return len(issues) == 0, issues[:20]
