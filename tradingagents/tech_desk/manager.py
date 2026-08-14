"""Tech Desk paper-trade manager."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .book import TechDeskPositionBook
from .exits import ExitReason
from tradingagents.paper.json_store import dump_json
from .report_loader import TechReportSnapshot, load_tech_reports
from .schemas import (
    EntryType,
    PositionReviewAction,
    TechDeskBatchDecision,
    TechDeskPositionReview,
)

logger = logging.getLogger(__name__)

_DEFAULT_HOME = os.path.join(os.path.expanduser("~"), ".tradingagents")


class TechDeskPaperTradeManager:
    def __init__(self, config: Optional[dict] = None):
        cfg = config or {}
        self.config = cfg
        self.book = TechDeskPositionBook(cfg)
        self.max_positions = int(cfg.get("tech_desk_max_positions", 20))
        desk_dir = Path(
            cfg.get("tech_desk_book_path", os.path.join(_DEFAULT_HOME, "tech_desk", "positions.json"))
        ).parent
        self.daily_dir = Path(cfg.get("tech_desk_daily_dir") or desk_dir / "daily")
        self.process_log_dir = Path(cfg.get("tech_desk_process_log_dir") or desk_dir / "process")
        self.daily_dir.mkdir(parents=True, exist_ok=True)
        self.process_log_dir.mkdir(parents=True, exist_ok=True)

    def _weakest_open(self, batch_tickers: set[str]) -> Optional[dict]:
        """Kept for diagnostics; Tech Desk no longer forecloses to free slots."""
        open_positions = [p for p in self.book.positions if p.get("status") == "open"]
        if not open_positions:
            return None

        def score(p: dict) -> float:
            s = 0.0
            entry = float(p.get("entry_price") or 0)
            price = self.book.latest_price(p["ticker"]) or entry
            ret = (price - entry) / entry if entry else 0.0
            s += ret * 100
            s += float(p.get("confidence") or 0) * 0.1
            if p["ticker"] not in batch_tickers:
                s -= 5.0
            if (p.get("bias") or "").lower() == "bearish":
                s -= 15.0
            return s

        return min(open_positions, key=score)

    def _foreclose_weakest(self, batch_tickers: set[str], as_of: str) -> Optional[str]:
        """Disabled — Tech Desk exits only via stop / targets (and daily rules)."""
        return None

    def _snapshot_meta(self, ticker: str, snapshots: Dict[str, TechReportSnapshot]) -> dict:
        snap = snapshots.get(ticker.upper()) or snapshots.get(ticker)
        if snap is None:
            return {}
        return {"report_path": snap.report_path, "report_date": snap.report_date}

    def process_batch(
        self,
        decision: TechDeskBatchDecision,
        prices: Dict[str, float],
        process_date: Optional[str] = None,
        snapshots: Optional[Dict[str, TechReportSnapshot]] = None,
    ) -> dict:
        process_date = process_date or datetime.now().strftime("%Y-%m-%d")
        snapshots = snapshots or {}
        batch_tickers = {
            *(p.ticker for p in decision.opens),
            *(p.ticker for p in decision.waits),
            *(s.ticker for s in decision.skips),
        }

        report: dict = {
            "date": process_date,
            "closes": [],
            "opened": [],
            "waits": [],
            "skipped": [],
            "foreclosures": [],
            "pending_replacements": [],
            "exits": [],
        }

        for ticker in decision.closes:
            if not self.book.has_open_position(ticker):
                continue
            price = prices.get(ticker) or self.book.latest_price(ticker)
            if price is None:
                continue
            if self.book.close_position(ticker, price, process_date, ExitReason.REVIEW_CLOSE.value):
                report["closes"].append({"ticker": ticker, "exit_price": price})

        for plan in decision.waits:
            if plan.entry_type != EntryType.LIMIT_ZONE:
                plan = plan.model_copy(update={"entry_type": EntryType.LIMIT_ZONE})
            if self.book.has_open_position(plan.ticker):
                report["skipped"].append({"ticker": plan.ticker, "reason": "already open"})
                continue
            err = self.book.validate_pending_plan(plan, prices.get(plan.ticker))
            if err:
                report["skipped"].append({"ticker": plan.ticker, "reason": err})
                if err == "post_target_pullback":
                    meta = self._snapshot_meta(plan.ticker, snapshots)
                    self.book.record_pending_dismissal(
                        plan.ticker,
                        err,
                        report_date=meta.get("report_date"),
                        plan_date=process_date,
                    )
                continue
            meta = self._snapshot_meta(plan.ticker, snapshots)
            row = self.book.add_pending_entry(
                plan,
                process_date,
                current_price=prices.get(plan.ticker),
                **meta,
            )
            if row:
                report["waits"].append(plan.ticker)
            else:
                dismissed = self.book.is_pending_dismissed(plan.ticker, meta.get("report_date"))
                reason = f"dismissed ({dismissed})" if dismissed else "pending validation failed"
                report["skipped"].append({"ticker": plan.ticker, "reason": reason})

        for skip in decision.skips:
            report["skipped"].append({"ticker": skip.ticker, "reason": skip.reason})

        for plan in decision.opens:
            if self.book.has_open_position(plan.ticker):
                report["skipped"].append({"ticker": plan.ticker, "reason": "already open"})
                continue

            if self.book.open_count() >= self.max_positions:
                report["skipped"].append({
                    "ticker": plan.ticker,
                    "reason": "portfolio full — wait for stop/target exit (no foreclosure)",
                })
                continue

            if plan.entry_type == EntryType.LIMIT_ZONE:
                err = self.book.validate_pending_plan(plan, prices.get(plan.ticker))
                if err:
                    report["skipped"].append({"ticker": plan.ticker, "reason": err})
                    if err == "post_target_pullback":
                        meta = self._snapshot_meta(plan.ticker, snapshots)
                        self.book.record_pending_dismissal(
                            plan.ticker,
                            err,
                            report_date=meta.get("report_date"),
                            plan_date=process_date,
                        )
                    continue
                meta = self._snapshot_meta(plan.ticker, snapshots)
                row = self.book.add_pending_entry(
                    plan,
                    process_date,
                    current_price=prices.get(plan.ticker),
                    **meta,
                )
                if row:
                    report["waits"].append(plan.ticker)
                else:
                    dismissed = self.book.is_pending_dismissed(
                        plan.ticker, meta.get("report_date")
                    )
                    reason = f"dismissed ({dismissed})" if dismissed else "pending validation failed"
                    report["skipped"].append({"ticker": plan.ticker, "reason": reason})
                continue

            if plan.entry_type not in (EntryType.MARKET, EntryType.MARKET_NEAR_SUPPORT):
                report["skipped"].append({"ticker": plan.ticker, "reason": "unsupported entry type"})
                continue

            entry_price = prices.get(plan.ticker) or self.book.latest_price(plan.ticker)
            if entry_price is None:
                report["skipped"].append({"ticker": plan.ticker, "reason": "no price"})
                continue

            meta = self._snapshot_meta(plan.ticker, snapshots)
            # Fetch hist for T1 check inside open_from_plan; also block if price >= T1.
            if entry_price >= float(plan.target_1):
                report["skipped"].append({"ticker": plan.ticker, "reason": "post_target_pullback"})
                self.book.record_pending_dismissal(
                    plan.ticker,
                    "post_target_pullback",
                    report_date=meta.get("report_date"),
                    plan_date=process_date,
                )
                continue

            pos = self.book.open_from_plan(plan, entry_price, process_date, **meta)
            if pos:
                report["opened"].append(plan.ticker)
            else:
                report["skipped"].append({"ticker": plan.ticker, "reason": "open rejected"})

        report["open_positions"] = self.book.open_count()
        report["stats"] = self.book.stats()
        report["summary"] = {
            "closes": len(report["closes"]),
            "opened": len(report["opened"]),
            "waits": len(report["waits"]),
            "skipped": len(report["skipped"]),
            "pending_replacements": len(report["pending_replacements"]),
        }

        dump_json(self.process_log_dir / f"{process_date}.json", report, default=str)
        return report

    @staticmethod
    def replacement_id(item: dict) -> str:
        if item.get("id"):
            return str(item["id"])
        foreclose = item.get("foreclose") or ""
        open_ticker = item.get("open") or ""
        return f"{foreclose}->{open_ticker}"

    def apply_pending_replacements(
        self,
        process_date: Optional[str] = None,
        prices: Optional[Dict[str, float]] = None,
        selected_ids: Optional[List[str]] = None,
    ) -> dict:
        """Disabled — Tech Desk does not foreclose; exits are stop / targets only."""
        process_date = process_date or datetime.now().strftime("%Y-%m-%d")
        log_path = self.process_log_dir / f"{process_date}.json"
        cleared = 0
        if log_path.exists():
            try:
                log = json.loads(log_path.read_text(encoding="utf-8"))
                pending = log.get("pending_replacements") or []
                if pending:
                    cleared = len(pending)
                    log["pending_replacements"] = []
                    log["replacements_applied"] = []
                    log["replacements_skipped"] = [
                        {"reason": "foreclosure disabled — exits via stop/target only"}
                    ]
                    log_path.write_text(
                        json.dumps(log, indent=2, default=str), encoding="utf-8"
                    )
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "Could not clear stale replacements in %s (%s)", log_path, e
                )
        return {
            "applied": [],
            "skipped": [],
            "cleared": cleared,
            "message": (
                "Tech Desk foreclosure is disabled. "
                "Positions exit on stop loss or targets only."
            ),
            "date": process_date,
        }

    def apply_review(
        self,
        review: TechDeskPositionReview,
        as_of: Optional[str] = None,
    ) -> dict:
        """Execute CLOSE / tighten_stop / trail_stop from a weekly review."""
        as_of = as_of or datetime.now().strftime("%Y-%m-%d")
        applied: dict = {"closed": [], "stops_raised": [], "skipped": []}

        for item in review.reviews:
            ticker = item.ticker
            if not self.book.has_open_position(ticker):
                applied["skipped"].append({"ticker": ticker, "reason": "not open"})
                continue

            if item.action == PositionReviewAction.CLOSE:
                price = self.book.latest_price(ticker)
                if price is None:
                    applied["skipped"].append({"ticker": ticker, "reason": "no price"})
                    continue
                if self.book.close_position(
                    ticker, price, as_of, ExitReason.REVIEW_CLOSE.value
                ):
                    applied["closed"].append(ticker)
                continue

            if item.action in (
                PositionReviewAction.TIGHTEN_STOP,
                PositionReviewAction.TRAIL_STOP,
            ):
                if item.new_stop is None:
                    applied["skipped"].append({"ticker": ticker, "reason": "no new_stop"})
                    continue
                new_stop = round(float(item.new_stop), 2)
                for p in self.book.positions:
                    if p["ticker"] != ticker or p.get("status") != "open":
                        continue
                    entry = float(p.get("entry_price") or 0)
                    cur = float(p.get("trailing_stop") or p.get("stop_loss") or 0)
                    if new_stop >= entry:
                        applied["skipped"].append({
                            "ticker": ticker,
                            "reason": "new_stop above entry",
                        })
                        break
                    if new_stop > cur:
                        p["trailing_stop"] = new_stop
                        p["stop_loss"] = new_stop
                        if entry > 0:
                            p["stop_loss_pct"] = round(-100.0 * (entry - new_stop) / entry, 2)
                        applied["stops_raised"].append(ticker)
                    else:
                        applied["skipped"].append({
                            "ticker": ticker,
                            "reason": "new_stop not higher than current",
                        })
                    break

        self.book._save()
        return applied

    def run_daily(self, as_of: Optional[str] = None) -> dict:
        as_of = as_of or datetime.now().strftime("%Y-%m-%d")
        report: dict = {
            "date": as_of,
            "exits": [],
            "zone_fills": [],
            "pending_removed": [],
        }

        exit_summary = self.book.evaluate_and_close_exits(as_of=as_of)
        report["exits"] = exit_summary.get("closed", [])

        fills = self.book.evaluate_pending_fills(as_of=as_of)
        report["zone_fills"] = fills

        lifecycle = self.book.evaluate_pending_lifecycle(as_of=as_of)
        report["pending_removed"] = lifecycle.get("removed", [])

        report["open_positions"] = self.book.open_count()
        report["pending_entries"] = len(self.book.pending_entries())
        report["stats"] = self.book.stats()

        dump_json(self.daily_dir / f"{as_of}.json", report, default=str)
        return report

    def run_review(
        self,
        llm: Any,
        reports_dir: Optional[str] = None,
        as_of: Optional[str] = None,
        *,
        apply: bool = False,
    ) -> dict:
        from tradingagents.agents.utils.structured import bind_structured
        from tradingagents.tech_desk.schemas import render_position_review

        as_of = as_of or datetime.now().strftime("%Y-%m-%d")
        reports_dir = reports_dir or self.config.get("tech_analyze_reports_dir")
        max_age = self.config.get("tech_desk_max_report_age_days")
        open_positions = [p for p in self.book.positions if p.get("status") == "open"]

        if not open_positions:
            return {"date": as_of, "review": None, "message": "no open positions"}

        snapshots, _stale = load_tech_reports(
            reports_dir,
            max_report_age_days=max_age,
            as_of=as_of,
        )
        snap_by_ticker = {s.ticker.upper(): s for s in snapshots}
        prices = {p["ticker"]: self.book.latest_price(p["ticker"]) for p in open_positions}

        from tradingagents.tech_desk.report_excerpt import format_report_excerpt

        blocks: List[str] = []
        for p in open_positions:
            ticker = p["ticker"]
            snap = snap_by_ticker.get(ticker.upper())
            if snap:
                report_excerpt = format_report_excerpt(
                    snap.market_text,
                    ticker=snap.ticker,
                    report_date=snap.report_date,
                    as_of=as_of,
                    pm_summary=snap.pm_summary,
                )
            else:
                report_excerpt = "(no saved report)"
            price = prices.get(ticker) or float(p.get("entry_price") or 0)
            blocks.append(
                f"### {ticker}\n"
                f"Entry {p.get('entry_price')} · now {price} · stop {p.get('stop_loss')} · "
                f"target {p.get('target_1')} · held since {p.get('screen_date')}\n\n"
                f"{report_excerpt}"
            )

        prompt = f"""Weekly Tech Desk review of open long-only NSE positions.

