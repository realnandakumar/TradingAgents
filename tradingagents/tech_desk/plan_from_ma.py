"""Build TechTradePlan objects from Market Analyst ``pm_summary`` blocks.

Used by Tech Desk and the RS screen so MA → stop / T1 / buying zone / open-vs-wait
rules stay identical.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from tradingagents.tech_desk.report_loader import TechReportSnapshot
from tradingagents.tech_desk.schemas import (
    Bias,
    EntryType,
    PlanAction,
    SkipEntry,
    TechDeskBatchDecision,
    TechTradePlan,
)

_WAIT_PROPOSALS = frozenset({"HOLD", "WAIT"})
_SKIP_PROPOSALS = frozenset({"SELL", "NONE", ""})


def _num(v: Any) -> Optional[float]:
    try:
        if v is None or v == "":
            return None
        f = float(v)
        if f == 0.0:
            # MA template often leaves zeros for unused fields
            return None
        return f
    except (TypeError, ValueError):
        return None


def _zone(summary: dict) -> Tuple[Optional[float], Optional[float]]:
    low = _num(summary.get("entry_zone_low"))
    high = _num(summary.get("entry_zone_high"))
    if low is not None and high is not None and high > low:
        return low, high
    return None, None


def _bias(summary: dict) -> Bias:
    raw = str(summary.get("bias") or "neutral").lower()
    if raw in ("bullish", "bearish", "neutral"):
        return Bias(raw)
    return Bias.NEUTRAL


def _confidence(summary: dict, default: int = 65) -> int:
    try:
        c = int(float(summary.get("confidence", default)))
    except (TypeError, ValueError):
        c = default
    return max(0, min(100, c))


def _zone_between_stop_and_t1(
    stop: float, zone_low: float, zone_high: float, target_1: float
) -> bool:
    return stop < zone_low and zone_high < target_1


def trade_plan_from_pm_summary(
    ticker: str,
    summary: Optional[dict],
    current_price: Optional[float],
    *,
    min_confidence: int = 60,
) -> Tuple[Optional[TechTradePlan], Optional[str]]:
    """Convert MA ``pm_summary`` into a TechTradePlan (open or wait) or skip.

    Returns ``(plan, None)`` or ``(None, skip_reason)``.

    Rules (aligned with Tech Desk PM validation / anti-chase):
    - Requires stop and target_1
    - SELL / missing proposal → skip
    - HOLD / WAIT with a valid buying zone → wait / limit_zone
    - BUY with price above zone_high → wait / limit_zone (do not chase)
    - BUY with price in/below zone (or no zone) → open / market
      when stop < entry < target_1
    """
    if not summary:
        return None, "no pm_summary"

    proposal = str(summary.get("proposal") or "").upper().strip()
    if proposal in _SKIP_PROPOSALS or not proposal:
        return None, f"proposal={proposal or 'NONE'}"

    stop = _num(summary.get("stop"))
    target_1 = _num(summary.get("target_1")) or _num(summary.get("target"))
    target_2 = _num(summary.get("target_2"))
    zone_low, zone_high = _zone(summary)
    conf = _confidence(summary)

    if stop is None or target_1 is None:
        return None, "missing stop or target_1"

    if conf < min_confidence and proposal == "BUY":
        # Market opens still need confidence at book open; we keep the plan and
        # let TechDeskBook / process_batch enforce min_confidence.
        pass

    invalidation = str(summary.get("invalidation") or "").strip() or (
        f"Break of stop {stop:.2f}"
    )
    rationale = (
        f"MA proposal {proposal}; bias {summary.get('bias', 'n/a')}; "
        f"zone {zone_low}–{zone_high}; stop {stop}; T1 {target_1}."
    )

    base = {
        "ticker": ticker,
        "stop_loss": round(stop, 2),
        "target_1": round(target_1, 2),
        "target_2": round(target_2, 2) if target_2 is not None else None,
        "confidence": conf,
        "bias": _bias(summary),
        "invalidation": invalidation,
        "rationale": rationale,
        "zone_low": round(zone_low, 2) if zone_low is not None else None,
        "zone_high": round(zone_high, 2) if zone_high is not None else None,
    }

    def _wait_plan() -> Tuple[Optional[TechTradePlan], Optional[str]]:
        if zone_low is None or zone_high is None:
            return None, f"{proposal} without entry zone"
        if not _zone_between_stop_and_t1(stop, zone_low, zone_high, target_1):
            return None, f"{proposal} zone not between stop and T1"
        return (
            TechTradePlan(
                action=PlanAction.WAIT,
                entry_type=EntryType.LIMIT_ZONE,
                **base,
            ),
            None,
        )

    if proposal in _WAIT_PROPOSALS:
        return _wait_plan()

    if proposal != "BUY":
        return None, f"unsupported proposal={proposal}"

    # Anti-chase: live price above buying zone → park as limit_zone wait
    if (
        zone_high is not None
        and current_price is not None
        and current_price > zone_high
    ):
        return _wait_plan()

    # Market open: need a live (or zone) entry between stop and T1
    if current_price is not None and current_price > 0:
        entry_ref = current_price
    elif zone_high is not None:
        entry_ref = zone_high
    else:
        return None, "BUY without price or entry zone"

    if not (stop < entry_ref < target_1):
        return None, f"BUY invalid levels stop={stop} entry={entry_ref} t1={target_1}"

    plan = TechTradePlan(
        action=PlanAction.OPEN,
        entry_type=EntryType.MARKET,
        **base,
    )
    return plan, None


def batch_decision_from_ma_snapshots(
    snapshots: List[TechReportSnapshot],
    prices: Dict[str, float],
    *,
    min_confidence: int = 60,
) -> TechDeskBatchDecision:
    """Turn a list of MA report snapshots into a Tech Desk batch decision."""
    opens: List[TechTradePlan] = []
    waits: List[TechTradePlan] = []
    skips: List[SkipEntry] = []

    for snap in snapshots:
        summary = snap.pm_summary or {}
        price = prices.get(snap.ticker)
        plan, reason = trade_plan_from_pm_summary(
            snap.ticker,
            summary,
            price,
            min_confidence=min_confidence,
        )
        if plan is None:
            skips.append(SkipEntry(ticker=snap.ticker, reason=reason or "skipped"))
            continue
        if plan.action == PlanAction.WAIT or plan.entry_type == EntryType.LIMIT_ZONE:
            waits.append(plan)
        else:
            opens.append(plan)

    return TechDeskBatchDecision(opens=opens, waits=waits, skips=skips)
