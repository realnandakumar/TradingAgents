"""Tech Desk portfolio manager — batch PM over saved tech-analyze reports."""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from tradingagents.agents.utils.structured import bind_structured
from tradingagents.tech_desk.report_loader import TechReportSnapshot
from tradingagents.tech_desk.schemas import (
    SkipEntry,
    TechDeskBatchDecision,
    render_batch_decision,
)

logger = logging.getLogger(__name__)

# Tech-analyze reports end with chart structure (§8), risk (§9), actionable
# levels (§10), summary table, and FINAL TRANSACTION PROPOSAL. PM reads a compact
# header, parsed key levels, then §8→end (full report if §8 is missing).

_SECTION_HEADER_RE = re.compile(r"^##\s+(\d+)\.\s+", re.MULTILINE)
_CLOSE_PRICE_RE = re.compile(
    r"Closing Price[^:\n]*:\s*\**([₹$]?\s*[\d,]+\.?\d*)",
    re.IGNORECASE,
)
_MA_50_RE = re.compile(r"\|\s*\*\*50 SMA\*\*\s*\|\s*₹?\s*([\d,.]+)", re.IGNORECASE)
_MA_200_RE = re.compile(r"\|\s*\*\*200 SMA\*\*\s*\|\s*₹?\s*([\d,.]+)", re.IGNORECASE)
_ATR_SUMMARY_RE = re.compile(
    r"\|\s*\*\*ATR\*\*\s*\|\s*([\d,.]+)",
    re.IGNORECASE,
)
_ATR_SECTION_RE = re.compile(
    r"\|\s*(?:July\s+\d+|Date)\s*\|\s*\*\*([\d,.]+)\*\*",
    re.IGNORECASE,
)
_SUPPORT_RE = re.compile(
    r"\|\s*\*\*Next Support\*\*\s*\|\s*([^\|]+)",
    re.IGNORECASE,
)
_RESISTANCE_RE = re.compile(
    r"\|\s*\*\*Next Resistance\*\*\s*\|\s*([^\|]+)",
    re.IGNORECASE,
)


def _find_section_start(market_text: str, section_num: int) -> Optional[int]:
    for match in _SECTION_HEADER_RE.finditer(market_text):
        if int(match.group(1)) == section_num:
            return match.start()
    return None


def _extract_report_close_price(market_text: str) -> Optional[str]:
    match = _CLOSE_PRICE_RE.search(market_text)
    if not match:
        return None
    return match.group(1).replace(",", "").strip()


def _clean_level_cell(raw: str) -> str:
    return re.sub(r"\s+", " ", raw.strip().strip("|").strip())


def _parse_key_levels(market_text: str) -> Dict[str, str]:
    """Best-effort parse of ATR, MAs, support, resistance from report tables."""
    levels: Dict[str, str] = {}

    if match := _MA_50_RE.search(market_text):
        levels["50_sma"] = match.group(1).replace(",", "")
    if match := _MA_200_RE.search(market_text):
        levels["200_sma"] = match.group(1).replace(",", "")

    atr_match = _ATR_SUMMARY_RE.search(market_text)
    if atr_match:
        levels["atr"] = atr_match.group(1).replace(",", "")
    else:
        section_six = _find_section_start(market_text, 6)
        if section_six is not None:
            section_text = market_text[section_six:]
            section_end = _find_section_start(section_text[10:], 7)
            atr_block = section_text if section_end is None else section_text[: section_end + 10]
            rows = list(_ATR_SECTION_RE.finditer(atr_block))
            if rows:
                levels["atr"] = rows[-1].group(1).replace(",", "")

    if match := _SUPPORT_RE.search(market_text):
        levels["key_support"] = _clean_level_cell(match.group(1))
    if match := _RESISTANCE_RE.search(market_text):
        levels["key_resistance"] = _clean_level_cell(match.group(1))

    return levels


