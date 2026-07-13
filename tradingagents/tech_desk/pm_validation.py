"""Post-validate Tech Desk PM decisions before execution."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from tradingagents.tech_desk.report_loader import TechReportSnapshot
from tradingagents.tech_desk.schemas import (
    EntryType,
    PlanAction,
    TechDeskBatchDecision,
    TechTradePlan,
)

logger = logging.getLogger(__name__)

_WAIT_PROPOSALS = frozenset({"HOLD", "WAIT", "SELL"})


def _zone_from_summary(summary: Optional[dict]) -> tuple[Optional[float], Optional[float]]:
    if not summary:
        return None, None
    low = summary.get("entry_zone_low")
    high = summary.get("entry_zone_high")
    try:
        zl = float(low) if low is not None else None
        zh = float(high) if high is not None else None
    except (TypeError, ValueError):
        return None, None
    if zl is not None and zh is not None and zh > zl:
        return zl, zh
    return None, None


def _should_wait_not_market(
    plan: TechTradePlan,
    current_price: Optional[float],
    summary: Optional[dict],
) -> bool:
    if plan.entry_type != EntryType.MARKET:
        return False
    proposal = (summary or {}).get("proposal")
    if isinstance(proposal, str) and proposal.upper() in _WAIT_PROPOSALS:
        return True
    zone_low, zone_high = _zone_from_summary(summary)
    if zone_high is None or current_price is None:
        return False
    return current_price > zone_high


def _to_wait_plan(plan: TechTradePlan, summary: Optional[dict]) -> TechTradePlan:
    zone_low, zone_high = _zone_from_summary(summary)
    updates: dict = {
        "action": PlanAction.WAIT,
        "entry_type": EntryType.LIMIT_ZONE,
    }
    if zone_low is not None and zone_high is not None:
        updates["zone_low"] = zone_low
        updates["zone_high"] = zone_high
    return plan.model_copy(update=updates)


def enforce_entry_timing(
    decision: TechDeskBatchDecision,
    prices: Dict[str, float],
    snapshots: Dict[str, TechReportSnapshot],
) -> TechDeskBatchDecision:
    """Downgrade market opens that chase above the analyst entry zone."""
    opens: List[TechTradePlan] = []
    waits: List[TechTradePlan] = list(decision.waits)

    for plan in decision.opens:
        snap = snapshots.get(plan.ticker.upper()) or snapshots.get(plan.ticker)
        summary = snap.pm_summary if snap else None
        price = prices.get(plan.ticker)
        if _should_wait_not_market(plan, price, summary):
            logger.info(
                "Anti-chase: %s open/market -> wait (price=%s proposal=%s)",
                plan.ticker,
                price,
                (summary or {}).get("proposal"),
            )
            waits.append(_to_wait_plan(plan, summary))
            continue
        opens.append(plan)

    if opens == decision.opens and waits == decision.waits:
        return decision
    return decision.model_copy(update={"opens": opens, "waits": waits})
