"""Virtual portfolio that paper-trades RS screen + Market Analyst BUY calls.

No real orders are ever placed. Opens use MA (or ATR fallback) stop/target.
Exits: stop → target → 20-day time. Sector cap and hard slot cap apply.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone, time as dt_time
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import yfinance as yf

from .exits import ExitAction, ExitReason, evaluate_bar_exits
from .sizing import compute_position_size, leg_rupee_pnl
from tradingagents.swing.exits import trading_days_between

logger = logging.getLogger(__name__)

_DEFAULT_HOME = os.path.join(os.path.expanduser("~"), ".tradingagents")

IST = timezone(timedelta(hours=5, minutes=30))
_NSE_OPEN = dt_time(9, 15)
_NSE_CLOSE = dt_time(15, 30)


def _next_execution(order_dt: datetime) -> datetime:
    """When a market order placed at ``order_dt`` would actually fill."""
    t = order_dt.timetz().replace(tzinfo=None)
    if order_dt.weekday() < 5 and _NSE_OPEN <= t <= _NSE_CLOSE:
        return order_dt
    if order_dt.weekday() < 5 and t < _NSE_OPEN:
        return order_dt.replace(hour=9, minute=15, second=0, microsecond=0)
    nxt = order_dt + timedelta(days=1)
    while nxt.weekday() >= 5:
        nxt += timedelta(days=1)
    return nxt.replace(hour=9, minute=15, second=0, microsecond=0)


class PaperBook:
    def __init__(self, config: Optional[dict] = None):
        cfg = config or {}
        path = cfg.get("paper_book_path") or os.getenv(
            "TRADINGAGENTS_PAPER_BOOK_PATH",
            os.path.join(_DEFAULT_HOME, "paper", "book.json"),
        )
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.config = cfg

        self.capital = float(cfg.get("desk_capital", cfg.get("paper_capital", 200_000.0)))
        self.max_positions = int(cfg.get("paper_max_positions", 20))
        self.max_per_sector = int(cfg.get("paper_max_per_sector", 4))
        self.holding_days = int(cfg.get("paper_holding_days", 20))
        self.benchmark = cfg.get("paper_benchmark", "^NSEI")

        self._state = self._load()
        self._backfill_sectors()

    def _load(self) -> dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except Exception as e:  # noqa: BLE001
                logger.warning("Could not read paper book (%s); starting fresh", e)
        return {"positions": []}

    def _save(self) -> None:
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

    def sector_open_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for p in self.positions:
            if p.get("status") == "open":
                sector = p.get("sector") or ""
                counts[sector] = counts.get(sector, 0) + 1
        return counts

    def _backfill_sectors(self) -> None:
        need = [
            p for p in self.positions
            if p.get("status") == "open" and (not p.get("sector") or p.get("sector") == "—")
        ]
        if not need:
            return
        try:
            from tradingagents.screening.universe import load_universe_metadata

            metadata = load_universe_metadata(
                csv_path=self.config.get("screen_universe_csv"),
                cache_dir=self.config.get("data_cache_dir"),
                allow_download=True,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("Could not backfill paper sectors (%s)", e)
            return
        changed = False
        for p in need:
            meta = metadata.get(p["ticker"], {})
            sector = meta.get("sector")
            if sector and sector != "—":
                p["sector"] = sector
                if meta.get("name"):
                    p["stock_name"] = meta["name"]
                changed = True
        if changed:
            self._save()

    def open_position(
        self,
        ticker: str,
        rating: str,
        entry_price: float,
        entry_date: str,
        signals: Optional[List[str]] = None,
        levels: Optional[dict] = None,
        sector: str = "",
        stock_name: str = "",
    ) -> Optional[dict]:
        """Record a simulated buy. Requires valid stop < entry < target."""
        if entry_price is None or entry_price <= 0:
            return None
        if self.has_open_position(ticker):
            return None
        if self.open_count() >= self.max_positions:
            return None

        levels = levels or {}
        stop = levels.get("stoploss")
        target = levels.get("target")
        try:
            stop_f = float(stop) if stop is not None else 0.0
            target_f = float(target) if target is not None else 0.0
        except (TypeError, ValueError):
            return None
        if stop_f <= 0 or target_f <= 0 or not (stop_f < entry_price < target_f):
            logger.warning(
                "Skip %s — invalid levels entry=%s stop=%s target=%s",
                ticker, entry_price, stop, target,
            )
            return None

        sector = sector or ""
        if self.sector_open_counts().get(sector, 0) >= self.max_per_sector:
            return None

        sizing = compute_position_size(self.capital, self.max_positions, entry_price)
        if int(sizing["shares"] or 0) < 1:
            return None

        stop_pct = levels.get("stop_pct")
        target_pct = levels.get("target_pct")
        if stop_pct is None:
            stop_pct = round(-100.0 * (entry_price - stop_f) / entry_price, 2)
        if target_pct is None:
            target_pct = round(100.0 * (target_f - entry_price) / entry_price, 2)

        order_dt = datetime.now(IST)
        exec_dt = _next_execution(order_dt)
        pos = {
            "ticker": ticker,
            "stock_name": stock_name or ticker.replace(".NS", "").replace(".BO", ""),
            "sector": sector or "—",
            "rating": rating,
            "signals": signals or [],
            "entry_date": entry_date,
            "order_time": order_dt.isoformat(timespec="minutes"),
            "execution_time": exec_dt.isoformat(timespec="minutes"),
            "execution_deferred": exec_dt > order_dt,
            "entry_price": round(float(entry_price), 2),
            "shares": sizing["shares"],
            "alloc": sizing["alloc"],
            "notional": sizing["notional"],
            "stoploss": round(stop_f, 2),
            "target": round(target_f, 2),
            "stop_pct": stop_pct,
            "target_pct": target_pct,
            "status": "open",
            "exit_date": None,
            "exit_price": None,
            "exit_reason": None,
            "raw_return": None,
            "alpha_return": None,
            "holding_days_actual": None,
            "rupee_pnl": None,
            "outcome": None,
        }
        self.positions.append(pos)
        self._save()
        return pos

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

    def _latest_close(self, symbol: str) -> Optional[float]:
        start = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
        end = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        df = self._history(symbol, start, end)
        if df is None or df.empty:
            return None
        return float(df["Close"].iloc[-1])

    def _alpha(self, entry_date: str, exit_date: str, raw: float) -> Optional[float]:
        end = (datetime.strptime(exit_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        bench = self._history(self.benchmark, entry_date, end)
        if bench is None or len(bench) < 2:
            return None
        bench_ret = (float(bench["Close"].iloc[-1]) - float(bench["Close"].iloc[0])) / float(
            bench["Close"].iloc[0]
        )
        return raw - bench_ret

    def _apply_exit(self, p: dict, action: ExitAction, history: pd.DataFrame) -> None:
        entry = float(p["entry_price"])
        raw = (action.exit_price - entry) / entry if entry else 0.0
        p["status"] = "closed"
        p["exit_price"] = action.exit_price
        p["exit_date"] = action.exit_date
        p["exit_reason"] = action.reason.value
        p["raw_return"] = round(raw, 4)
        p["rupee_pnl"] = leg_rupee_pnl(p["shares"], entry, action.exit_price, 100.0)
        alpha = self._alpha(p["entry_date"], action.exit_date, raw)
        p["alpha_return"] = round(alpha, 4) if alpha is not None else None
        p["holding_days_actual"] = trading_days_between(p["entry_date"], action.exit_date, history)
        p["outcome"] = "loss" if action.reason == ExitReason.STOP else (
            "success" if raw > 0 else "loss"
        )

    def mark_to_market(self, as_of: Optional[str] = None) -> dict:
        """Value opens; close on stop / target / time."""
        as_of = as_of or datetime.now().strftime("%Y-%m-%d")
        closed_now = 0
        unrealized = 0.0

        for p in list(self.positions):
            if p.get("status") != "open":
                continue
            # Skip same-day exit
            if p["entry_date"] >= as_of:
                price = self._latest_close(p["ticker"])
                if price is not None:
                    unrealized += (price - float(p["entry_price"])) * float(p["shares"])
                continue

            end = (datetime.strptime(as_of, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
            hist = self._history(p["ticker"], p["entry_date"], end)
            if hist is None or hist.empty:
                price = self._latest_close(p["ticker"])
                if price is not None:
                    unrealized += (price - float(p["entry_price"])) * float(p["shares"])
                continue

            closed = False
            for i in range(len(hist)):
                bar_date = hist.index[i].strftime("%Y-%m-%d")
                if bar_date <= p["entry_date"]:
                    continue
                if bar_date > as_of:
                    break
                action = evaluate_bar_exits(
                    p, hist.iloc[i], bar_date, self.holding_days, hist.iloc[: i + 1]
                )
                if action is not None:
                    self._apply_exit(p, action, hist.iloc[: i + 1])
                    closed_now += 1
                    closed = True
                    break

            if not closed:
                price = float(hist["Close"].iloc[-1])
                unrealized += (price - float(p["entry_price"])) * float(p["shares"])

        self._save()
        return {
            "closed_now": closed_now,
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
            wins = sum(1 for t in trades if (t.get("raw_return") or 0) > 0)
            avg_ret = sum(t.get("raw_return") or 0 for t in trades) / n
            alphas = [t["alpha_return"] for t in trades if t.get("alpha_return") is not None]
            avg_alpha = sum(alphas) / len(alphas) if alphas else None
            pnl = sum(
                t.get("rupee_pnl")
                if t.get("rupee_pnl") is not None
                else (float(t["exit_price"]) - float(t["entry_price"])) * float(t["shares"])
                for t in trades
                if t.get("exit_price") is not None
            )
            return {
                "trades": n,
                "win_rate": round(100 * wins / n, 1),
                "avg_return": round(100 * avg_ret, 2),
                "avg_alpha": round(100 * avg_alpha, 2) if avg_alpha is not None else None,
                "total_pnl": round(pnl, 2),
            }

        per_signal: Dict[str, dict] = {}
        signal_names = {s for p in closed for s in p.get("signals", [])}
        for name in sorted(signal_names):
            subset = [p for p in closed if name in p.get("signals", [])]
            per_signal[name] = _agg(subset)

        by_reason: Dict[str, dict] = {}
        for reason in (ExitReason.STOP.value, ExitReason.TARGET.value, ExitReason.TIME.value):
            subset = [p for p in closed if p.get("exit_reason") == reason]
            if subset:
                by_reason[reason] = _agg(subset)

        return {
            "overall": _agg(closed),
            "open_positions": len(open_),
            "closed_positions": len(closed),
            "per_signal": per_signal,
            "by_exit_reason": by_reason,
        }
