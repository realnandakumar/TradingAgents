"""Pydantic schemas for Tech Desk paper trading."""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class PlanAction(str, Enum):
    OPEN = "open"
    WAIT = "wait"
    SKIP = "skip"


class EntryType(str, Enum):
    MARKET = "market"
    LIMIT_ZONE = "limit_zone"


class Bias(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class TechTradePlan(BaseModel):
    """Trade plan for one ticker from the Tech Desk PM."""

    ticker: str = Field(description="NSE ticker symbol, e.g. RELIANCE.NS")
    action: PlanAction = Field(
        description="open = enter now or on zone fill; wait = limit zone only; skip = pass"
    )
    entry_type: EntryType = Field(
        description="market = enter at current price; limit_zone = wait for pullback zone"
    )
    zone_low: Optional[float] = Field(
        default=None,
        description="Pullback zone lower bound (required when entry_type is limit_zone)",
    )
    zone_high: Optional[float] = Field(
        default=None,
        description="Pullback zone upper bound (required when entry_type is limit_zone)",
    )
    stop_loss: float = Field(description="Hard stop-loss price in quote currency")
    target_1: float = Field(description="Primary profit target price")
    target_2: Optional[float] = Field(
        default=None,
        description="Optional stretch target; exit at target_2 if reached before target_1",
    )
    holding_days: Optional[int] = Field(
        default=None,
        description="Max trading days to hold; omit to use desk default",
    )
    confidence: int = Field(
        ge=0,
        le=100,
        description="Conviction score 0-100 for this setup",
    )
    bias: Bias = Field(description="Directional bias from the technical report")
    invalidation: str = Field(
        description="What price/action would invalidate the thesis (one sentence)",
    )
    rationale: str = Field(
        description="Why this action — grounded in the saved technical report (2-4 sentences)",
    )


class SkipEntry(BaseModel):
    ticker: str
    reason: str


class TechDeskBatchDecision(BaseModel):
    """PM batch decision across all candidate tech-analyze reports."""

    opens: List[TechTradePlan] = Field(
        default_factory=list,
        description="Ordered list of market-entry plans to open (best first)",
    )
    waits: List[TechTradePlan] = Field(
        default_factory=list,
        description="Pullback zone entries to park as pending",
    )
    skips: List[SkipEntry] = Field(
        default_factory=list,
        description="Tickers passed over with reason",
    )
    closes: List[str] = Field(
        default_factory=list,
        description="Open position tickers to exit (SELL = square off)",
    )


class PositionReviewAction(str, Enum):
    HOLD = "hold"
    CLOSE = "close"
    TIGHTEN_STOP = "tighten_stop"
    TRAIL_STOP = "trail_stop"


class PositionReviewItem(BaseModel):
    ticker: str
    action: PositionReviewAction = Field(
        description="Recommended action for this open position"
    )
    new_stop: Optional[float] = Field(
        default=None,
        description="Suggested stop if action is tighten_stop or trail_stop",
    )
    rationale: str = Field(description="Weekly review rationale grounded in latest report")


class TechDeskPositionReview(BaseModel):
    """Weekly LLM review of open Tech Desk positions."""

    summary: str = Field(description="Portfolio-level weekly summary (2-4 sentences)")
    reviews: List[PositionReviewItem] = Field(default_factory=list)


def render_batch_decision(decision: TechDeskBatchDecision) -> str:
    lines = ["# Tech Desk Batch Decision", ""]
    if decision.closes:
        lines.append(f"**Closes**: {', '.join(decision.closes)}")
        lines.append("")
    if decision.opens:
        lines.append("**Opens** (ordered):")
        for p in decision.opens:
            lines.append(f"- {p.ticker} ({p.entry_type.value}, conf={p.confidence})")
        lines.append("")
    if decision.waits:
        lines.append("**Waits** (zone):")
        for p in decision.waits:
            lines.append(
                f"- {p.ticker} zone {p.zone_low}-{p.zone_high} (conf={p.confidence})"
            )
        lines.append("")
    if decision.skips:
        lines.append("**Skips**:")
        for s in decision.skips:
            lines.append(f"- {s.ticker}: {s.reason}")
    return "\n".join(lines)


def render_position_review(review: TechDeskPositionReview) -> str:
    lines = ["# Tech Desk Weekly Review", "", f"**Summary**: {review.summary}", ""]
    for item in review.reviews:
        lines.append(f"### {item.ticker}")
        lines.append(f"- **Action**: {item.action.value}")
        if item.new_stop is not None:
            lines.append(f"- **New stop**: {item.new_stop}")
        lines.append(f"- {item.rationale}")
        lines.append("")
    return "\n".join(lines)
