"""Persist Path-5 Trader decisions next to tech-analyze reports."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from tradingagents.tech_desk.report_loader import TechReportSnapshot
from tradingagents.tech_desk.schemas import SkipEntry, TechTradePlan
from tradingagents.tech_desk.trader_validation import reward_risk_from_levels


def _rr_for_plan(plan: TechTradePlan) -> Optional[float]:
    return reward_risk_from_levels(
        plan.stop_loss,
        plan.target_1,
        zone_low=plan.zone_low,
        zone_high=plan.zone_high,
    )


def trader_payload_from_plan(
    plan: TechTradePlan,
    *,
    process_date: str,
    report_date: Optional[str] = None,
) -> Dict[str, Any]:
    rr = _rr_for_plan(plan)
    return {
        "ticker": plan.ticker,
        "process_date": process_date,
        "report_date": report_date,
        "disposition": plan.action.value,
        "entry_type": plan.entry_type.value,
        "zone_low": plan.zone_low,
        "zone_high": plan.zone_high,
        "stop_loss": plan.stop_loss,
        "target_1": plan.target_1,
        "target_2": plan.target_2,
        "confidence": plan.confidence,
        "bias": plan.bias.value if hasattr(plan.bias, "value") else plan.bias,
        "invalidation": plan.invalidation,
        "rationale": plan.rationale,
        "reward_risk": round(rr, 2) if rr is not None else None,
        "skip_reason": None,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
    }


def trader_payload_from_skip(
    skip: SkipEntry,
    *,
    process_date: str,
    report_date: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "ticker": skip.ticker,
        "process_date": process_date,
        "report_date": report_date,
        "disposition": "skip",
        "entry_type": None,
        "zone_low": None,
        "zone_high": None,
        "stop_loss": None,
        "target_1": None,
        "target_2": None,
        "confidence": None,
        "bias": None,
        "invalidation": None,
        "rationale": None,
        "reward_risk": None,
        "skip_reason": skip.reason,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
    }


def render_trader_markdown(payload: Dict[str, Any]) -> str:
    ticker = payload.get("ticker") or "?"
    disp = str(payload.get("disposition") or "—").upper()
    lines = [
        f"# Tech Desk Trader — {ticker}",
        "",
        f"**Disposition**: {disp}",
        f"**Process date**: {payload.get('process_date') or '—'}",
        f"**Report date**: {payload.get('report_date') or '—'}",
        "",
    ]
    if payload.get("disposition") == "skip":
        lines.extend(
            [
                "## Skip reason",
                "",
                str(payload.get("skip_reason") or "—"),
                "",
            ]
        )
    else:
        zone = "—"
        if payload.get("zone_low") is not None and payload.get("zone_high") is not None:
            zone = f"{payload['zone_low']}–{payload['zone_high']}"
        lines.extend(
            [
                "## Levels",
                "",
                f"- Entry type: {payload.get('entry_type') or '—'}",
                f"- Zone: {zone}",
                f"- Stop: {payload.get('stop_loss')}",
                f"- Target 1: {payload.get('target_1')}",
                f"- Target 2: {payload.get('target_2') or '—'}",
                f"- R:R (zone mid): {payload.get('reward_risk') if payload.get('reward_risk') is not None else '—'}",
                f"- Confidence: {payload.get('confidence')}",
                f"- Bias: {payload.get('bias') or '—'}",
                "",
                "## Rationale",
                "",
                str(payload.get("rationale") or "—"),
                "",
                "## Invalidation",
                "",
                str(payload.get("invalidation") or "—"),
                "",
            ]
        )
    return "\n".join(lines)


def save_trader_report(report_dir: Path, payload: Dict[str, Any]) -> Path:
    report_dir = Path(report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    json_path = report_dir / "trader.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (report_dir / "trader.md").write_text(
        render_trader_markdown(payload), encoding="utf-8"
    )
    return json_path


def persist_trader_reports(
    *,
    snapshots_by_ticker: Dict[str, TechReportSnapshot],
    plans: Sequence[TechTradePlan],
    skips: Sequence[SkipEntry],
    process_date: str,
) -> List[str]:
    """Write trader.json/md beside each MA report dir. Returns saved ticker list."""
    saved: List[str] = []

    def _snap(ticker: str) -> Optional[TechReportSnapshot]:
        return snapshots_by_ticker.get(ticker.upper()) or snapshots_by_ticker.get(ticker)

    for plan in plans:
        snap = _snap(plan.ticker)
        if snap is None:
            continue
        payload = trader_payload_from_plan(
            plan, process_date=process_date, report_date=snap.report_date
        )
        save_trader_report(snap.report_dir, payload)
        saved.append(plan.ticker)

    for skip in skips:
        # Prefer writing skips that map to a snapshot (watchlist MA reports)
        snap = _snap(skip.ticker)
        if snap is None:
            continue
        # Don't overwrite a plan with a skip for the same ticker
        if any(p.ticker.upper() == skip.ticker.upper() for p in plans):
            continue
        payload = trader_payload_from_skip(
            skip, process_date=process_date, report_date=snap.report_date
        )
        save_trader_report(snap.report_dir, payload)
        saved.append(skip.ticker)

    return saved
