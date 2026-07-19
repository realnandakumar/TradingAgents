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
                result = structured_llm.invoke(prompt)
                if result is None:
                    raise ValueError("structured PM returned None")
                return result, None
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


def _format_trader_plans(
    plans: List[Any],
    prices: Dict[str, float],
) -> str:
    if not plans:
        return "No trader-approved plans."
    lines: List[str] = []
    for p in plans:
        price = prices.get(p.ticker)
        price_s = f"{price:.2f}" if price is not None else "?"
        zone = (
            f"{p.zone_low:.2f}–{p.zone_high:.2f}"
            if p.zone_low is not None and p.zone_high is not None
            else "—"
        )
        lines.append(
            f"- **{p.ticker}**: action={p.action.value} · entry={p.entry_type.value} · "
            f"price {price_s} · zone {zone} · stop {p.stop_loss:.2f} · "
            f"T1 {p.target_1:.2f} · conf {p.confidence} · bias {p.bias.value}\n"
            f"  _{p.rationale}_"
        )
    return "\n".join(lines)


def _format_trader_skips(skips: List[SkipEntry]) -> str:
    if not skips:
        return "None."
    return "\n".join(f"- {s.ticker}: {s.reason}" for s in skips)


def run_tech_desk_batch_pm(
    llm: Any,
    candidates: List[TechReportSnapshot],
    open_positions: List[dict],
    slots_available: int,
    config: dict,
    prices: Optional[Dict[str, float]] = None,
    *,
    as_of: Optional[str] = None,
    trader_plans: Optional[List[Any]] = None,
    trader_skips: Optional[List[SkipEntry]] = None,
) -> Tuple[TechDeskBatchDecision, Optional[str]]:
    """Pick best setups from trader-approved plans (Path 5) or raw reports."""
    prices = prices or {}
    min_conf = int(config.get("tech_desk_min_confidence", 60))
    max_pos = int(config.get("tech_desk_max_positions", 20))
    default_hold = int(config.get("tech_desk_holding_days", 20))
    min_rr = float(config.get("tech_desk_min_rr", 1.5))

    structured_llm = bind_structured(llm, TechDeskBatchDecision, "Tech Desk PM")

    if trader_plans is not None:
        prompt = f"""You are the Tech Desk Portfolio Manager for a long-only NSE cash paper book.

**Path 5 desk split**
- Market Analyst wrote the technical reports (candidate levels).
- **Tech Desk Trader** already decided open/wait/skip and owns entry type + R:R (≥ {min_rr:.2f}).
- Your job is **portfolio selection only**: which trader plans to keep, order opens
  best-first, park waits, and which open positions to close. Do **not** invent new
  stops/targets/zones — copy trader plan levels when you include a name in opens/waits.

**Desk rules**
- Capital: ₹{config.get('desk_capital', 100_000):,.0f} · max {max_pos} slots · equal weight sizing
- Long-only: SELL means exit/square off an open position
- Min confidence to open: {min_conf}
- Default holding cap: {default_hold} trading days
- Slots available for new opens: {slots_available}

**Open positions**
{_format_open_positions(open_positions, prices)}

**Trader-approved plans** ({len(trader_plans)})
{_format_trader_plans(trader_plans, prices)}

**Already skipped by Trader**
{_format_trader_skips(trader_skips or [])}

---

Populate `opens` / `waits` only from trader-approved plans (same ticker levels).
You may skip a trader plan if slots are full or a stronger plan should take priority.
Populate `closes` for open positions (invalidation, weak thesis, or make room).
Order `opens` best-first; respect slots_available.
"""
    else:
        prompt = f"""You are the Tech Desk Portfolio Manager for a long-only NSE cash paper book.

**Desk rules**
- Capital: ₹{config.get('desk_capital', 100_000):,.0f} · max {max_pos} slots · equal weight sizing
- Long-only: SELL means exit/square off an open position
- Accept HOLD setups with **pullback zone** entries (limit_zone), not only immediate BUY
- Min confidence to open: {min_conf}
- Default holding cap: {default_hold} trading days (override per plan when justified)
- Slots available for new opens: {slots_available}
- When full, only recommend opens if you also list weaker positions in `closes`, or use `waits` for zone entries
- Prefer setups with reward:risk ≥ {min_rr:.2f} from zone midpoint

**Open positions**
{_format_open_positions(open_positions, prices)}

**Candidate reports** ({len(candidates)} tickers — latest saved tech-analyze each)
{_format_candidates(candidates, prices, as_of=as_of)}

---

For each candidate, decide:
- **wait** + **limit_zone** with zone_low/zone_high when the report's final proposal is **HOLD**, **WAIT**, or explicitly says to **wait for a pullback** / **do not chase** / **patience for entry** — parse the cited support or entry range (e.g. ₹256–260) into zone_low/zone_high
- **open** + **market** only when the report signals immediate action (breakout now, buy/add, or price is **already inside** the report's preferred entry zone)
- **skip** if setup is weak, extended without a usable zone, R:R < {min_rr:.2f}, or confidence < {min_conf}

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
    empty = (
        decision is None
        or not (decision.opens or decision.waits or decision.skips or decision.closes)
    )
    if decision is None or (pm_error and empty):
        reason = pm_error or "PM returned no structured decision"
        # Path 5 fallback: if traders already produced plans, use them directly
        if trader_plans:
            from tradingagents.tech_desk.schemas import PlanAction

            opens = [p for p in trader_plans if p.action == PlanAction.OPEN]
            waits = [p for p in trader_plans if p.action == PlanAction.WAIT]
            decision = TechDeskBatchDecision(
                opens=opens[: max(0, slots_available)],
                waits=waits,
                skips=list(trader_skips or [])
                + [SkipEntry(ticker=c.ticker, reason=f"PM failed: {reason}") for c in candidates
                   if c.ticker.upper() not in {p.ticker.upper() for p in trader_plans}],
            )
            pm_error = pm_error or reason
        else:
            decision = TechDeskBatchDecision(
                skips=[SkipEntry(ticker=c.ticker, reason=f"PM failed: {reason}") for c in candidates],
            )
            pm_error = pm_error or reason
    else:
        if trader_plans:
            decision = _reconcile_pm_with_trader_plans(decision, trader_plans)
        logger.debug("Tech Desk PM decision:\n%s", render_batch_decision(decision))
    return decision, pm_error


def _reconcile_pm_with_trader_plans(
    decision: TechDeskBatchDecision,
    trader_plans: List[Any],
) -> TechDeskBatchDecision:
    """Replace PM-invented levels with trader plan levels for matching tickers."""
    by_ticker = {p.ticker.upper(): p for p in trader_plans}

    def _fix(plans: List[Any]) -> List[Any]:
        out = []
        for p in plans:
            trader = by_ticker.get(p.ticker.upper())
            if trader is None:
                continue  # drop PM inventions not approved by trader
            # Keep PM action/entry_type if compatible; always use trader levels
            out.append(
                trader.model_copy(
                    update={
                        "action": p.action,
                        "entry_type": p.entry_type,
                        "rationale": p.rationale or trader.rationale,
                        "confidence": p.confidence or trader.confidence,
                    }
                )
            )
        return out

    return decision.model_copy(
        update={
            "opens": _fix(decision.opens),
            "waits": _fix(decision.waits),
        }
    )


# Back-compat aliases for tests
_format_report_excerpt = format_report_excerpt
_parse_key_levels = parse_key_levels
