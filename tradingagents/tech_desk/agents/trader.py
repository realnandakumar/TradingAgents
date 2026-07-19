"""Tech Desk Trader — Path 5: owns R:R and entry type from MA candidate levels."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from tradingagents.agents.utils.structured import bind_structured
from tradingagents.tech_desk.report_excerpt import format_report_excerpt
from tradingagents.tech_desk.report_loader import TechReportSnapshot
from tradingagents.tech_desk.schemas import (
    SkipEntry,
    TechDeskTraderDecision,
    TechDeskTraderDisposition,
    TechTradePlan,
)
from tradingagents.tech_desk.trader_validation import (
    reward_risk_from_levels,
    validate_trader_decision,
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
    raise ValueError("no JSON object found in trader response")


def _invoke_trader_decision(
    structured_llm: Optional[Any],
    plain_llm: Any,
    prompt: str,
) -> Tuple[Optional[TechDeskTraderDecision], Optional[str]]:
    last_err: Optional[str] = None
    if structured_llm is not None:
        for attempt in range(2):
            try:
                result = structured_llm.invoke(prompt)
                if result is None:
                    raise ValueError("structured trader returned None")
                if isinstance(result, TechDeskTraderDecision):
                    return result, None
                return TechDeskTraderDecision.model_validate(result), None
            except Exception as exc:
                last_err = str(exc)
                logger.warning(
                    "Tech Desk Trader structured call failed (attempt %d/2): %s",
                    attempt + 1,
                    exc,
                )
    json_prompt = (
        f"{prompt}\n\n"
        "Respond with ONLY a JSON object matching TechDeskTraderDecision fields."
    )
    try:
        response = plain_llm.invoke(json_prompt)
        text = response.content if hasattr(response, "content") else str(response)
        if isinstance(text, list):
            text = "".join(
                p.get("text", "") if isinstance(p, dict) else str(p) for p in text
            )
        data = _extract_json_object(str(text))
        return TechDeskTraderDecision.model_validate(data), None
    except Exception as exc:
        err = last_err or str(exc)
        logger.error("Tech Desk Trader free-text fallback failed: %s", exc)
        return None, err


def run_tech_desk_trader(
    llm: Any,
    snap: TechReportSnapshot,
    *,
    current_price: Optional[float],
    config: dict,
) -> Tuple[Optional[TechTradePlan], Optional[SkipEntry]]:
    """Turn one MA report into a validated trade plan or skip.

    Market Analyst provides candidate levels; this agent owns entry type and
    reward:risk. Deterministic validation enforces ``tech_desk_min_rr``.
    """
    min_rr = float(config.get("tech_desk_min_rr", 1.5))
    min_conf = int(config.get("tech_desk_min_confidence", 60))
    summary = snap.pm_summary or {}

    # Fast path: if MA candidate geometry already fails R:R hard, still ask trader
    # to adjust T1/stop — but prompt states the bar clearly.
    ma_rr = None
    try:
        stop = float(summary.get("stop") or 0)
        t1 = float(summary.get("target_1") or 0)
        zl = float(summary.get("entry_zone_low") or 0) or None
        zh = float(summary.get("entry_zone_high") or 0) or None
        if stop and t1:
            ma_rr = reward_risk_from_levels(
                stop, t1, zone_low=zl, zone_high=zh, entry=current_price
            )
    except (TypeError, ValueError):
        ma_rr = None

    excerpt = format_report_excerpt(
        snap.market_text,
        ticker=snap.ticker,
        report_date=snap.report_date,
        pm_summary=summary,
    )
    price_line = (
        f"Current price: {current_price:.2f}"
        if current_price is not None
        else "Current price: unknown"
    )
    ma_rr_line = f"{ma_rr:.2f}" if ma_rr is not None else "n/a"

    prompt = f"""You are the Tech Desk **Trader** (long-only NSE cash paper).

The Market Analyst already wrote the technical report and candidate levels.
Your job is NOT to re-analyze indicators. Your job is to decide whether this
is a trade, and to own **entry type** and **reward:risk**.

**Hard rules**
- Long-only. No short entries.
- Min reward:risk from zone midpoint: **{min_rr:.2f}**
  R:R = (target_1 − zone_mid) / (zone_mid − stop). If no zone, use current price as mid.
- If MA candidate R:R is below the bar, either **raise target_1** / tighten stop
  using levels still grounded in the report, or **skip**.
- If MA bias is **bearish**, disposition must be **skip** (no long open/wait).
- Prefer **wait** + **limit_zone** when price is above the buy zone (do not chase).
- Prefer **open** + **market** only when price is inside the zone (or at/near support
  with a clear MA buy).
- Min confidence to open/wait: {min_conf} (else skip).
- Geometry: stop < zone_low < zone_high < target_1 for limit_zone setups.

**MA candidate R:R (zone mid):** {ma_rr_line}
**{price_line}**
**Ticker:** {snap.ticker} · report date {snap.report_date}

**Report excerpt**
{excerpt}

Return a TechDeskTraderDecision for {snap.ticker} only.
"""

    structured = bind_structured(llm, TechDeskTraderDecision, "Tech Desk Trader")
    raw, err = _invoke_trader_decision(structured, llm, prompt)
    if raw is None:
        return None, SkipEntry(
            ticker=snap.ticker,
            reason=f"trader failed: {err or 'no decision'}",
        )

    # Ensure ticker is set
    if not raw.ticker:
        raw = raw.model_copy(update={"ticker": snap.ticker})
    elif raw.ticker.upper() != snap.ticker.upper():
        raw = raw.model_copy(update={"ticker": snap.ticker})

    plan, reason = validate_trader_decision(
        raw, min_rr=min_rr, current_price=current_price
    )
    if plan is None:
        return None, SkipEntry(
            ticker=snap.ticker,
            reason=reason or raw.skip_reason or "trader validation failed",
        )
    if plan.confidence < min_conf and plan.action.value == "open":
        return None, SkipEntry(
            ticker=snap.ticker,
            reason=f"trader confidence {plan.confidence} < min {min_conf}",
        )
    return plan, None


def run_tech_desk_traders(
    llm: Any,
    candidates: List[TechReportSnapshot],
    prices: Dict[str, float],
    config: dict,
    *,
    progress=None,
) -> Tuple[List[TechTradePlan], List[SkipEntry]]:
    """Run Path-5 Trader on each candidate report."""
    plans: List[TechTradePlan] = []
    skips: List[SkipEntry] = []

    def _log(msg: str) -> None:
        if progress:
            progress(msg)

    for i, snap in enumerate(candidates):
        _log(f"Tech Desk Trader [{i + 1}/{len(candidates)}] {snap.ticker}...")
        plan, skip = run_tech_desk_trader(
            llm,
            snap,
            current_price=prices.get(snap.ticker),
            config=config,
        )
        if plan is not None:
            plans.append(plan)
        elif skip is not None:
            skips.append(skip)
        else:
            skips.append(SkipEntry(ticker=snap.ticker, reason="trader returned nothing"))
    return plans, skips
