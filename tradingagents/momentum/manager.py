"""Portfolio paper-trade manager for momentum_trade_positional."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Optional, TYPE_CHECKING

from .book import MomentumPositionBook
from tradingagents.swing.exits import ExitReason

if TYPE_CHECKING:
    from tradingagents.screening.momentum_screener import MomentumPick

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
    new_volume_ratio: float
    new_rsi: float
    new_adx: float
    approved: Optional[bool] = None


class MomentumPaperTradeManager:
    def __init__(self, config: Optional[dict] = None):
        cfg = config or {}
        self.config = cfg
        self.book = MomentumPositionBook(cfg)
        self.max_positions = int(cfg.get("momentum_max_positions", 20))
        momentum_dir = Path(
            cfg.get("momentum_book_path", os.path.join(_DEFAULT_HOME, "momentum", "positions.json"))
        ).parent
        self.pending_path = Path(cfg.get("momentum_pending_path") or momentum_dir / "pending_replacements.json")
        self.daily_dir = Path(cfg.get("momentum_daily_dir") or momentum_dir / "daily")
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
            s -= float(p.get("volume_ratio_5_20") or 0)
            return s

        return min(open_positions, key=score)

    def _proposal_id(self) -> str:
        return datetime.now().strftime("%Y%m%d%H%M%S%f")

    def propose_replacement(self, pick: "MomentumPick", today_tickers: set[str]) -> ReplacementProposal:
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
            new_volume_ratio=pick.volume_ratio_5_20,
            new_rsi=pick.rsi,
            new_adx=pick.adx,
        )

    def approve_replacement(self, proposal_id: str, pick: "MomentumPick") -> bool:
        pending = self._load_pending()
        match = next((p for p in pending if p["id"] == proposal_id and not p.get("approved")), None)
        if match is None:
            return False
        price = self.book.latest_price(match["close_ticker"])
        if price is None:
            return False
        screen_date = datetime.now().strftime("%Y-%m-%d")
        self.book.close_position(
            match["close_ticker"],
            exit_price=price,
            exit_date=screen_date,
            reason=ExitReason.FORECLOSURE.value,
        )
        self.book.open_position(pick, screen_date)
        match["approved"] = True
        self._save_pending(pending)
        return True

    def run_daily(
        self,
        picks: List["MomentumPick"],
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
            "proposals": [],
            "approved_replacements": [],
        }

        exit_summary = self.book.evaluate_and_close_exits(as_of=screen_date)
        report["exits"] = exit_summary.get("closed", [])

        today_tickers = {p.symbol for p in picks}
        open_count = self.book.open_count()

        for pick in picks:
            if self.book.has_open_position(pick.symbol):
                self.book.touch_screen_date(pick.symbol, screen_date)
                report["skipped_duplicate"].append(pick.symbol)
                continue

            if open_count < self.max_positions:
                pos = self.book.open_position(pick, screen_date)
                if pos:
                    report["opened"].append(pick.symbol)
                    open_count += 1
                continue

            pending = self._load_pending()
            if any(
                not p.get("approved") and p.get("new_ticker") == pick.symbol
                for p in pending
            ):
                continue

            proposal = self.propose_replacement(pick, today_tickers)
            report["proposals"].append(asdict(proposal))

            if approve and approve(proposal):
                price = self.book.latest_price(proposal.close_ticker)
                if price is not None:
                    self.book.close_position(
                        proposal.close_ticker,
                        exit_price=price,
                        exit_date=screen_date,
                        reason=ExitReason.FORECLOSURE.value,
                    )
                    self.book.open_position(pick, screen_date)
                    report["approved_replacements"].append({
                        "closed": proposal.close_ticker,
                        "opened": pick.symbol,
                    })
                    proposal.approved = True

            pending = self._load_pending()
            pending.append(asdict(proposal))
            self._save_pending(pending)

        report["open_positions"] = self.book.open_count()
        report["stats"] = self.book.stats()

        out = self.daily_dir / f"{screen_date}.json"
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report

    def latest_daily_report(self) -> Optional[dict]:
        files = sorted(self.daily_dir.glob("*.json"), reverse=True)
        if not files:
            return None
        return json.loads(files[0].read_text(encoding="utf-8"))
