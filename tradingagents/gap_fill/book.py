"""Persist Gap Fill screener picks as ``gap_fill`` positions."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, TYPE_CHECKING

import pandas as pd
import yfinance as yf

from .exits import evaluate_bar_exits
from .trailing import ratchet_stop
from tradingagents.paper.sizing import (
    compute_position_size,
    ensure_sizing_fields,
    leg_rupee_pnl,
    skip_exit_for_entry_day,
    total_rupee_pnl_from_legs,
)
from tradingagents.screening.gap_fill_engine import gap_trade_side, pick_passes_long_entry
from tradingagents.screening.swing_indicators import compute_trade_levels
from tradingagents.swing.exits import ExitAction, ExitReason, trading_days_between

if TYPE_CHECKING:
    from tradingagents.screening.gap_fill_screener import GapFillPick

logger = logging.getLogger(__name__)

_DEFAULT_HOME = os.path.join(os.path.expanduser("~"), ".tradingagents")
STRATEGY_NAME = "gap_fill"


class GapFillPositionBook:
    def __init__(self, config: Optional[dict] = None):
        cfg = config or {}
        self.config = cfg
        path = cfg.get("gap_fill_book_path") or os.getenv(
            "TRADINGAGENTS_GAP_FILL_BOOK_PATH",
            os.path.join(_DEFAULT_HOME, "gap_fill", "positions.json"),
        )
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.holding_days = int(cfg.get("gap_fill_holding_days", 20))
        self.max_positions = int(cfg.get("gap_fill_max_positions", 20))
        self.max_per_sector = int(cfg.get("gap_fill_max_per_sector", 4))
        self.desk_capital = float(cfg.get("desk_capital", 100_000.0))
        self.target_1_rr = float(cfg.get("gap_fill_target_1_rr", 1.5))
        self.target_2_rr = float(cfg.get("gap_fill_target_2_rr", 2.5))
        self.stop_buffer_pct = float(cfg.get("gap_fill_stop_buffer_pct", 0.5))
        self.benchmark = cfg.get("paper_benchmark", "^NSEI")
        self._state = self._load()
        self._migrate_positions()
        self._backfill_sectors()

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
            "initial_stop_loss": p.get("stop_loss"),
            "t2_partial_done": False,
            "partial_exits": [],
            "risk_pct": p.get("stop_loss_pct"),
        }
        for key, val in defaults.items():
            if key not in p or p[key] is None:
                p[key] = val
                changed = True
        if p.get("t2_partial_done") and p.get("status") == "open":
            if p.get("phase") != "runner":
                p["phase"] = "runner"
                changed = True
        if ensure_sizing_fields(p, self.desk_capital, self.max_positions):
            changed = True
        return changed

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
            logger.warning("Could not backfill Gap Fill sectors (%s)", e)
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

    def _load(self) -> dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except Exception as e:  # noqa: BLE001
                logger.warning("Could not read Gap Fill book (%s); starting fresh", e)
        return {"strategy": STRATEGY_NAME, "positions": [], "sell_signals": []}

    def _save(self) -> None:
        self._state["strategy"] = STRATEGY_NAME
        self._state.setdefault("sell_signals", [])
        self._state["updated_at"] = datetime.now().isoformat(timespec="seconds")
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._state, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    @property
    def positions(self) -> List[dict]:
        return self._state["positions"]

    @property
    def sell_signals(self) -> List[dict]:
        return self._state.setdefault("sell_signals", [])

    def open_count(self) -> int:
        return sum(1 for p in self.positions if p.get("status") == "open")

    def has_open_position(self, ticker: str) -> bool:
        return any(p["ticker"] == ticker and p.get("status") == "open" for p in self.positions)

    def touch_screen_date(self, ticker: str, screen_date: str) -> None:
        for p in self.positions:
            if p["ticker"] == ticker and p.get("status") == "open":
                p["last_screen_date"] = screen_date
        self._save()

    def reset_book(self) -> None:
        """Clear all positions and start a fresh paper book."""
        self._state = {"strategy": STRATEGY_NAME, "positions": [], "sell_signals": []}
        self._save()

    def sector_open_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for p in self.positions:
            if p.get("status") == "open":
                sector = p.get("sector") or ""
                counts[sector] = counts.get(sector, 0) + 1
        return counts

    def open_position(self, pick: "GapFillPick", screen_date: str) -> Optional[dict]:
        ok, reason = pick_passes_long_entry(pick.signal, self.config)
        if not ok:
            logger.warning("Skip %s — %s", pick.symbol, reason)
            return None
        if gap_trade_side(pick.direction) != "BUY":
            return None
        if self.has_open_position(pick.symbol):
            return None
        if self.open_count() >= self.max_positions:
            return None
        sector = pick.sector or (pick.signal.sector if pick.signal else None) or ""
        if self.sector_open_counts().get(sector, 0) >= self.max_per_sector:
            return None
        row = self._pick_to_position(pick, screen_date)
        if row is None:
            return None
        self.positions.append(row)
        self._save()
        return row

    def store_sell_signals(
        self,
        picks: List["GapFillPick"],
        screen_date: Optional[str] = None,
    ) -> List[dict]:
        """Persist UP-gap (SELL) signals for audit + closing open longs."""
        screen_date = screen_date or datetime.now().strftime("%Y-%m-%d")
        rows: List[dict] = []
        for pick in picks:
            if gap_trade_side(pick.direction) != "SELL":
                continue
            sig = pick.signal
            rows.append({
                "ticker": pick.symbol,
                "stock_name": pick.stock_name or sig.stock_name or pick.symbol.replace(".NS", ""),
                "sector": pick.sector or sig.sector or "—",
                "screen_date": screen_date,
                "direction": "SELL",
                "gap_direction": sig.direction,
                "close": float(sig.close),
                "gap_pct": float(sig.gap_pct),
                "fill_pct": float(sig.fill_pct),
                "gap_age": int(sig.gap_age),
                "remark": sig.remark,
            })
        kept = [s for s in self.sell_signals if s.get("screen_date") != screen_date]
        kept.extend(rows)
        if len(kept) > 500:
            kept = kept[-500:]
        self._state["sell_signals"] = kept
        self._save()
        return rows

    def close_on_sell_signals(
        self,
        picks: List["GapFillPick"],
        as_of: Optional[str] = None,
    ) -> List[dict]:
        """Close open longs when a matching UP-gap (SELL) signal appears."""
        as_of = as_of or datetime.now().strftime("%Y-%m-%d")
        events: List[dict] = []
        for pick in picks:
            if gap_trade_side(pick.direction) != "SELL":
                continue
            if not self.has_open_position(pick.symbol):
                continue
            pos = next(
                p for p in self.positions
                if p["ticker"] == pick.symbol and p.get("status") == "open"
            )
            if skip_exit_for_entry_day(pos["screen_date"], as_of):
                continue
            self._ensure_position_fields(pos)
            remaining = float(pos.get("remaining_pct", 100.0))
            if remaining <= 0:
                continue
            exit_price = float(pick.signal.close)
            hist = self._history(
                pos["ticker"],
                pos["screen_date"],
                (datetime.strptime(as_of, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d"),
            )
            if hist is None:
                hist = pd.DataFrame({"Close": [exit_price]}, index=pd.to_datetime([as_of]))
            action = ExitAction(
                ticker=pos["ticker"],
                reason=ExitReason.SIGNAL_SELL,
                exit_price=round(exit_price, 2),
                exit_date=as_of,
                exit_pct=remaining,
                partial=False,
            )
            events.append(self._apply_action(pos, action, hist))
        if events:
            self._save()
        return events

    def save_picks(self, picks: List["GapFillPick"], screen_date: Optional[str] = None) -> List[dict]:
        screen_date = screen_date or datetime.now().strftime("%Y-%m-%d")
        self.store_sell_signals(picks, screen_date=screen_date)
        saved: List[dict] = []
        for pick in picks:
            ok, _ = pick_passes_long_entry(pick.signal, self.config)
            if not ok:
                continue
            if gap_trade_side(pick.direction) != "BUY":
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

    def _pick_to_position(self, pick: "GapFillPick", screen_date: str) -> Optional[dict]:
        sig = pick.signal
        entry = float(sig.close)
        stop = float(sig.gap_low) * (1.0 - self.stop_buffer_pct / 100.0)
        levels = compute_trade_levels(entry, stop, self.target_1_rr, self.target_2_rr)
        if levels is None:
            logger.warning("Invalid trade levels for %s (entry=%s stop=%s)", pick.symbol, entry, stop)
            return None

        target_1 = float(sig.fill_target)
        if target_1 <= entry:
            logger.warning("Fill target not above entry for %s", pick.symbol)
            return None

        levels["target_1"] = round(target_1, 2)
        levels["target_1_pct"] = round(100.0 * (target_1 - entry) / entry, 2)

        sizing = compute_position_size(self.desk_capital, self.max_positions, levels["entry"])
        if int(sizing["shares"] or 0) < 1:
            logger.warning("Skip %s — cannot fit in INR %.0f slot at entry %.2f", pick.symbol, sizing["alloc"], levels["entry"])
            return None
        return {
            "strategy": STRATEGY_NAME,
            "ticker": pick.symbol,
            "stock_name": sig.stock_name or pick.stock_name or pick.symbol.replace(".NS", ""),
            "sector": sig.sector or pick.sector or "—",
            "screen_date": screen_date,
            "last_screen_date": screen_date,
            "entry_price": levels["entry"],
            "shares": sizing["shares"],
            "alloc": sizing["alloc"],
            "notional": sizing["notional"],
            "stop_loss": levels["stop_loss"],
            "stop_loss_pct": levels["stop_loss_pct"],
            "trailing_stop": levels["stop_loss"],
            "initial_stop_loss": levels["stop_loss"],
            "risk_pct": levels["stop_loss_pct"],
            "target_1": levels["target_1"],
            "target_1_pct": levels["target_1_pct"],
            "target_2": levels["target_2"],
            "target_2_pct": levels["target_2_pct"],
            "risk_reward_ratio": levels["risk_reward_ratio"],
            "risk_reward_ratio_2": levels["risk_reward_ratio_2"],
            "gap_age": sig.gap_age,
            "gap_pct": sig.gap_pct,
            "gap_low": sig.gap_low,
            "gap_high": sig.gap_high,
            "fill_target": sig.fill_target,
            "fill_pct": sig.fill_pct,
            "rsi": sig.rsi,
            "remark": sig.remark,
            "direction": "BUY",
            "gap_direction": sig.direction if sig.direction in ("UP", "DOWN") else None,
            "phase": "initial",
            "remaining_pct": 100.0,
            "t2_partial_done": False,
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

    def _update_trailing_stop(self, p: dict, history: pd.DataFrame) -> None:
        gap_low = float(p.get("gap_low") or 0)
        if gap_low <= 0:
            return
        close = float(history["Close"].iloc[-1])
        if close > gap_low:
            floor = gap_low * (1.0 - self.stop_buffer_pct / 100.0)
            p["trailing_stop"] = round(
                ratchet_stop(float(p.get("trailing_stop") or p["stop_loss"]), floor),
                2,
            )
            p["stop_loss"] = p["trailing_stop"]
            entry = float(p["entry_price"])
            if entry > 0:
                p["stop_loss_pct"] = round(-100.0 * (entry - p["trailing_stop"]) / entry, 2)

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

            replay = dict(p)
            initial_stop = float(p.get("initial_stop_loss") or p.get("stop_loss") or 0)
            replay["stop_loss"] = initial_stop
            replay["trailing_stop"] = initial_stop
            closed = False
            for i in range(len(hist)):
                bar_date = hist.index[i].strftime("%Y-%m-%d")
                history_to_bar = hist.iloc[: i + 1]
                if bar_date <= p["screen_date"]:
                    self._update_trailing_stop(replay, history_to_bar)
                    continue
                if bar_date > as_of:
                    break
                actions = evaluate_bar_exits(
                    replay, hist.iloc[i], bar_date, self.holding_days, history_to_bar
                )
                if actions:
                    events.append(self._apply_action(p, actions[0], history_to_bar))
                    closed = True
                    break
                self._update_trailing_stop(replay, history_to_bar)
            if not closed:
                p["trailing_stop"] = replay.get("trailing_stop", p.get("trailing_stop"))
                p["stop_loss"] = replay.get("stop_loss", p.get("stop_loss"))
                p["stop_loss_pct"] = replay.get("stop_loss_pct", p.get("stop_loss_pct"))

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

        if action.partial:
            p["partial_exits"].append({
                "date": action.exit_date,
                "price": action.exit_price,
                "pct": action.exit_pct,
                "reason": action.reason.value,
                "return": round(leg_return, 4),
                "rupee_pnl": leg_rupee,
            })
            p["remaining_pct"] = round(float(p["remaining_pct"]) - action.exit_pct, 2)
            p["t2_partial_done"] = True
            p["phase"] = "runner"
            event["remaining_pct"] = p["remaining_pct"]
            return event

        p["partial_exits"].append({
            "date": action.exit_date,
            "price": action.exit_price,
            "pct": action.exit_pct,
            "reason": action.reason.value,
            "return": round(leg_return, 4),
            "rupee_pnl": leg_rupee,
        })
        blended = self._blended_return(p)
        p["status"] = "closed"
        p["remaining_pct"] = 0.0
        p["exit_price"] = action.exit_price
        p["exit_date"] = action.exit_date
        p["exit_reason"] = action.reason.value
        p["raw_return"] = round(blended, 4)
        p["rupee_pnl"] = total_rupee_pnl_from_legs(p["partial_exits"])
        alpha = self._alpha(p["screen_date"], action.exit_date, blended) if blended is not None else None
        p["alpha_return"] = round(alpha, 4) if alpha is not None else None
        p["trading_days_held"] = trading_days_between(p["screen_date"], action.exit_date, history)
        p["outcome"] = self._outcome_for_reason(action.reason, blended)
        event["raw_return"] = p["raw_return"]
        event["rupee_pnl"] = p["rupee_pnl"]
        event["outcome"] = p["outcome"]
        return event

    def _blended_return(self, p: dict) -> float:
        total = 0.0
        for leg in p.get("partial_exits", []):
            total += (leg["pct"] / 100.0) * leg["return"]
        return total

    def _outcome_for_reason(self, reason: ExitReason, blended: float) -> str:
        if reason == ExitReason.STOP:
            return "loss"
        if reason in (
            ExitReason.TARGET_1,
            ExitReason.TARGET_2_PARTIAL,
            ExitReason.TRAIL_STOP,
            ExitReason.TIME,
            ExitReason.SIGNAL_SELL,
        ):
            return "success" if blended > 0 else "loss"
        return "success" if blended > 0 else "loss"

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
                    partial=False,
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
            "partial_events": sum(1 for e in summary.get("closed", []) if e.get("partial")),
            "unrealized_pnl": round(unrealized, 2),
            "open_positions": self.open_count(),
        }

    def stats(self) -> dict:
        closed = [p for p in self.positions if p.get("status") == "closed"]
        open_ = [p for p in self.positions if p.get("status") == "open"]
        runners = [p for p in open_ if p.get("phase") == "runner"]

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
        for reason in (
            ExitReason.STOP.value,
            ExitReason.TARGET_1.value,
            ExitReason.TARGET_2_PARTIAL.value,
            ExitReason.TRAIL_STOP.value,
            ExitReason.TIME.value,
            ExitReason.SIGNAL_SELL.value,
            ExitReason.FORECLOSURE.value,
        ):
            subset = [p for p in closed if p.get("exit_reason") == reason]
            if subset:
                by_reason[reason] = _agg(subset)

        return {
            "overall": _agg(closed),
            "by_exit_reason": by_reason,
            "open_positions": len(open_),
            "runner_positions": len(runners),
            "closed_positions": len(closed),
        }
