"""Universe gates for desk process decisions (Tech watchlist / RS candidates)."""

from __future__ import annotations

import logging
from typing import Iterable, List, Optional, Set

from tradingagents.tech_desk.report_loader import _ticker_match_keys
from tradingagents.tech_desk.schemas import SkipEntry, TechDeskBatchDecision, TechTradePlan

logger = logging.getLogger(__name__)


def universe_key_set(tickers: Iterable[str]) -> Set[str]:
    """Flatten tickers into bare + .NS/.BO match keys."""
    keys: Set[str] = set()
    for t in tickers:
        keys |= _ticker_match_keys(str(t))
    return keys


def ticker_in_universe(ticker: str, universe: Set[str]) -> bool:
    if not universe:
        return False
    return bool(_ticker_match_keys(ticker) & universe)


def filter_decision_entries_to_universe(
    decision: TechDeskBatchDecision,
    allowed_tickers: Iterable[str],
    *,
    reason: str = "not in entry universe",
) -> TechDeskBatchDecision:
    """Drop opens/waits outside *allowed_tickers*; convert them to skips.

    Closes are left unchanged (may exit names no longer on the watchlist).
    """
    universe = universe_key_set(allowed_tickers)
    if not universe:
        rejected = list(decision.opens) + list(decision.waits)
        skips = list(decision.skips)
        for plan in rejected:
            skips.append(SkipEntry(ticker=plan.ticker, reason=reason))
        if rejected:
            logger.info(
                "Universe gate: rejected %d open/wait (empty universe)",
                len(rejected),
            )
        return decision.model_copy(
            update={"opens": [], "waits": [], "skips": skips}
        )

    opens: List[TechTradePlan] = []
    waits: List[TechTradePlan] = []
    skips: List[SkipEntry] = list(decision.skips)
    rejected = 0

    for plan in decision.opens:
        if ticker_in_universe(plan.ticker, universe):
            opens.append(plan)
        else:
            rejected += 1
            skips.append(SkipEntry(ticker=plan.ticker, reason=reason))

    for plan in decision.waits:
        if ticker_in_universe(plan.ticker, universe):
            waits.append(plan)
        else:
            rejected += 1
            skips.append(SkipEntry(ticker=plan.ticker, reason=reason))

    if rejected:
        logger.info(
            "Universe gate: rejected %d open/wait not in allowed set (%d allowed)",
            rejected,
            len(list(allowed_tickers)),
        )
    return decision.model_copy(update={"opens": opens, "waits": waits, "skips": skips})


def assert_pending_paths_isolated(
    tech_pending: Optional[str],
    rs_pending: Optional[str],
) -> None:
    """Raise if Tech and RS pending files would collide."""
    if not tech_pending or not rs_pending:
        return
    t = str(tech_pending).replace("\\", "/").lower()
    r = str(rs_pending).replace("\\", "/").lower()
    if t == r:
        raise ValueError(
            "Tech Desk and RS Desk pending paths must differ; "
            f"both point at {tech_pending}"
        )
