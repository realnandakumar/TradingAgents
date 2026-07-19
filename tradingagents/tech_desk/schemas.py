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
    MARKET_NEAR_SUPPORT = "market_near_support"


class Bias(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class PmSummary(BaseModel):
    """Structured levels block written by tech-analyze for the Tech Desk PM."""

    proposal: str = Field(
        description="Exactly one of BUY, HOLD, WAIT, or SELL (uppercase).",
    )
    bias: str = Field(
        description="Directional bias: bullish, bearish, or neutral.",
    )
    confidence: int = Field(
        ge=0,
        le=100,
        description="Conviction 0-100 from the technical analysis.",
    )
    entry_zone_low: float = Field(
        description=(
            "Pullback / buy-zone lower price. Required (>0) for BUY/WAIT/HOLD "
            "when a zone is described; use 0 only for SELL or no zone."
        ),
    )
    entry_zone_high: float = Field(
        description=(
            "Pullback / buy-zone upper price. Must be > entry_zone_low when both >0."
        ),
    )
    stop: float = Field(
        description=(
            "Hard stop-loss price. Must be >0 whenever proposal is BUY, WAIT, or HOLD "
            "with an actionable setup."
        ),
    )
    target_1: float = Field(
        description="Primary profit target. Must be >0 for BUY/WAIT/HOLD setups.",
    )
    target_2: float = Field(
        default=0.0,
        description="Optional stretch target; 0 if none.",
    )
    atr: float = Field(default=0.0, description="ATR value from the report (0 if unknown).")
    sma_50: float = Field(default=0.0, description="50 SMA (0 if unknown).")
    sma_200: float = Field(default=0.0, description="200 SMA (0 if unknown).")
    key_support: str = Field(default="", description="Nearest support level or description.")
    key_resistance: str = Field(
        default="", description="Nearest resistance level or description."
    )
    invalidation: str = Field(
        default="",
        description="One sentence: what price action invalidates the thesis.",
    )

    def as_dict(self) -> dict:
        return self.model_dump()


class TechTradePlan(BaseModel):
    """Trade plan for one ticker from the Tech Desk PM."""

    ticker: str = Field(description="NSE ticker symbol, e.g. RELIANCE.NS")
    action: PlanAction = Field(
        description="open = enter now or on zone fill; wait = limit zone only; skip = pass"
    )
    entry_type: EntryType = Field(
        description="market = enter at current price; limit_zone = wait for pullback zone; "
        "market_near_support = enter near support with tight stop at zone_low",
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


class TechDeskTraderDisposition(str, Enum):
    OPEN = "open"
    WAIT = "wait"
    SKIP = "skip"


class TechDeskTraderDecision(BaseModel):
    """Per-ticker Tech Desk Trader output — owns R:R and entry type (Path 5).

    Market Analyst supplies candidate levels; this agent decides whether the
    desk should trade and with what geometry.
    """

    ticker: str = Field(description="NSE ticker symbol, e.g. RELIANCE.NS")
    disposition: TechDeskTraderDisposition = Field(
        description="open / wait / skip — skip when no edge or R:R too weak",
    )
    entry_type: Optional[EntryType] = Field(
        default=None,
        description="Required for open/wait. Omit when disposition is skip.",
    )
    zone_low: Optional[float] = Field(default=None)
    zone_high: Optional[float] = Field(default=None)
    stop_loss: Optional[float] = Field(
        default=None,
        description="Required for open/wait.",
    )
    target_1: Optional[float] = Field(
        default=None,
        description="Required for open/wait. Must clear min reward:risk vs zone mid.",
    )
    target_2: Optional[float] = Field(default=None)
    confidence: int = Field(
        default=50,
        ge=0,
        le=100,
        description="Trader conviction 0-100 after geometry check",
    )
    bias: Bias = Field(default=Bias.NEUTRAL)
    invalidation: str = Field(default="")
    rationale: str = Field(
        description="Why this disposition — cite MA levels and R:R (2-4 sentences)",
    )
    skip_reason: Optional[str] = Field(
        default=None,
        description="When disposition is skip, short reason for the desk log",
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


def _price_vs_zone(
    price: Optional[float],
    zone_low: Optional[float],
    zone_high: Optional[float],
) -> str:
    if price is None or zone_low is None or zone_high is None:
        return "—"
    if zone_low <= price <= zone_high:
        return "inside zone"
    if price > zone_high:
        return "above zone"
    return "below zone"


def _dist_to_zone_pct(
    price: Optional[float],
    zone_low: Optional[float],
    zone_high: Optional[float],
) -> str:
    if price is None or zone_low is None or zone_high is None:
        return "—"
    if zone_low <= price <= zone_high:
        return "0% (in zone)"
    if price > zone_high:
        pct = (price - zone_high) / price * 100
        return f"+{pct:.1f}% above"
    pct = (zone_low - price) / price * 100
    return f"+{pct:.1f}% below"


def _dist_to_tgt_pct(price: Optional[float], target: Optional[float]) -> str:
    if price is None or target is None:
        return "—"
    pct = (target - price) / price * 100
    return f"{pct:+.1f}%"


def render_batch_decision(
    decision: Optional[TechDeskBatchDecision],
    prices: Optional[dict[str, float]] = None,
) -> str:
    if decision is None:
        return "# Tech Desk Batch Decision\n\n_(no decision returned)_"

    lines = ["# Tech Desk Batch Decision", ""]

    if prices:
        rows: list[tuple[str, str, str, str, str, str, str]] = []
        for p in decision.opens:
            px = prices.get(p.ticker)
            cur = f"{px:.2f}" if px is not None else "?"
            zone = (
                f"{p.zone_low:.2f}–{p.zone_high:.2f}"
                if p.entry_type == EntryType.LIMIT_ZONE
                and p.zone_low is not None
                and p.zone_high is not None
                else "market"
            )
            rows.append(
                (
                    p.ticker,
                    cur,
                    zone,
                    _price_vs_zone(px, p.zone_low, p.zone_high),
                    _dist_to_zone_pct(px, p.zone_low, p.zone_high),
                    _dist_to_tgt_pct(px, p.target_1),
                    "open",
                )
            )
        for p in decision.waits:
            px = prices.get(p.ticker)
            cur = f"{px:.2f}" if px is not None else "?"
            zone = (
                f"{p.zone_low:.2f}–{p.zone_high:.2f}"
                if p.zone_low is not None and p.zone_high is not None
                else "?"
            )
            rows.append(
                (
                    p.ticker,
                    cur,
                    zone,
                    _price_vs_zone(px, p.zone_low, p.zone_high),
                    _dist_to_zone_pct(px, p.zone_low, p.zone_high),
                    _dist_to_tgt_pct(px, p.target_1),
                    "wait",
                )
            )
        for s in decision.skips:
            px = prices.get(s.ticker)
            cur = f"{px:.2f}" if px is not None else "?"
            rows.append((s.ticker, cur, "—", "—", "—", "—", "skip"))

        if rows:
            lines.append("## Price check (live at process time)")
            lines.append("")
            lines.append(
                "| Ticker | Current | Entry zone | vs zone | Δ zone | Δ T1 | Action |"
            )
            lines.append("| --- | ---: | --- | --- | ---: | ---: | --- |")
            for ticker, cur, zone, vs, dz, dt, action in rows:
                sym = ticker.replace(".NS", "")
                lines.append(f"| {sym} | {cur} | {zone} | {vs} | {dz} | {dt} | {action} |")
            lines.append("")

    if decision.closes:
        lines.append(f"**Closes** ({len(decision.closes)}): {', '.join(decision.closes)}")
        lines.append("")
    if decision.opens:
        lines.append(f"**Opens** ({len(decision.opens)}, best-first):")
        for p in decision.opens:
            zone = ""
            if p.entry_type in (EntryType.LIMIT_ZONE, EntryType.MARKET_NEAR_SUPPORT) and p.zone_low is not None and p.zone_high is not None:
                zone = f" · zone {p.zone_low:.2f}–{p.zone_high:.2f}"
            mode = p.entry_type.value
            if p.entry_type == EntryType.MARKET_NEAR_SUPPORT:
                mode = "market_near_support (proximity)"
            tgt2 = f" · T2 {p.target_2:.2f}" if p.target_2 is not None else ""
            lines.append(
                f"- **{p.ticker}** · {mode}{zone} · "
                f"stop {p.stop_loss:.2f} · T1 {p.target_1:.2f}{tgt2} · "
                f"conf {p.confidence} · {p.bias.value}"
            )
            if p.rationale:
                snippet = p.rationale.strip().replace("\n", " ")
                if len(snippet) > 160:
                    snippet = snippet[:157] + "..."
                lines.append(f"  _{snippet}_")
        lines.append("")
    if decision.waits:
        lines.append(f"**Waits** ({len(decision.waits)}, limit zone):")
        for p in decision.waits:
            zone = f"{p.zone_low:.2f}–{p.zone_high:.2f}" if p.zone_low is not None and p.zone_high is not None else "?"
            lines.append(
                f"- **{p.ticker}** · zone {zone} · stop {p.stop_loss:.2f} · "
                f"T1 {p.target_1:.2f} · conf {p.confidence}"
            )
            if p.rationale:
                snippet = p.rationale.strip().replace("\n", " ")
                if len(snippet) > 160:
                    snippet = snippet[:157] + "..."
                lines.append(f"  _{snippet}_")
        lines.append("")
    if decision.skips:
        lines.append(f"**Skips** ({len(decision.skips)}):")
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
