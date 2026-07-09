"""Virtual portfolio that paper-trades the screener's bullish calls.

No real orders are ever placed. When the analysis pipeline rates a screened
stock bullish, :meth:`PaperBook.open_position` records a simulated buy at the
latest close. :meth:`PaperBook.mark_to_market` later fetches prices to value
open positions and auto-closes any that have reached their holding period,
scoring each closed trade's return and its alpha versus the Nifty benchmark.

The point is reliability measurement: :meth:`PaperBook.stats` reports win
rate, average return, and average alpha overall *and per technical signal*,
so we can learn which patterns actually predict winners.

State lives in a single JSON file (default ``~/.tradingagents/paper/book.json``)
written atomically.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone, time as dt_time
from pathlib import Path
from typing import Dict, List, Optional

import yfinance as yf

from .sizing import compute_position_size, leg_rupee_pnl

logger = logging.getLogger(__name__)

_DEFAULT_HOME = os.path.join(os.path.expanduser("~"), ".tradingagents")

# NSE regular session, IST (India has no DST so a fixed offset is safe).
IST = timezone(timedelta(hours=5, minutes=30))
_NSE_OPEN = dt_time(9, 15)
_NSE_CLOSE = dt_time(15, 30)


def _next_execution(order_dt: datetime) -> datetime:
    """When a market order placed at ``order_dt`` would actually fill.

    During the NSE session it fills immediately; otherwise it fills at the next
    session's open (09:15 IST the next trading day). Holidays are not modelled,
    so a holiday fill time may be a day early -- close enough for paper trades.
    """
    t = order_dt.timetz().replace(tzinfo=None)
    if order_dt.weekday() < 5 and _NSE_OPEN <= t <= _NSE_CLOSE:
        return order_dt  # market open now
    if order_dt.weekday() < 5 and t < _NSE_OPEN:
        return order_dt.replace(hour=9, minute=15, second=0, microsecond=0)
    nxt = order_dt + timedelta(days=1)
    while nxt.weekday() >= 5:  # skip Sat/Sun
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

        self.capital = float(cfg.get("desk_capital", cfg.get("paper_capital", 100_000.0)))
        self.max_positions = int(cfg.get("paper_max_positions", 20))
        self.holding_days = int(cfg.get("paper_holding_days", 20))
        self.benchmark = cfg.get("paper_benchmark", "^NSEI")

        self._state = self._load()

    # ---- persistence -----------------------------------------------------

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

    def has_open_position(self, ticker: str) -> bool:
        return any(
            p["ticker"] == ticker and p["status"] == "open" for p in self.positions
        )

    # ---- opening ---------------------------------------------------------

    def open_position(
        self,
        ticker: str,
        rating: str,
        entry_price: float,
        entry_date: str,
        signals: Optional[List[str]] = None,
        levels: Optional[dict] = None,
    ) -> Optional[dict]:
        """Record a simulated buy. No-op (returns None) if a position for this
        ticker is already open or inputs are invalid."""
        if entry_price is None or entry_price <= 0:
            return None
        if self.has_open_position(ticker):
            return None
        sizing = compute_position_size(self.capital, self.max_positions, entry_price)
        alloc = sizing["alloc"]
        shares = sizing["shares"]
        notional = sizing["notional"]
        order_dt = datetime.now(IST)
        exec_dt = _next_execution(order_dt)
        pos = {
            "ticker": ticker,
            "rating": rating,
            "signals": signals or [],
            "entry_date": entry_date,
            # When the screen placed the order vs when a real fill would occur.
            "order_time": order_dt.isoformat(timespec="minutes"),
            "execution_time": exec_dt.isoformat(timespec="minutes"),
            "execution_deferred": exec_dt > order_dt,
            "entry_price": round(entry_price, 2),
            "shares": shares,
            "alloc": alloc,
            "notional": notional,
            # ATR-based trade levels (target & stoploss) for the buy list.
            "stoploss": (levels or {}).get("stoploss"),
            "target": (levels or {}).get("target"),
            "stop_pct": (levels or {}).get("stop_pct"),
            "target_pct": (levels or {}).get("target_pct"),
            "status": "open",
            "exit_date": None,
            "exit_price": None,
            "raw_return": None,
            "alpha_return": None,
            "holding_days_actual": None,
        }
        self.positions.append(pos)
        self._save()
        return pos

    # ---- marking & closing ----------------------------------------------

    def _history(self, symbol: str, start: str, end: str):
        try:
            df = yf.Ticker(symbol).history(start=start, end=end)
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            return df
        except Exception as e:  # noqa: BLE001
            logger.warning("price fetch failed for %s (%s)", symbol, e)
            return None

    def _latest_close(self, symbol: str) -> Optional[float]:
        start = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
        df = self._history(symbol, start, datetime.now().strftime("%Y-%m-%d"))
        if df is None or df.empty:
            return None
        return float(df["Close"].iloc[-1])

    def mark_to_market(self) -> dict:
        """Value open positions and close any past their holding period.

        Returns a dict with current unrealized P&L and how many positions were
        closed this call. Closed trades get raw return + alpha vs benchmark.
        """
        closed_now = 0
        unrealized = 0.0
        today = datetime.now()

        for p in self.positions:
            if p["status"] != "open":
                continue
            entry = datetime.strptime(p["entry_date"], "%Y-%m-%d")
            # Trading days ~ calendar days * 5/7; add buffer for holidays.
            target_cal_days = int(self.holding_days * 7 / 5) + 5
            due = entry + timedelta(days=target_cal_days)

            if today >= due:
                self._close_position(p, entry)
                if p["status"] == "closed":
                    closed_now += 1
            else:
                price = self._latest_close(p["ticker"])
                if price is not None:
                    unrealized += (price - p["entry_price"]) * p["shares"]

        self._save()
        return {
            "closed_now": closed_now,
            "unrealized_pnl": round(unrealized, 2),
            "open_positions": sum(1 for p in self.positions if p["status"] == "open"),
        }

    def _close_position(self, p: dict, entry: datetime) -> None:
        """Close at the price ``holding_days`` trading days after entry and
        compute alpha vs the benchmark over the same window."""
        end = entry + timedelta(days=int(self.holding_days * 7 / 5) + 10)
        stock = self._history(p["ticker"], p["entry_date"], end.strftime("%Y-%m-%d"))
        bench = self._history(self.benchmark, p["entry_date"], end.strftime("%Y-%m-%d"))
        if stock is None or len(stock) < 2:
            return  # try again next run

        idx = min(self.holding_days, len(stock) - 1)
        exit_price = float(stock["Close"].iloc[idx])
        raw = (exit_price - p["entry_price"]) / p["entry_price"]

        alpha = None
        if bench is not None and len(bench) >= 2:
            b_idx = min(self.holding_days, len(bench) - 1)
            bench_ret = (
                float(bench["Close"].iloc[b_idx]) - float(bench["Close"].iloc[0])
            ) / float(bench["Close"].iloc[0])
            alpha = raw - bench_ret

        p["status"] = "closed"
        p["exit_price"] = round(exit_price, 2)
        p["exit_date"] = stock.index[idx].strftime("%Y-%m-%d")
        p["raw_return"] = round(raw, 4)
        p["alpha_return"] = round(alpha, 4) if alpha is not None else None
        p["holding_days_actual"] = idx
        p["rupee_pnl"] = leg_rupee_pnl(p["shares"], p["entry_price"], exit_price, 100.0)

    # ---- reporting -------------------------------------------------------

    def stats(self) -> dict:
        """Aggregate reliability metrics overall and per technical signal."""
        closed = [p for p in self.positions if p["status"] == "closed"]
        open_ = [p for p in self.positions if p["status"] == "open"]

        def _agg(trades: List[dict]) -> dict:
            n = len(trades)
            if n == 0:
                return {"trades": 0, "win_rate": None, "avg_return": None,
                        "avg_alpha": None, "total_pnl": 0.0}
            wins = sum(1 for t in trades if (t["raw_return"] or 0) > 0)
            avg_ret = sum(t["raw_return"] or 0 for t in trades) / n
            alphas = [t["alpha_return"] for t in trades if t["alpha_return"] is not None]
            avg_alpha = sum(alphas) / len(alphas) if alphas else None
            pnl = sum(t.get("rupee_pnl") or (t["exit_price"] - t["entry_price"]) * t["shares"] for t in trades)
            return {
                "trades": n,
                "win_rate": round(100 * wins / n, 1),
                "avg_return": round(100 * avg_ret, 2),
                "avg_alpha": round(100 * avg_alpha, 2) if avg_alpha is not None else None,
                "total_pnl": round(pnl, 2),
            }

        # Per-signal breakdown: a trade contributes to every signal that fired.
        per_signal: Dict[str, dict] = {}
        signal_names = {s for p in closed for s in p.get("signals", [])}
        for name in sorted(signal_names):
            subset = [p for p in closed if name in p.get("signals", [])]
            per_signal[name] = _agg(subset)

        return {
            "overall": _agg(closed),
            "open_positions": len(open_),
            "closed_positions": len(closed),
            "per_signal": per_signal,
        }
