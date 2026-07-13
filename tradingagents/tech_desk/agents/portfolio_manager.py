"""Tech Desk portfolio manager — batch PM over saved tech-analyze reports."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from tradingagents.agents.utils.structured import bind_structured
from tradingagents.tech_desk.report_excerpt import format_report_excerpt, parse_key_levels
from tradingagents.tech_desk.report_loader import TechReportSnapshot
from tradingagents.tech_desk.schemas import (
    SkipEntry,
    TechDeskBatchDecision,
    render_batch_decision,
)

logger = logging.getLogger(__name__)

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _extract_json_object(text: str) -> dict:
    text = text.strip()
    fence = _JSON_FENCE_RE.search(text)
    if fence:
        return json.loads(fence.group(1))
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return json.loads(text[start : end + 1])
    raise ValueError("no JSON object found in PM response")


def _invoke_batch_decision(
    structured_llm: Optional[Any],
    plain_llm: Any,
    prompt: str,
) -> Tuple[TechDeskBatchDecision, Optional[str]]:
    last_err: Optional[str] = None
    if structured_llm is not None:
        for attempt in range(2):
            try:
                return structured_llm.invoke(prompt), None
            except Exception as exc:
                last_err = str(exc)
                logger.warning(
                    "Tech Desk PM structured call failed (attempt %d/2): %s",
                    attempt + 1,
                    exc,
                )

    json_prompt = (
        f"{prompt}\n\n"
        "If structured output is unavailable, respond with ONLY a JSON object matching "
        "TechDeskBatchDecision: {\"opens\": [], \"waits\": [], \"skips\": [], \"closes\": []}."
    )
    try:
        response = plain_llm.invoke(json_prompt)
        text = response.content if hasattr(response, "content") else str(response)
        data = _extract_json_object(text)
        return TechDeskBatchDecision.model_validate(data), None
    except Exception as exc:
        err = last_err or str(exc)
        logger.error("Tech Desk PM free-text JSON fallback failed: %s", exc)
        return TechDeskBatchDecision(), err


def _format_candidates(
    candidates: List[TechReportSnapshot],
    prices: Dict[str, float],
    *,
    as_of: Optional[str] = None,
) -> str:
    blocks: List[str] = []
    for snap in candidates:
        price = prices.get(snap.ticker)
        price_line = f"Current price: {price:.2f}" if price is not None else "Current price: unknown"
        excerpt = format_report_excerpt(
            snap.market_text,
            ticker=snap.ticker,
            report_date=snap.report_date,
            as_of=as_of,
            pm_summary=snap.pm_summary,
        )
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
    *,
    as_of: Optional[str] = None,
) -> Tuple[TechDeskBatchDecision, Optional[str]]:
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
{_format_candidates(candidates, prices, as_of=as_of)}

---

For each candidate, decide:
- **wait** + **limit_zone** with zone_low/zone_high when the report's final proposal is **HOLD**, **WAIT**, or explicitly says to **wait for a pullback** / **do not chase** / **patience for entry** — parse the cited support or entry range (e.g. ₹256–260) into zone_low/zone_high
- **open** + **market** only when the report signals immediate action (breakout now, buy/add, or price is **already inside** the report's preferred entry zone)
- **skip** if setup is weak, extended without a usable zone, or confidence < {min_conf}

**Analyst entry timing (strict):**
- If the report recommends waiting for a pullback zone and **current price is above** that zone, you MUST use **wait** + **limit_zone** — do NOT market-buy above the zone (proximity promotion may still apply automatically for with-trend setups within 1.5% of zone)
- If current price is **inside** the report's entry zone, **open** + **market** is allowed
- If current price is **below** zone_low, treat as deeper pullback: still **wait** for zone_low–zone_high fill unless the report says the setup is invalidated

Populate `closes` with tickers to exit (bearish invalidation, SELL signal, or make room for stronger names).
Order `opens` best-first; respect slots_available.
Ground stop_loss, targets, and zones in each report's PM summary, parsed key levels, and actionable tail sections.
Prefer the structured **PM summary** block and **FINAL TRANSACTION PROPOSAL** when present.
"""

    decision, pm_error = _invoke_batch_decision(structured_llm, llm, prompt)
    if pm_error and not (decision.opens or decision.waits or decision.skips or decision.closes):
        decision = TechDeskBatchDecision(
            skips=[SkipEntry(ticker=c.ticker, reason=f"PM failed: {pm_error}") for c in candidates],
        )
    else:
        logger.debug("Tech Desk PM decision:\n%s", render_batch_decision(decision))
    return decision, pm_error


# Back-compat aliases for tests
_format_report_excerpt = format_report_excerpt
_parse_key_levels = parse_key_levels
