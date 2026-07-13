"""Tech Desk entry rules — proximity market and counter-trend checks."""

from __future__ import annotations

from typing import Dict, List, Optional

from tradingagents.tech_desk.report_loader import TechReportSnapshot
from tradingagents.tech_desk.schemas import (
    Bias,
    EntryType,
    PlanAction,
    TechDeskBatchDecision,
    TechTradePlan,
)

_ANTI_CHASE_PHRASES = (
    "do not chase",
    "wait for a pullback",
    "wait for pullback",
    "patience for entry",
    "not suitable for aggressive",
)

_COUNTER_TREND_PHRASES = (
    "counter-trend",
    "counter trend",
    "bear market",
    "decisively bearish",
    "bear trend",
    "secular bear",
)


def is_counter_trend(
    plan: TechTradePlan,
    summary: Optional[dict],
    price: Optional[float],
) -> bool:
    """Block proximity entries for counter-trend / below-50-SMA setups."""
    if plan.bias == Bias.BEARISH:
        return True
    if summary and (summary.get("bias") or "").lower() == "bearish":
        return True
    if summary and price is not None:
        sma50 = summary.get("sma_50")
        try:
            if sma50 is not None and price < float(sma50) * 0.995:
                return True
        except (TypeError, ValueError):
            pass
    text = f"{plan.invalidation} {plan.rationale}".lower()
    return any(phrase in text for phrase in _COUNTER_TREND_PHRASES)


def _has_explicit_wait_language(plan: TechTradePlan, summary: Optional[dict]) -> bool:
    proposal = (summary or {}).get("proposal")
    if isinstance(proposal, str) and proposal.upper() in {"WAIT", "SELL"}:
        return True
    text = f"{plan.rationale} {(summary or {}).get('invalidation', '')}".lower()
    return any(phrase in text for phrase in _ANTI_CHASE_PHRASES)


def evaluate_proximity_entry(
    plan: TechTradePlan,
    price: Optional[float],
    summary: Optional[dict],
    config: dict,
) -> Optional[TechTradePlan]:
    """Promote a wait plan to market_near_support when near zone with favorable R:R."""
    if is_counter_trend(plan, summary, price):
        return None
    if _has_explicit_wait_language(plan, summary):
        return None

    zone_low = plan.zone_low
    zone_high = plan.zone_high
    target_1 = plan.target_1
    if price is None or zone_low is None or zone_high is None or target_1 is None:
        return None
    if price <= 0 or zone_high <= zone_low or target_1 <= zone_high:
        return None

    tolerance = float(config.get("tech_desk_zone_proximity_pct", 1.5)) / 100.0
    min_ratio = float(config.get("tech_desk_min_reward_to_zone_ratio", 2.5))
    min_conf = int(config.get("tech_desk_proximity_min_confidence", 65))
    if plan.confidence < min_conf:
        return None

    max_price = zone_high * (1.0 + tolerance)
    if price < zone_low or price > max_price:
        return None

    upside_pct = (target_1 - price) / price
    if upside_pct <= 0:
        return None

    if price > zone_high:
        chase_pct = (price - zone_high) / price
        if chase_pct <= 0 or upside_pct / chase_pct < min_ratio:
            return None
    else:
        risk_pct = (price - plan.stop_loss) / price
        if risk_pct <= 0 or upside_pct / risk_pct < min_ratio:
            return None

    stop = zone_low if config.get("tech_desk_proximity_stop_at_zone_low", True) else plan.stop_loss
    if stop >= price:
        return None

    return plan.model_copy(
        update={
            "action": PlanAction.OPEN,
            "entry_type": EntryType.MARKET_NEAR_SUPPORT,
            "stop_loss": round(stop, 2),
        }
    )


def promote_proximity_entries(
    decision: TechDeskBatchDecision,
    prices: Dict[str, float],
    snapshots: Dict[str, TechReportSnapshot],
    config: dict,
) -> TechDeskBatchDecision:
    """Move eligible wait plans to opens as market_near_support entries."""
    opens: List[TechTradePlan] = list(decision.opens)
    waits: List[TechTradePlan] = []

    for plan in decision.waits:
        if plan.entry_type != EntryType.LIMIT_ZONE:
            waits.append(plan)
            continue
        snap = snapshots.get(plan.ticker.upper()) or snapshots.get(plan.ticker)
        summary = snap.pm_summary if snap else None
        price = prices.get(plan.ticker)
        promoted = evaluate_proximity_entry(plan, price, summary, config)
        if promoted is not None:
            opens.append(promoted)
        else:
            waits.append(plan)

    if opens == decision.opens and waits == decision.waits:
        return decision
    return decision.model_copy(update={"opens": opens, "waits": waits})