def _format_key_levels_block(levels: Dict[str, str]) -> str:
    if not levels:
        return ""
    lines = ["### Key levels (parsed from report)"]
    if "atr" in levels:
        lines.append(f"- ATR: {levels['atr']}")
    if "50_sma" in levels:
        lines.append(f"- 50 SMA: {levels['50_sma']}")
    if "200_sma" in levels:
        lines.append(f"- 200 SMA: {levels['200_sma']}")
    if "key_support" in levels:
        lines.append(f"- Key support: {levels['key_support']}")
    if "key_resistance" in levels:
        lines.append(f"- Key resistance: {levels['key_resistance']}")
    return "\n".join(lines)


def _format_compact_header(ticker: str, report_date: str, close_price: Optional[str]) -> str:
    lines = ["### Report context"]
    if ticker:
        lines.append(f"- Ticker: {ticker}")
    if report_date:
        lines.append(f"- Report date: {report_date}")
    if close_price:
        lines.append(f"- Report close: ₹{close_price.lstrip('₹$')}")
    return "\n".join(lines)


def _format_report_excerpt(
    market_text: str,
    *,
    ticker: str = "",
    report_date: str = "",
) -> str:
    """Build PM-facing excerpt: header + key levels + §8→end (or full report)."""
    if not market_text:
        return ""

    start = _find_section_start(market_text, 8)
    body = market_text[start:] if start is not None else market_text

    close_price = _extract_report_close_price(market_text)
    key_levels = _format_key_levels_block(_parse_key_levels(market_text))
    header = _format_compact_header(ticker, report_date, close_price)

    parts = [header]
    if key_levels:
        parts.append(key_levels)
    parts.append(body)
    return "\n\n".join(p for p in parts if p)


def _format_candidates(
    candidates: List[TechReportSnapshot],
    prices: Dict[str, float],
) -> str:
    blocks: List[str] = []
    for snap in candidates:
        price = prices.get(snap.ticker)
        price_line = f"Current price: {price:.2f}" if price is not None else "Current price: unknown"
        excerpt = _format_report_excerpt(
            snap.market_text,
            ticker=snap.ticker,
            report_date=snap.report_date,
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
) -> Tuple[TechDeskBatchDecision, Optional[str]]:
    """Pick best setups from a batch of saved tech-analyze reports.

    Returns ``(decision, pm_error)`` where ``pm_error`` is set when structured
    output failed after retry.
    """
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
- **wait** + **limit_zone** with zone_low/zone_high when the report's final proposal is **HOLD**, **WAIT**, or explicitly says to **wait for a pullback** / **do not chase** / **patience for entry** — parse the cited support or entry range (e.g. ₹256–260) into zone_low/zone_high
- **open** + **market** only when the report signals immediate action (breakout now, buy/add, or price is **already inside** the report's preferred entry zone)
- **skip** if setup is weak, extended without a usable zone, or confidence < {min_conf}

**Analyst entry timing (strict):**
- If the report recommends waiting for a pullback zone and **current price is above** that zone, you MUST use **wait** + **limit_zone** — do NOT market-buy above the zone
- If current price is **inside** the report's entry zone, **open** + **market** is allowed
- If current price is **below** zone_low, treat as deeper pullback: still **wait** for zone_low–zone_high fill unless the report says the setup is invalidated

Populate `closes` with tickers to exit (bearish invalidation, SELL signal, or make room for stronger names).
Order `opens` best-first; respect slots_available.
Ground stop_loss, targets, and zones in each report's levels and ATR context.
Each report excerpt includes parsed key levels plus §8 onward (patterns, risk, summary table) — use those for levels and signals.
"""

    pm_error: Optional[str] = None
    if structured_llm is not None:
        for attempt in range(2):
            try:
                decision = structured_llm.invoke(prompt)
                logger.debug("Tech Desk PM decision:\n%s", render_batch_decision(decision))
                return decision, None
            except Exception as exc:
                pm_error = str(exc)
                logger.warning(
                    "Tech Desk PM structured call failed (attempt %d/2): %s",
                    attempt + 1,
                    exc,
                )
    else:
        pm_error = "provider does not support structured output"

    logger.error("Tech Desk PM returning empty decision after structured output failure")
    reason = f"PM structured output failed: {pm_error}" if pm_error else "PM structured output failed"
    return TechDeskBatchDecision(
        skips=[SkipEntry(ticker=c.ticker, reason=reason) for c in candidates],
    ), pm_error
