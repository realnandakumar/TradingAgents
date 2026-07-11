"""Tech Desk portfolio manager — batch PM over saved tech-analyze reports."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from tradingagents.agents.utils.structured import bind_structured
from tradingagents.tech_desk.report_loader import TechReportSnapshot
from tradingagents.tech_desk.schemas import (
    SkipEntry,
    TechDeskBatchDecision,
    render_batch_decision,
)

logger = logging.getLogger(__name__)


def _format_candidates(
    candidates: List[TechReportSnapshot],
    prices: Dict[str, float],
) -> str:
    blocks: List[str] = []
    for snap in candidates:
        price = prices.get(snap.ticker)
        price_line = f"Current price: {price:.2f}" if price is not None else "Current price: unknown"
        excerpt = snap.market_text[:4000]
        if len(snap.market_text) > 4000:
            excerpt += "\n...[truncated]..."
        blocks.append(
            f"### {snap.ticker} (report date: {snap.report_date})\n"
            f"{price_line}\n\n{excerpt}"
        )
    return "\n\n---\n\n".join(blocks)


def _format_open_positions(open_positions: List[dict], prices: Dict[str, float]) -> str:
    if not open_positions:
        return "No open positions."
    lines: List[str] = []
    for p in open_positions:
        ticker = p["ticker"]
        entry = float(p.get("entry_price") or 0)
        price = prices.get(ticker, entry)
        ret = (price - entry) / entry * 100 if entry else 0.0
        lines.append(
            f"- {ticker}: entry {entry:.2f}, now {price:.2f} ({ret:+.1f}%), "
            f"stop {p.get('stop_loss')}, target_1 {p.get('target_1')}, "
            f"conf {p.get('confidence')}, bias {p.get('bias')}"
        )
    return "\n".join(lines)


def run_tech_desk_batch_pm(
    llm: Any,
    candidates: List[TechReportSnapshot],
    open_positions: List[dict],
    slots_available: int,
    config: dict,
    prices: Optional[Dict[str, float]] = None,
) -> TechDeskBatchDecision:
    """Pick best setups from a batch of saved tech-analyze reports."""
    prices = prices or {}
    min_conf = int(config.get("tech_desk_min_confidence", 60))
    max_pos = int(config.get("tech_desk_max_positions", 10))
    default_hold = int(config.get("tech_desk_holding_days", 20))

    structured_llm = bind_structured(llm, TechDeskBatchDecision, "Tech Desk PM")

    prompt = f"""You are the Tech Desk Portfolio Manager for a long-only NSE cash paper book.

**Desk rules**
- Capital: ₹{config.get('desk_capital', 100_000):,.0f} · max {max_pos} slots · equal weight sizing
- Long-only: SELL means exit/square off an open position
- Accept HOLD setups with **pullback zone** entries (limit_zone), not only immediate BUY
- Min confidence to open: {min_conf}
- Default holding cap: {default_hold} trading days (override per plan when justified)
- Slots available for new opens: {slots_available}
- When full, only recommend opens if you also list weaker positions in `closes`, or use `waits` for zone entries

**Open positions**
{_format_open_positions(open_positions, prices)}

**Candidate reports** ({len(candidates)} tickers — latest saved tech-analyze each)
{_format_candidates(candidates, prices)}

---

For each candidate, decide:
- **open** + **market** if price is actionable now (breakout / resuming after shallow pullback)
- **wait** + **limit_zone** with zone_low/zone_high for HOLD/pullback entries
- **skip** if setup is weak, extended, or confidence < {min_conf}

Populate `closes` with tickers to exit (bearish invalidation, SELL signal, or make room for stronger names).
Order `opens` best-first; respect slots_available.
Ground stop_loss, targets, and zones in each report's levels and ATR context.
"""

    if structured_llm is not None:
        try:
            decision = structured_llm.invoke(prompt)
            logger.debug("Tech Desk PM decision:\n%s", render_batch_decision(decision))
            return decision
        except Exception as exc:
            logger.warning("Tech Desk PM structured call failed (%s)", exc)

    logger.warning("Tech Desk PM returning empty decision (structured output unavailable)")
    return TechDeskBatchDecision(
        skips=[
            SkipEntry(ticker=c.ticker, reason="PM structured output failed")
            for c in candidates
        ]
    )