Recommend per ticker: hold, close, tighten_stop, or trail_stop.
If tightening/trailing, set new_stop. Ground decisions in the latest saved reports.

{chr(10).join(blocks)}
"""

        structured_llm = bind_structured(llm, TechDeskPositionReview, "Tech Desk Review")
        review: Optional[TechDeskPositionReview] = None
        if structured_llm is not None:
            try:
                review = structured_llm.invoke(prompt)
            except Exception as exc:
                logger.warning("Tech Desk review failed (%s)", exc)

        result = {
            "date": as_of,
            "review": review.model_dump() if review else None,
            "review_markdown": render_position_review(review) if review else None,
            "open_positions": len(open_positions),
        }

        if apply and review is not None:
            result["applied"] = self.apply_review(review, as_of=as_of)

        out = self.process_log_dir / f"review_{as_of}.json"
        out.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
        return result

    def latest_daily_report(self) -> Optional[dict]:
        files = sorted(self.daily_dir.glob("*.json"), reverse=True)
        if not files:
            return None
        return json.loads(files[0].read_text(encoding="utf-8"))

    def latest_process_report(self) -> Optional[dict]:
        files = sorted(
            (p for p in self.process_log_dir.glob("*.json") if not p.name.startswith("review_")),
            reverse=True,
        )
        if not files:
            return None
        return json.loads(files[0].read_text(encoding="utf-8"))
