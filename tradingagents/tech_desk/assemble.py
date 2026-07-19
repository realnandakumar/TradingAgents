"""Script portfolio assemble for Tech Desk daily Process (Path 5).

Trader owns plans; this module only ranks, fills slots, and parks waits.
Daily closes / replacements are out of scope — weekly position review covers
position management; replacement heuristics can be added later.
"""

from __future__ import annotations

from typing import List, Optional, Sequence

from tradingagents.tech_desk.schemas import (
    EntryType,
    PlanAction,
    SkipEntry,
    TechDeskBatchDecision,
    TechTradePlan,
)
from tradingagents.tech_desk.trader_validation import reward_risk_from_levels


def _plan_sort_key(plan: TechTradePlan) -> tuple:
    """Higher confidence first; then higher R:R; then ticker for stability."""
    rr = reward_risk_from_levels(
        plan.stop_loss,
        plan.target_1,
        zone_low=plan.zone_low,
        zone_high=plan.zone_high,
    )
    return (-int(plan.confidence or 0), -(rr or 0.0), plan.ticker.upper())


def _demote_open_to_wait(plan: TechTradePlan) -> Optional[TechTradePlan]:
    """Park a slot-overflow open as wait when a zone exists."""
    if plan.zone_low is None or plan.zone_high is None:
        return None
    if float(plan.zone_high) <= float(plan.zone_low):
        return None
    return plan.model_copy(
        update={
            "action": PlanAction.WAIT,
            "entry_type": EntryType.LIMIT_ZONE,
            "rationale": (
                f"{plan.rationale} [script PM: demoted open→wait — no free slots]"
            ).strip(),
        }
    )


def assemble_decision_from_traders(
    trader_plans: Sequence[TechTradePlan],
    trader_skips: Sequence[SkipEntry],
    *,
    slots_available: int,
    extra_skips: Optional[Sequence[SkipEntry]] = None,
) -> TechDeskBatchDecision:
    """Build a batch decision without an LLM Portfolio Manager.

    - Opens: trader OPEN plans, ranked, capped at ``slots_available``
    - Overflow opens: demote to WAIT if zone exists, else skip
    - Waits: all trader WAIT plans (plus demotions)
    - Closes: always empty (weekly review path)
    - Skips: trader skips + extras + overflow without zone
    """
    opens_in = sorted(
        [p for p in trader_plans if p.action == PlanAction.OPEN],
        key=_plan_sort_key,
    )
    waits_in = sorted(
        [p for p in trader_plans if p.action == PlanAction.WAIT],
        key=_plan_sort_key,
    )

    slots = max(0, int(slots_available))
    selected_opens = list(opens_in[:slots])
    overflow = list(opens_in[slots:])

    waits: List[TechTradePlan] = list(waits_in)
    skips: List[SkipEntry] = list(trader_skips)
    if extra_skips:
        skips.extend(extra_skips)

    seen_skip = {s.ticker.upper() for s in skips}
    for plan in overflow:
        demoted = _demote_open_to_wait(plan)
        if demoted is not None:
            waits.append(demoted)
        else:
            key = plan.ticker.upper()
            if key not in seen_skip:
                skips.append(
                    SkipEntry(
                        ticker=plan.ticker,
                        reason="no free slots and no zone to park as wait",
                    )
                )
                seen_skip.add(key)

    # Dedupe waits by ticker (keep higher-ranked / first)
    wait_by: dict[str, TechTradePlan] = {}
    for w in sorted(waits, key=_plan_sort_key):
        wait_by.setdefault(w.ticker.upper(), w)
    # Drop waits that are also selected opens
    open_keys = {p.ticker.upper() for p in selected_opens}
    waits_out = [w for k, w in wait_by.items() if k not in open_keys]
    waits_out.sort(key=_plan_sort_key)

    return TechDeskBatchDecision(
        opens=selected_opens,
        waits=waits_out,
        skips=skips,
        closes=[],
    )
