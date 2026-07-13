"""Tech Desk paper position book."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, TYPE_CHECKING

import pandas as pd
import yfinance as yf

from .exits import ExitAction, ExitReason, evaluate_bar_exits, zone_fill_price
from tradingagents.paper.sizing import (
    compute_position_size,
    ensure_sizing_fields,
    leg_rupee_pnl,
    skip_exit_for_entry_day,
    total_rupee_pnl_from_legs,
)
from tradingagents.swing.exits import trading_days_between

if TYPE_CHECKING:
    from .schemas import TechTradePlan

logger = logging.getLogger(__name__)

_DEFAULT_HOME = os.path.join(os.path.expanduser("~"), ".tradingagents")
STRATEGY_NAME = "tech_desk"


class TechDeskPositionBook:
    def __init__(self, config: Optional[dict] = None):
        cfg = config or {}
        self.config = cfg
        path = cfg.get("tech_desk_book_path") or os.getenv(
            "TRADINGAGENTS_TECH_DESK_BOOK_PATH",
            os.path.join(_DEFAULT_HOME, "tech_desk", "positions.json"),
        )
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        pending = cfg.get("tech_desk_pending_path") or os.path.join(
            _DEFAULT_HOME, "tech_desk", "pending_entries.json"
        )
        self.pending_path = Path(pending).expanduser()
        self.pending_path.parent.mkdir(parents=True, exist_ok=True)
        dismissed = cfg.get("tech_desk_pending_dismissed_path") or os.path.join(
            _DEFAULT_HOME, "tech_desk", "pending_dismissed.json"
        )
        self.dismissed_path = Path(dismissed).expanduser()
        self.dismissed_path.parent.mkdir(parents=True, exist_ok=True)
        self.holding_days = int(cfg.get("tech_desk_holding_days", 20))
        self.max_positions = int(cfg.get("tech_desk_max_positions", 10))
        self.min_confidence = int(cfg.get("tech_desk_min_confidence", 60))
        self.desk_capital = float(cfg.get("desk_capital", 100_000.0))
        self.benchmark = cfg.get("paper_benchmark", "^NSEI")
        self._state = self._load()
        self._migrate_positions()

    def _migrate_positions(self) -> None:
        changed = False
        for p in self.positions:
            if self._ensure_position_fields(p):
                changed = True
        if changed:
            self._save()

    def _ensure_position_fields(self, p: dict) -> bool:
        changed = False
        defaults = {
            "remaining_pct": 100.0 if p.get("status") == "open" else 0.0,
            "phase": "initial",
            "trailing_stop": p.get("stop_loss"),
            "partial_exits": [],
        }
        for key, val in defaults.items():
            if key not in p or p[key] is None:
                p[key] = val
                changed = True
        if ensure_sizing_fields(p, self.desk_capital, self.max_positions):
            changed = True
        return changed

    def _load(self) -> dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except Exception as e:  # noqa: BLE001
                logger.warning("Could not read Tech Desk book (%s); starting fresh", e)
        return {"strategy": STRATEGY_NAME, "positions": []}

    def _save(self) -> None:
        self._state["strategy"] = STRATEGY_NAME
        self._state["updated_at"] = datetime.now().isoformat(timespec="seconds")
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._state, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def _load_pending(self) -> List[dict]:
        if not self.pending_path.exists():
            return []
        try:
            return json.loads(self.pending_path.read_text(encoding="utf-8")).get("pending", [])
        except Exception:  # noqa: BLE001
            return []

    def _save_pending(self, pending: List[dict]) -> None:
        tmp = self.pending_path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"pending": pending}, indent=2), encoding="utf-8")
        tmp.replace(self.pending_path)

    def _load_dismissed(self) -> List[dict]:
        if not self.dismissed_path.exists():
            return []
        try:
            return json.loads(self.dismissed_path.read_text(encoding="utf-8")).get("dismissed", [])
        except Exception:  # noqa: BLE001
            return []

    def _save_dismissed(self, dismissed: List[dict]) -> None:
        tmp = self.dismissed_path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"dismissed": dismissed}, indent=2), encoding="utf-8")
        tmp.replace(self.dismissed_path)

    def is_pending_dismissed(self, ticker: str, report_date: Optional[str] = None) -> Optional[str]:
        """Return dismiss reason if ticker must not be re-queued."""
        for row in self._load_dismissed():
            if row.get("ticker") != ticker:
                continue
            dismissed_report = row.get("report_date") or ""
            if not report_date or not dismissed_report:
                return str(row.get("reason") or "dismissed")
            if report_date <= dismissed_report:
                return str(row.get("reason") or "dismissed")
        return None

    def record_pending_dismissal(
        self,
        ticker: str,
        reason: str,
        *,
        report_date: Optional[str] = None,
        plan_date: Optional[str] = None,
    ) -> None:
        dismissed = [d for d in self._load_dismissed() if d.get("ticker") != ticker]
        dismissed.append(
            {
                "ticker": ticker,
                "reason": reason,
                "report_date": report_date,
                "plan_date": plan_date,
                "dismissed_at": datetime.now().isoformat(timespec="seconds"),
            }
        )
        self._save_dismissed(dismissed)

    def dismiss_pending(
        self,
        ticker: str,
        reason: str,
        *,
        report_date: Optional[str] = None,
        plan_date: Optional[str] = None,
    ) -> None:
        self.record_pending_dismissal(
            ticker,
            reason,
            report_date=report_date,
            plan_date=plan_date,
        )
        self.remove_pending(ticker)

    @property
    def positions(self) -> List[dict]:
        return self._state["positions"]

    def open_count(self) -> int:
        return sum(1 for p in self.positions if p.get("status") == "open")

    def has_open_position(self, ticker: str) -> bool:
        return any(p["ticker"] == ticker and p.get("status") == "open" for p in self.positions)

    def pending_entries(self) -> List[dict]:
        return self._load_pending()

    def validate_pending_plan(
        self,
        plan: "TechTradePlan",
        current_price: Optional[float] = None,
    ) -> Optional[str]:
        """Return an error string if the pending plan fails validation."""
        if plan.confidence < self.min_confidence:
            return f"confidence {plan.confidence} < min {self.min_confidence}"
        if plan.stop_loss <= 0:
            return "stop_loss must be positive"
        if plan.target_1 <= 0:
            return "target_1 must be positive"

        zone_low = plan.zone_low
        zone_high = plan.zone_high
        if zone_low is None or zone_high is None:
            return "missing zone bounds"
        if zone_low <= 0 or zone_high <= zone_low:
            return "invalid zone bounds"
        if plan.stop_loss >= zone_low:
            return "stop must be below zone_low for long entries"
        if plan.target_1 <= zone_high:
            return "target_1 must be above zone_high"

        if current_price is not None and current_price > 0:
            if zone_low > current_price * 1.03:
                return "zone_low above current price (not a pullback entry)"
            if zone_high < current_price * 0.85:
                return "zone too far below current price"

        return None

    def add_pending_entry(
        self,
        plan: "TechTradePlan",
        plan_date: str,
        *,
        report_path: Optional[str] = None,
        report_date: Optional[str] = None,
        current_price: Optional[float] = None,
    ) -> Optional[dict]:
        blocked = self.is_pending_dismissed(plan.ticker, report_date)
        if blocked:
            logger.info("Reject pending %s — dismissed (%s)", plan.ticker, blocked)
            return None
        err = self.validate_pending_plan(plan, current_price)
        if err:
            logger.info("Reject pending %s — %s", plan.ticker, err)
            return None
        pending = self._load_pending()
        pending = [p for p in pending if p.get("ticker") != plan.ticker]
        row = {
            "ticker": plan.ticker,
            "entry_type": plan.entry_type.value,
            "zone_low": plan.zone_low,
            "zone_high": plan.zone_high,
            "stop_loss": plan.stop_loss,
            "target_1": plan.target_1,
            "target_2": plan.target_2,
            "holding_days": plan.holding_days,
            "confidence": plan.confidence,
            "bias": plan.bias.value,
            "invalidation": plan.invalidation,
            "rationale": plan.rationale,
            "plan_date": plan_date,
            "report_path": report_path,
            "report_date": report_date,
            "added_at": datetime.now().isoformat(timespec="seconds"),
            "peak_since_added": current_price,
            "peak_date": plan_date,
            "setup_status": "active",
        }
        pending.append(row)
        self._save_pending(pending)
        return row

    def remove_pending(self, ticker: str) -> None:
        pending = [p for p in self._load_pending() if p.get("ticker") != ticker]
        self._save_pending(pending)

    def open_from_plan(
        self,
        plan: "TechTradePlan",
        entry_price: float,
        screen_date: str,
        *,
        report_path: Optional[str] = None,
        report_date: Optional[str] = None,
    ) -> Optional[dict]:
        if plan.confidence < self.min_confidence:
            logger.info("Skip %s — confidence %s < min %s", plan.ticker, plan.confidence, self.min_confidence)
            return None
        if self.has_open_position(plan.ticker):
            return None
        if self.open_count() >= self.max_positions:
            return None
        if entry_price <= 0 or plan.stop_loss <= 0 or plan.stop_loss >= entry_price:
            logger.warning("Invalid levels for %s entry=%s stop=%s", plan.ticker, entry_price, plan.stop_loss)
            return None
        if plan.target_1 <= entry_price:
            logger.warning("Invalid target_1 for %s", plan.ticker)
            return None

        sizing = compute_position_size(self.desk_capital, self.max_positions, entry_price)
        stop_pct = round(-100.0 * (entry_price - plan.stop_loss) / entry_price, 2)
        target_1_pct = round(100.0 * (plan.target_1 - entry_price) / entry_price, 2)
        holding = plan.holding_days if plan.holding_days is not None else self.holding_days

        row = {
            "strategy": STRATEGY_NAME,
            "ticker": plan.ticker,
            "screen_date": screen_date,
            "last_screen_date": screen_date,
            "entry_price": round(entry_price, 2),
            "shares": sizing["shares"],
            "alloc": sizing["alloc"],
            "notional": sizing["notional"],
            "stop_loss": round(plan.stop_loss, 2),
            "stop_loss_pct": stop_pct,
            "trailing_stop": round(plan.stop_loss, 2),
            "target_1": round(plan.target_1, 2),
            "target_1_pct": target_1_pct,
            "target_2": round(plan.target_2, 2) if plan.target_2 is not None else None,
            "holding_days": holding,
            "confidence": plan.confidence,
            "bias": plan.bias.value,
            "invalidation": plan.invalidation,
            "rationale": plan.rationale,
            "report_path": report_path,
            "report_date": report_date,
            "entry_type": plan.entry_type.value,
            "phase": "initial",
            "remaining_pct": 100.0,
            "partial_exits": [],
            "status": "open",
            "exit_date": None,
            "exit_price": None,
            "exit_reason": None,
            "outcome": None,
            "raw_return": None,
            "alpha_return": None,
            "trading_days_held": None,
        }
        self.positions.append(row)
        self._save()
        self.remove_pending(plan.ticker)
        return row

    def _history(self, symbol: str, start: str, end: str) -> Optional[pd.DataFrame]:
        try:
            df = yf.Ticker(symbol).history(start=start, end=end, interval="1d")
            if df is None or df.empty:
                return None
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            return df
        except Exception as e:  # noqa: BLE001
            logger.warning("price fetch failed for %s (%s)", symbol, e)
            return None

    def latest_price(self, symbol: str) -> Optional[float]:
        start = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
        end = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        df = self._history(symbol, start, end)
        if df is None or df.empty:
            return None
        return float(df["Close"].iloc[-1])

    def evaluate_and_close_exits(self, as_of: Optional[str] = None) -> dict:
        as_of = as_of or datetime.now().strftime("%Y-%m-%d")
        events: List[dict] = []

        for p in list(self.positions):
            if p.get("status") != "open":
                continue
            self._ensure_position_fields(p)
            if skip_exit_for_entry_day(p["screen_date"], as_of):
                continue

            start = p["screen_date"]
            end = (datetime.strptime(as_of, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
            hist = self._history(p["ticker"], start, end)
            if hist is None or hist.empty:
                continue

            last = hist.iloc[-1]
            bar_date = hist.index[-1].strftime("%Y-%m-%d")
            holding = int(p.get("holding_days") or self.holding_days)

            actions = evaluate_bar_exits(p, last, bar_date, holding, hist)
            for action in actions:
                events.append(self._apply_action(p, action, hist))

        self._save()
        return {"closed": events, "open_positions": self.open_count()}

    def evaluate_pending_lifecycle(self, as_of: Optional[str] = None) -> dict:
        """Update peaks and remove invalidated/expired/exhausted pending entries."""
        from .pending_lifecycle import (
            history_from_plan_date,
            is_pending_expired,
            is_pending_invalidated,
            is_setup_exhausted,
            update_pending_peak,
        )

        as_of = as_of or datetime.now().strftime("%Y-%m-%d")
        pending = self._load_pending()
        if not pending:
            return {"removed": [], "updated": 0}

        remaining: List[dict] = []
        removed: List[dict] = []

        for entry in pending:
            ticker = entry["ticker"]
            plan_date = entry.get("plan_date") or as_of
            start = plan_date
            end = (datetime.strptime(as_of, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
            hist = self._history(ticker, start, end)
            if hist is not None and not hist.empty:
                entry = update_pending_peak(entry, hist)

            if is_pending_expired(entry, as_of, self.config):
                removed.append({"ticker": ticker, "reason": "expired"})
                self.record_pending_dismissal(
                    ticker,
                    "expired",
                    report_date=entry.get("report_date"),
                    plan_date=plan_date,
                )
                continue

            hist_slice = history_from_plan_date(hist, plan_date, as_of)
            hist_for_rules = hist_slice if hist_slice is not None else hist
            if hist_for_rules is None:
                hist_for_rules = pd.DataFrame()
            invalidated, inv_reason = is_pending_invalidated(entry, hist_for_rules, self.config)
            if invalidated:
                removed.append({"ticker": ticker, "reason": inv_reason})
                self.record_pending_dismissal(
                    ticker,
                    inv_reason,
                    report_date=entry.get("report_date"),
                    plan_date=plan_date,
                )
                continue

            exhausted, ex_reason = is_setup_exhausted(entry, hist_for_rules, self.config)
            if exhausted:
                removed.append({"ticker": ticker, "reason": ex_reason})
                self.record_pending_dismissal(
                    ticker,
                    ex_reason,
                    report_date=entry.get("report_date"),
                    plan_date=plan_date,
                )
                continue

            remaining.append(entry)

        if len(remaining) != len(pending):
            self._save_pending(remaining)
        elif remaining:
            self._save_pending(remaining)

        return {"removed": removed, "updated": len(remaining)}

    def evaluate_pending_fills(self, as_of: Optional[str] = None) -> List[dict]:
        as_of = as_of or datetime.now().strftime("%Y-%m-%d")
        self.evaluate_pending_lifecycle(as_of=as_of)
        filled: List[dict] = []
        pending = self._load_pending()
        if not pending:
            return filled

        from .pending_lifecycle import history_from_plan_date, is_setup_exhausted

        remaining_pending: List[dict] = []
        for entry in pending:
            ticker = entry["ticker"]
            if self.has_open_position(ticker):
                continue
            if self.open_count() >= self.max_positions:
                remaining_pending.append(entry)
                continue

            zone_low = float(entry.get("zone_low") or 0)
            zone_high = float(entry.get("zone_high") or 0)
            if zone_low <= 0 or zone_high <= zone_low:
                continue

            plan_date = entry.get("plan_date") or as_of
            start = plan_date
            end = (datetime.strptime(as_of, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
            hist = self._history(ticker, start, end)
            if hist is None or hist.empty:
                remaining_pending.append(entry)
                continue

            hist_slice = history_from_plan_date(hist, plan_date, as_of)
            hist_for_rules = hist_slice if hist_slice is not None else hist
            exhausted, ex_reason = is_setup_exhausted(entry, hist_for_rules, self.config)
            if exhausted:
                self.dismiss_pending(
                    ticker,
                    ex_reason,
                    report_date=entry.get("report_date"),
                    plan_date=plan_date,
                )
                continue

            last = hist.iloc[-1]
            fill = zone_fill_price(last, zone_low, zone_high)
            if fill is None:
                remaining_pending.append(entry)
                continue

            from .schemas import Bias, EntryType, PlanAction, TechTradePlan

            plan = TechTradePlan(
                ticker=ticker,
                action=PlanAction.OPEN,
                entry_type=EntryType.LIMIT_ZONE,
                zone_low=zone_low,
                zone_high=zone_high,
                stop_loss=float(entry["stop_loss"]),
                target_1=float(entry["target_1"]),
                target_2=entry.get("target_2"),
                holding_days=entry.get("holding_days"),
                confidence=int(entry.get("confidence") or 0),
                bias=Bias(entry.get("bias", "neutral")),
                invalidation=str(entry.get("invalidation") or ""),
                rationale=str(entry.get("rationale") or ""),
            )
            pos = self.open_from_plan(
                plan,
                fill,
                as_of,
                report_path=entry.get("report_path"),
                report_date=entry.get("report_date"),
            )
            if pos:
                filled.append({"ticker": ticker, "fill_price": fill, "position": pos})
            else:
                remaining_pending.append(entry)

        self._save_pending(remaining_pending)
        return filled

    def _apply_action(self, p: dict, action: ExitAction, history: pd.DataFrame) -> dict:
        entry = float(p["entry_price"])
        shares = float(p.get("shares") or 0)
        leg_return = (action.exit_price - entry) / entry if entry else 0.0
        leg_rupee = leg_rupee_pnl(shares, entry, action.exit_price, action.exit_pct)
        event = {
            "ticker": p["ticker"],
            "reason": action.reason.value,
            "exit_price": action.exit_price,
            "exit_date": action.exit_date,
            "exit_pct": action.exit_pct,
            "leg_return": round(leg_return, 4),
            "leg_rupee_pnl": leg_rupee,
            "partial": action.partial,
        }

        p["partial_exits"].append({
            "date": action.exit_date,
            "price": action.exit_price,
            "pct": action.exit_pct,
            "reason": action.reason.value,
            "return": round(leg_return, 4),
            "rupee_pnl": leg_rupee,
        })
        p["status"] = "closed"
        p["remaining_pct"] = 0.0
        p["exit_price"] = action.exit_price
        p["exit_date"] = action.exit_date
        p["exit_reason"] = action.reason.value
        p["raw_return"] = round(leg_return, 4)
        p["rupee_pnl"] = total_rupee_pnl_from_legs(p["partial_exits"])
        alpha = self._alpha(p["screen_date"], action.exit_date, leg_return)
        p["alpha_return"] = round(alpha, 4) if alpha is not None else None
        p["trading_days_held"] = trading_days_between(p["screen_date"], action.exit_date, history)
        p["outcome"] = "success" if leg_return > 0 else "loss"
        event["raw_return"] = p["raw_return"]
        event["rupee_pnl"] = p["rupee_pnl"]
        event["outcome"] = p["outcome"]
        self._append_closed_history(p)
        return event

    def _closed_history_path(self) -> Path:
        custom = self.config.get("tech_desk_closed_history_path")
        if custom:
            return Path(custom).expanduser()
        return self.path.parent / "closed_history.json"

    def _append_closed_history(self, position: dict) -> None:
        """Append-only archive so closed trades survive book resets."""
        path = self._closed_history_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        state: dict = {"trades": []}
        if path.exists():
            try:
                state = json.loads(path.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                state = {"trades": []}
        trades: List[dict] = state.setdefault("trades", [])
        key = (
            position.get("ticker"),
            position.get("screen_date"),
            position.get("exit_date"),
        )
        if any(
            t.get("ticker") == key[0]
            and t.get("screen_date") == key[1]
            and t.get("exit_date") == key[2]
            for t in trades
        ):
            return
        snapshot = dict(position)
        snapshot["archived_at"] = datetime.now().isoformat(timespec="seconds")
        trades.append(snapshot)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
        tmp.replace(path)

    def close_position(
        self,
        ticker: str,
        exit_price: float,
        exit_date: str,
        reason: str,
    ) -> bool:
        for p in self.positions:
            if p["ticker"] == ticker and p.get("status") == "open":
                self._ensure_position_fields(p)
                action = ExitAction(
                    ticker=ticker,
                    reason=ExitReason(reason)
                    if reason in {e.value for e in ExitReason}
                    else ExitReason.FORECLOSURE,
                    exit_price=exit_price,
                    exit_date=exit_date,
                    exit_pct=float(p.get("remaining_pct", 100.0)),
                )
                hist = self._history(
                    p["ticker"],
                    p["screen_date"],
                    (datetime.strptime(exit_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d"),
                )
                self._apply_action(p, action, hist)
                self._save()
                return True
        return False

    def _alpha(self, entry_date: str, exit_date: str, raw: float) -> Optional[float]:
        end = (datetime.strptime(exit_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        bench = self._history(self.benchmark, entry_date, end)
        if bench is None or len(bench) < 2:
            return None
        bench_ret = (float(bench["Close"].iloc[-1]) - float(bench["Close"].iloc[0])) / float(
            bench["Close"].iloc[0]
        )
        return raw - bench_ret

    def _r_multiple(self, trade: dict) -> Optional[float]:
        entry = float(trade.get("entry_price") or 0)
        stop = float(trade.get("stop_loss") or trade.get("initial_stop_loss") or 0)
        exit_p = trade.get("exit_price")
        if exit_p is None or entry <= 0 or stop <= 0 or entry <= stop:
            return None
        risk = entry - stop
        return round((float(exit_p) - entry) / risk, 2)

    def stats(self) -> dict:
        closed = [p for p in self.positions if p.get("status") == "closed"]
        open_ = [p for p in self.positions if p.get("status") == "open"]

        def _agg(trades: List[dict]) -> dict:
            n = len(trades)
            if n == 0:
                return {
                    "trades": 0,
                    "win_rate": None,
                    "avg_return": None,
                    "avg_alpha": None,
                    "avg_r": None,
                    "total_pnl": 0.0,
                }
            wins = sum(1 for t in trades if t.get("outcome") == "success")
            avg_ret = sum(t.get("raw_return") or 0 for t in trades) / n
            alphas = [t["alpha_return"] for t in trades if t.get("alpha_return") is not None]
            pnl = sum(t.get("rupee_pnl") or 0 for t in trades)
            rs = [r for r in (self._r_multiple(t) for t in trades) if r is not None]
            return {
                "trades": n,
                "win_rate": round(100 * wins / n, 1),
                "avg_return": round(100 * avg_ret, 2),
                "avg_alpha": round(100 * sum(alphas) / len(alphas), 2) if alphas else None,
                "avg_r": round(sum(rs) / len(rs), 2) if rs else None,
                "total_pnl": round(pnl, 2),
            }

        by_reason: Dict[str, dict] = {}
        for reason in (
            ExitReason.STOP.value,
            ExitReason.TARGET_1.value,
            ExitReason.TARGET_2.value,
            ExitReason.TIME.value,
            ExitReason.FORECLOSURE.value,
            ExitReason.REVIEW_CLOSE.value,
        ):
            subset = [p for p in closed if p.get("exit_reason") == reason]
            if subset:
                by_reason[reason] = _agg(subset)

        return {
            "overall": _agg(closed),
            "by_exit_reason": by_reason,
            "open_positions": len(open_),
            "closed_positions": len(closed),
            "pending_entries": len(self._load_pending()),
        }
