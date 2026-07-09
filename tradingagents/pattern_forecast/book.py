"""Pattern Forecast paper position book — 5-day target, mandatory stop loss."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, TYPE_CHECKING

import pandas as pd
import yfinance as yf

from .exits import ExitAction, ExitReason, evaluate_bar_exits
from tradingagents.paper.sizing import (
    compute_position_size,
    ensure_sizing_fields,
    leg_rupee_pnl,
    skip_exit_for_entry_day,
    total_rupee_pnl_from_legs,
)
from tradingagents.swing.exits import trading_days_between

if TYPE_CHECKING:
    from tradingagents.screening.pattern_forecast_screener import PatternForecastPick

logger = logging.getLogger(__name__)

_DEFAULT_HOME = os.path.join(os.path.expanduser("~"), ".tradingagents")
STRATEGY_NAME = "pattern_forecast"


class PatternForecastPositionBook:
    def __init__(self, config: Optional[dict] = None):
        cfg = config or {}
        self.config = cfg
        path = cfg.get("pattern_forecast_book_path") or os.getenv(
            "TRADINGAGENTS_PATTERN_FORECAST_BOOK_PATH",
            os.path.join(_DEFAULT_HOME, "pattern_forecast", "positions.json"),
        )
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.holding_days = int(cfg.get("pattern_forecast_holding_days", 5))
        self.max_positions = int(cfg.get("pattern_forecast_max_positions", 10))
        self.desk_capital = float(cfg.get("desk_capital", 100_000.0))
        self.benchmark = cfg.get("paper_benchmark", "^NSEI")
        self.stop_on_close_only = bool(cfg.get("pattern_forecast_stop_on_close_only", False))
        self.breakeven_trigger_pct = float(cfg.get("pattern_forecast_breakeven_trigger_pct", 0.0))
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
                logger.warning("Could not read Pattern Forecast book (%s); starting fresh", e)
        return {"strategy": STRATEGY_NAME, "positions": []}

    def _save(self) -> None:
        self._state["strategy"] = STRATEGY_NAME
        self._state["updated_at"] = datetime.now().isoformat(timespec="seconds")
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._state, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    @property
    def positions(self) -> List[dict]:
        return self._state["positions"]

    def open_count(self) -> int:
        return sum(1 for p in self.positions if p.get("status") == "open")

    def has_open_position(self, ticker: str) -> bool:
        return any(p["ticker"] == ticker and p.get("status") == "open" for p in self.positions)

    def touch_screen_date(self, ticker: str, screen_date: str) -> None:
        for p in self.positions:
            if p["ticker"] == ticker and p.get("status") == "open":
                p["last_screen_date"] = screen_date
        self._save()

    def open_position(self, pick: "PatternForecastPick", screen_date: str) -> Optional[dict]:
        if pick.direction != "UP":
            return None
        if self.has_open_position(pick.symbol):
            return None
        if self.open_count() >= self.max_positions:
            return None
        row = self._pick_to_position(pick, screen_date)
        if row is None:
            return None
        self.positions.append(row)
        self._save()
        return row

    def save_picks(self, picks: List["PatternForecastPick"], screen_date: Optional[str] = None) -> List[dict]:
        screen_date = screen_date or datetime.now().strftime("%Y-%m-%d")
        saved: List[dict] = []
        for pick in picks:
            if pick.direction != "UP":
                continue
            if self.has_open_position(pick.symbol):
                self.touch_screen_date(pick.symbol, screen_date)
                saved.append(
                    next(p for p in self.positions if p["ticker"] == pick.symbol and p["status"] == "open")
                )
            else:
                pos = self.open_position(pick, screen_date)
                if pos:
                    saved.append(pos)
        return saved

    def _pick_to_position(self, pick: "PatternForecastPick", screen_date: str) -> Optional[dict]:
        sig = pick.signal
        entry = float(sig.close)
        stop = float(sig.stop_loss)
        target = float(sig.projected_max_high_5d)

        if stop <= 0 or stop >= entry:
            logger.warning("Invalid mandatory SL for %s (entry=%s stop=%s)", pick.symbol, entry, stop)
            return None
        if target <= entry:
            logger.warning("Invalid 5d target for %s (entry=%s target=%s)", pick.symbol, entry, target)
            return None

        stop_pct = round(-100.0 * (entry - stop) / entry, 2)
        target_pct = round(100.0 * (target - entry) / entry, 2)
        proj_close_pct = round(float(sig.projected_move_pct), 2)
        entry_price = round(entry, 2)
        sizing = compute_position_size(self.desk_capital, self.max_positions, entry_price)

        return {
            "strategy": STRATEGY_NAME,
            "ticker": pick.symbol,
            "stock_name": sig.stock_name or pick.stock_name or pick.symbol.replace(".NS", ""),
            "sector": sig.sector or pick.sector or "—",
            "screen_date": screen_date,
            "last_screen_date": screen_date,
            "entry_price": entry_price,
            "shares": sizing["shares"],
            "alloc": sizing["alloc"],
            "notional": sizing["notional"],
            "stop_loss": round(stop, 2),
            "stop_loss_pct": stop_pct,
            "target_max": round(target, 2),
            "target_max_pct": target_pct,
            "projected_close_5d": sig.projected_close_5d,
            "projected_close_pct": proj_close_pct,
            "probability": sig.probability,
            "correlation": sig.correlation,
            "composite_score": sig.composite_score,
            "risk_reward": sig.risk_reward,
            "hist_fwd_return_pct": sig.hist_fwd_return_pct,
            "analogue_end_date": sig.analogue_end_date,
            "remark": sig.remark,
            "direction": sig.direction,
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

            actions = evaluate_bar_exits(
                p,
                last,
                bar_date,
                self.holding_days,
                hist,
                stop_on_close_only=self.stop_on_close_only,
                breakeven_trigger_pct=self.breakeven_trigger_pct,
            )
            for action in actions:
                events.append(self._apply_action(p, action, hist))

        self._save()
        return {"closed": events, "open_positions": self.open_count()}

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
        p["outcome"] = self._outcome_for_reason(action.reason, leg_return)
        event["raw_return"] = p["raw_return"]
        event["rupee_pnl"] = p["rupee_pnl"]
        event["outcome"] = p["outcome"]
        return event

    def _outcome_for_reason(self, reason: ExitReason, ret: float) -> str:
        if reason == ExitReason.STOP:
            return "loss"
        return "success" if ret > 0 else "loss"

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
                    reason=ExitReason(reason) if reason in {e.value for e in ExitReason} else ExitReason.FORECLOSURE,
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

    def mark_to_market(self) -> dict:
        summary = self.evaluate_and_close_exits()
        unrealized = 0.0
        for p in self.positions:
            if p.get("status") != "open":
                continue
            price = self.latest_price(p["ticker"])
            if price is not None:
                rem = float(p.get("remaining_pct", 100.0)) / 100.0
                shares = float(p.get("shares") or 0)
                unrealized += (price - float(p["entry_price"])) * shares * rem
        return {
            "closed_now": len(summary.get("closed", [])),
            "unrealized_pnl": round(unrealized, 2),
            "open_positions": self.open_count(),
        }

    def stats(self) -> dict:
        closed = [p for p in self.positions if p.get("status") == "closed"]
        open_ = [p for p in self.positions if p.get("status") == "open"]

        def _agg(trades: List[dict]) -> dict:
            n = len(trades)
            if n == 0:
                return {"trades": 0, "win_rate": None, "avg_return": None,
                        "avg_alpha": None, "total_pnl": 0.0}
            wins = sum(1 for t in trades if t.get("outcome") == "success")
            avg_ret = sum(t.get("raw_return") or 0 for t in trades) / n
            alphas = [t["alpha_return"] for t in trades if t.get("alpha_return") is not None]
            pnl = sum(t.get("rupee_pnl") or 0 for t in trades)
            return {
                "trades": n,
                "win_rate": round(100 * wins / n, 1),
                "avg_return": round(100 * avg_ret, 2),
                "avg_alpha": round(100 * sum(alphas) / len(alphas), 2) if alphas else None,
                "total_pnl": round(pnl, 2),
            }

        by_reason: Dict[str, dict] = {}
        for reason in (ExitReason.STOP.value, ExitReason.TARGET.value, ExitReason.TIME.value):
            subset = [p for p in closed if p.get("exit_reason") == reason]
            if subset:
                by_reason[reason] = _agg(subset)

        return {
            "overall": _agg(closed),
            "by_exit_reason": by_reason,
            "open_positions": len(open_),
            "closed_positions": len(closed),
        }
