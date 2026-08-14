"""Portfolio paper-trade manager for nanda_swing_scanner."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional, TYPE_CHECKING

from .book import NSSPositionBook
from tradingagents.paper.json_store import dump_json

if TYPE_CHECKING:
    from tradingagents.screening.nss_screener import NSSPick

_DEFAULT_HOME = os.path.join(os.path.expanduser("~"), ".tradingagents")
BEARISH_RATINGS = {"Underweight", "Sell"}


@dataclass
class ReplacementProposal:
    id: str
    proposed_at: str
    close_ticker: str
    close_stock_name: str
    close_reason: str
    close_score: float
    new_ticker: str
    new_stock_name: str
    new_composite_score: float
    approved: Optional[bool] = None


class NSSPaperTradeManager:
    def __init__(self, config: Optional[dict] = None):
        cfg = config or {}
        self.config = cfg
        self.book = NSSPositionBook(cfg)
        self.max_positions = int(cfg.get("nss_max_positions", 20))
        self.max_per_sector = int(cfg.get("nss_max_per_sector", 4))
        nss_dir = Path(
            cfg.get("nss_book_path", os.path.join(_DEFAULT_HOME, "nss", "positions.json"))
        ).parent
        self.pending_path = Path(cfg.get("nss_pending_path") or nss_dir / "pending_replacements.json")
        self.daily_dir = Path(cfg.get("nss_daily_dir") or nss_dir / "daily")
        self.daily_dir.mkdir(parents=True, exist_ok=True)

    def _load_pending(self) -> List[dict]:
        if not self.pending_path.exists():
            return []
        try:
            return json.loads(self.pending_path.read_text(encoding="utf-8")).get("proposals", [])
        except Exception:  # noqa: BLE001
            return []

    def _save_pending(self, proposals: List[dict]) -> None:
        self.pending_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.pending_path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"proposals": proposals}, indent=2), encoding="utf-8")
        tmp.replace(self.pending_path)

    def pending_proposals(self) -> List[ReplacementProposal]:
        return [
            ReplacementProposal(**p)
            for p in self._load_pending()
            if not p.get("approved")
        ]

    def _weakest_open(self, today_tickers: set[str]) -> Optional[dict]:
        open_positions = [p for p in self.book.positions if p.get("status") == "open"]
        if not open_positions:
            return None

        def score(p: dict) -> float:
            s = 0.0
            entry = float(p.get("entry_price") or 0)
            price = self.book.latest_price(p["ticker"]) or entry
            ret = (price - entry) / entry if entry else 0.0
            s += ret * 100
            if p["ticker"] not in today_tickers:
                s -= 5.0
            rating = (p.get("ai_rating") or "").strip()
            if rating in BEARISH_RATINGS:
                s -= 10.0
            s += float(p.get("composite_score") or 0)
            return s

        return min(open_positions, key=score)

    def _proposal_id(self) -> str:
        return datetime.now().strftime("%Y%m%d%H%M%S%f")

    def propose_replacement(self, pick: "NSSPick", today_tickers: set[str]) -> ReplacementProposal:
        weak = self._weakest_open(today_tickers)
        if weak is None:
            raise RuntimeError("No open position to replace")
        return ReplacementProposal(
            id=self._proposal_id(),
            proposed_at=datetime.now().isoformat(timespec="seconds"),
            close_ticker=weak["ticker"],
            close_stock_name=weak.get("stock_name", weak["ticker"]),
            close_reason="weakest_in_portfolio",
            close_score=0.0,
            new_ticker=pick.symbol,
            new_stock_name=pick.stock_name,
            new_composite_score=pick.composite_score,
        )

    def approve_replacement(self, proposal_id: str, pick: "NSSPick") -> bool:
        """Disabled — positions exit via stop/target (or time) only."""
        pending = self._load_pending()
        if pending:
            self._save_pending([])
        return False

    def run_daily(
        self,
        picks: List["NSSPick"],
        screen_date: Optional[str] = None,
        approve: Optional[Callable[[ReplacementProposal], bool]] = None,
    ) -> dict:
        screen_date = screen_date or datetime.now().strftime("%Y-%m-%d")
        report: dict = {
            "date": screen_date,
            "chart_timeframe": "1d",
            "screener_picks": len(picks),
            "exits": [],
            "opened": [],
            "skipped_duplicate": [],
            "skipped_sector_cap": [],
            "proposals": [],
            "approved_replacements": [],
        }

        legacy = self.book.close_legacy_runners(as_of=screen_date)
        exit_summary = self.book.evaluate_and_close_exits(as_of=screen_date)
        report["exits"] = legacy + exit_summary.get("closed", [])
        report["legacy_runner_closes"] = [e["ticker"] for e in legacy]

        open_count = self.book.open_count()
        sector_counts = self.book.sector_open_counts()

        if self._load_pending():
            self._save_pending([])  # foreclosure disabled

        for pick in picks:
            if self.book.has_open_position(pick.symbol):
                self.book.touch_screen_date(pick.symbol, screen_date)
                report["skipped_duplicate"].append(pick.symbol)
                continue

            sector = pick.sector or ""
            if sector_counts.get(sector, 0) >= self.max_per_sector:
                report["skipped_sector_cap"].append(pick.symbol)
                continue

            if open_count < self.max_positions:
                pos = self.book.open_position(pick, screen_date)
                if pos:
                    report["opened"].append(pick.symbol)
                    open_count += 1
                    sector_counts[sector] = sector_counts.get(sector, 0) + 1
                continue

            # Portfolio full — no foreclosure; wait for stop/target (or time) exits.
            report.setdefault("skipped_full", []).append(pick.symbol)
            continue

        report["open_positions"] = self.book.open_count()
        report["stats"] = self.book.stats()

        dump_json(self.daily_dir / f"{screen_date}.json", report)
        return report

    def latest_daily_report(self) -> Optional[dict]:
        files = sorted(self.daily_dir.glob("*.json"), reverse=True)
        if not files:
            return None
        return json.loads(files[0].read_text(encoding="utf-8"))
