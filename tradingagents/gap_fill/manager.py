"""Portfolio paper-trade manager for Gap Fill."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional, TYPE_CHECKING

from .book import GapFillPositionBook
from tradingagents.paper.json_store import dump_json
from tradingagents.screening.gap_fill_engine import gap_trade_side, pick_passes_long_entry

if TYPE_CHECKING:
    from tradingagents.screening.gap_fill_screener import GapFillPick

_DEFAULT_HOME = os.path.join(os.path.expanduser("~"), ".tradingagents")


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
    new_signal_score: float
    new_flip_age: int
    approved: Optional[bool] = None


class GapFillPaperTradeManager:
    def __init__(self, config: Optional[dict] = None):
        cfg = config or {}
        self.config = cfg
        self.book = GapFillPositionBook(cfg)
        self.max_positions = int(cfg.get("gap_fill_max_positions", 20))
        self.max_per_sector = int(cfg.get("gap_fill_max_per_sector", 4))
        gap_dir = Path(
            cfg.get("gap_fill_book_path", os.path.join(_DEFAULT_HOME, "gap_fill", "positions.json"))
        ).parent
        self.pending_path = Path(cfg.get("gap_fill_pending_path") or gap_dir / "pending_replacements.json")
        self.daily_dir = Path(cfg.get("gap_fill_daily_dir") or gap_dir / "daily")
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

    def reset_portfolio(self) -> None:
        """Clear paper book and pending replacement proposals."""
        self.book.reset_book()
        if self.pending_path.exists():
            self._save_pending([])

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
            s += float(p.get("fill_pct") or 0) * 0.1
            s += abs(float(p.get("gap_pct") or 0))
            s -= float(p.get("gap_age") or 0)
            return s

        return min(open_positions, key=score)

    def _proposal_id(self) -> str:
        return datetime.now().strftime("%Y%m%d%H%M%S%f")

    def propose_replacement(self, pick: "GapFillPick", today_tickers: set[str]) -> ReplacementProposal:
        weak = self._weakest_open(today_tickers)
        if weak is None:
            raise RuntimeError("No open position to replace")
        return ReplacementProposal(
            id=self._proposal_id(),
            proposed_at=datetime.now().isoformat(timespec="seconds"),
            close_ticker=weak["ticker"],
            close_stock_name=weak.get("stock_name", weak["ticker"]),
            close_reason="weakest_in_portfolio",
            close_score=float(weak.get("fill_pct") or 0),
            new_ticker=pick.symbol,
            new_stock_name=pick.stock_name or pick.symbol,
            new_signal_score=float(pick.signal.score),
            new_flip_age=pick.signal.gap_age,
        )

    def approve_replacement(self, proposal_id: str, pick: "GapFillPick") -> bool:
        """Disabled — positions exit via stop/target (or time) only."""
        pending = self._load_pending()
        if pending:
            self._save_pending([])
        return False

    def run_daily(
        self,
        picks: List["GapFillPick"],
        screen_date: Optional[str] = None,
        approve: Optional[Callable[[ReplacementProposal], bool]] = None,
    ) -> dict:
        screen_date = screen_date or datetime.now().strftime("%Y-%m-%d")
        buy_picks: List["GapFillPick"] = []
        sell_picks: List["GapFillPick"] = []
        skipped_rules: List[dict] = []
        if self._load_pending():
            self._save_pending([])  # foreclosure disabled

        for pick in picks:
            side = gap_trade_side(pick.direction)
            if side == "SELL":
                sell_picks.append(pick)
                continue
            if not pick.is_long_candidate:
                continue
            ok, reason = pick_passes_long_entry(pick.signal, self.config)
            if ok:
                buy_picks.append(pick)
            else:
                skipped_rules.append({"symbol": pick.symbol, "reason": reason})

        report: dict = {
            "date": screen_date,
            "chart_timeframe": "1d",
            "screener_picks": len(buy_picks),
            "sell_signals": len(sell_picks),
            "skipped_rules": skipped_rules,
            "exits": [],
            "opened": [],
            "skipped_duplicate": [],
            "skipped_sector_cap": [],
            "proposals": [],
            "approved_replacements": [],
        }

        stored_sells = self.book.store_sell_signals(picks, screen_date=screen_date)
        report["stored_sell_signals"] = [s["ticker"] for s in stored_sells]

        exit_summary = self.book.evaluate_and_close_exits(as_of=screen_date)
        sell_closes = self.book.close_on_sell_signals(sell_picks, as_of=screen_date)
        report["exits"] = exit_summary.get("closed", []) + sell_closes
        report["signal_sell_closes"] = [e["ticker"] for e in sell_closes]

        open_count = self.book.open_count()
        sector_counts = self.book.sector_open_counts()

        for pick in buy_picks:
            if self.book.has_open_position(pick.symbol):
                self.book.touch_screen_date(pick.symbol, screen_date)
                report["skipped_duplicate"].append(pick.symbol)
                continue

            sector = pick.sector or (pick.signal.sector if pick.signal else None) or ""
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
