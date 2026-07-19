"""Deterministic validation for Tech Desk Trader plans (Path 5)."""

from __future__ import annotations

from typing import Optional, Tuple

from tradingagents.tech_desk.schemas import (
    Bias,
    EntryType,
    PlanAction,
    TechDeskTraderDecision,
    TechDeskTraderDisposition,
    TechTradePlan,
)


def zone_midpoint(zone_low: Optional[float], zone_high: Optional[float]) -> Optional[float]:
    if zone_low is None or zone_high is None:
        return None
    if zone_high <= zone_low:
        return None
    return (float(zone_low) + float(zone_high)) / 2.0


def reward_risk_from_levels(
    stop: float,
    target_1: float,
    *,
    zone_low: Optional[float] = None,
    zone_high: Optional[float] = None,
    entry: Optional[float] = None,
) -> Optional[float]:
    """(T1 − ref) / (ref − stop) using zone mid, else entry, else midpoint stop/T1."""
    ref = zone_midpoint(zone_low, zone_high)
    if ref is None and entry is not None:
        ref = float(entry)
    if ref is None:
        ref = (float(stop) + float(target_1)) / 2.0
    risk = ref - float(stop)
    reward = float(target_1) - ref
    if risk <= 0 or reward <= 0:
        return None
    return reward / risk


def validate_trader_decision(
    decision: TechDeskTraderDecision,
    *,
    min_rr: float = 1.5,
    current_price: Optional[float] = None,
) -> Tuple[Optional[TechTradePlan], Optional[str]]:
    """Return ``(plan, None)`` or ``(None, skip_reason)``."""
    if decision.disposition == TechDeskTraderDisposition.SKIP:
        return None, decision.skip_reason or decision.rationale or "trader skip"

    if decision.stop_loss is None or decision.target_1 is None:
        return None, "trader open/wait missing stop or target_1"
    if decision.entry_type is None:
        return None, "trader open/wait missing entry_type"

    stop = float(decision.stop_loss)
    t1 = float(decision.target_1)
    zl = decision.zone_low
    zh = decision.zone_high

    if decision.disposition == TechDeskTraderDisposition.WAIT or (
        decision.entry_type == EntryType.LIMIT_ZONE
    ):
        if zl is None or zh is None or float(zh) <= float(zl):
            return None, "wait/limit_zone needs valid entry zone"
        if not (stop < float(zl) < float(zh) < t1):
            return None, "geometry: need stop < zone_low < zone_high < target_1"

    if decision.disposition == TechDeskTraderDisposition.OPEN:
        if decision.entry_type == EntryType.LIMIT_ZONE:
            if zl is None or zh is None or float(zh) <= float(zl):
                return None, "open+limit_zone needs valid entry zone"
            if not (stop < float(zl) < float(zh) < t1):
                return None, "geometry: need stop < zone_low < zone_high < target_1"
        else:
            # market / market_near_support: stop < entry < t1 when price known
            entry = current_price
            if zl is not None and zh is not None and float(zh) > float(zl):
                mid = zone_midpoint(zl, zh)
                entry = entry if entry is not None else mid
            if entry is not None and not (stop < float(entry) < t1):
                return None, "geometry: need stop < entry < target_1"
            elif entry is None and not (stop < t1):
                return None, "geometry: need stop < target_1"

    if decision.bias == Bias.BEARISH and decision.disposition in (
        TechDeskTraderDisposition.OPEN,
        TechDeskTraderDisposition.WAIT,
    ):
        return None, "bearish bias with long open/wait — stand aside"

    # Never open/wait a long after price has already tagged T1.
    if current_price is not None and current_price > 0 and float(current_price) >= t1:
        return None, "post_target_pullback"

    rr = reward_risk_from_levels(
        stop,
        t1,
        zone_low=float(zl) if zl is not None else None,
        zone_high=float(zh) if zh is not None else None,
        entry=current_price,
    )
    if rr is None or rr < float(min_rr):
        return None, f"R:R {rr if rr is not None else 0:.2f} < min {min_rr:.2f}"

    action = (
        PlanAction.OPEN
        if decision.disposition == TechDeskTraderDisposition.OPEN
        else PlanAction.WAIT
    )
    plan = TechTradePlan(
        ticker=decision.ticker,
        action=action,
        entry_type=decision.entry_type,
        zone_low=float(zl) if zl is not None else None,
        zone_high=float(zh) if zh is not None else None,
        stop_loss=round(stop, 2),
        target_1=round(t1, 2),
        target_2=round(float(decision.target_2), 2) if decision.target_2 else None,
        confidence=int(decision.confidence),
        bias=decision.bias,
        invalidation=decision.invalidation
        or f"Break of stop {stop:.2f}",
        rationale=decision.rationale,
    )
    return plan, None
