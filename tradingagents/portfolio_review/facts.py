"""Collect grounded facts from all paper desks (no LLM)."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

DESK_BOOKS: List[Tuple[str, str, str]] = [
    ("swing", "Swing", "tradingagents.swing.SwingPositionBook"),
    ("momentum", "Momentum", "tradingagents.momentum.MomentumPositionBook"),
    ("nss", "NSS", "tradingagents.nss.NSSPositionBook"),
    ("supertrend_rsi", "ST+RSI", "tradingagents.supertrend_rsi.SuperTrendRSIPositionBook"),
    ("trama", "TRAMA", "tradingagents.trama.TramaPositionBook"),
    ("nw_envelope", "NW Envelope", "tradingagents.nw_envelope.NwEnvelopePositionBook"),
    ("pattern_forecast", "Pattern FC", "tradingagents.pattern_forecast.PatternForecastPositionBook"),
]


def _import_book(class_path: str):
    module_name, cls_name = class_path.rsplit(".", 1)
    import importlib

    mod = importlib.import_module(module_name)
    return getattr(mod, cls_name)


def _days_held(screen_date: Optional[str], as_of: str) -> Optional[int]:
    if not screen_date:
        return None
    try:
        a = datetime.strptime(as_of, "%Y-%m-%d")
        b = datetime.strptime(screen_date[:10], "%Y-%m-%d")
        return max(0, (a - b).days)
    except ValueError:
        return None


def _signal_summary(desk: str, p: dict) -> str:
    parts: List[str] = []
    if p.get("direction"):
        parts.append(str(p["direction"]))
    if p.get("ai_rating"):
        parts.append(f"AI={p['ai_rating']}")
    if p.get("composite_score") is not None:
        parts.append(f"score={p['composite_score']}")
    if p.get("signal_score") is not None:
        parts.append(f"STscore={p['signal_score']}")
    if p.get("probability") is not None:
        parts.append(f"prob={p['probability']:.1f}%")
    if p.get("projected_close_pct") is not None:
        parts.append(f"proj5d={p['projected_close_pct']:+.1f}%")
    if p.get("rsi") is not None:
        parts.append(f"RSI={float(p['rsi']):.1f}")
    if p.get("adx") is not None:
        parts.append(f"ADX={float(p['adx']):.1f}")
    if p.get("cross_age") is not None:
        parts.append(f"cross_age={p['cross_age']}")
    if p.get("flip_age") is not None:
        parts.append(f"flip_age={p['flip_age']}")
    if p.get("dist_pct") is not None:
        parts.append(f"dist={float(p['dist_pct']):+.1f}%")
    if p.get("primary_reason"):
        parts.append(str(p["primary_reason"])[:40])
    if p.get("analogue_end_date"):
        parts.append(f"analogue={p['analogue_end_date']}")
    if not parts:
        return desk
    return " · ".join(parts)


def _position_facts(
    desk_id: str,
    desk_label: str,
    p: dict,
    *,
    as_of: str,
    price: Optional[float],
) -> dict:
    status = p.get("status", "open")
    ticker = p.get("ticker", "")
    entry = float(p.get("entry_price") or 0)
    shares = float(p.get("shares") or 0)
    rem = float(p.get("remaining_pct", 100.0)) / 100.0
    notional = float(p.get("notional") or p.get("notional_inr") or shares * entry)
    stop = p.get("trailing_stop") or p.get("stop_loss")
    stop_f = float(stop) if stop is not None else None

    realized = float(p.get("rupee_pnl") or 0) if status == "closed" else 0.0
    unrealized = 0.0
    current = price
    return_pct = None
    stop_cushion_pct = None

    if status == "open" and current is not None and entry and shares:
        unrealized = (current - entry) * shares * rem
        return_pct = round(100.0 * (current / entry - 1), 2)
        if stop_f is not None and current > 0:
            stop_cushion_pct = round(100.0 * (current - stop_f) / current, 2)
    market_value_inr = None
    if status == "open" and current is not None and shares:
        market_value_inr = round(current * shares * rem, 2)

    pos_id = f"{desk_id}|{ticker}|{status}|{p.get('screen_date', '')}"

    return {
        "id": pos_id,
        "desk": desk_id,
        "desk_label": desk_label,
        "ticker": ticker,
        "symbol": ticker.replace(".NS", ""),
        "stock_name": p.get("stock_name") or ticker.replace(".NS", ""),
        "sector": p.get("sector"),
        "status": status,
        "screen_date": p.get("screen_date"),
        "exit_date": p.get("exit_date"),
        "days_held": _days_held(p.get("screen_date"), as_of) if status == "open" else p.get("trading_days_held"),
        "entry_price": round(entry, 2) if entry else None,
        "current_price": round(current, 2) if current is not None else None,
        "shares": int(shares) if shares else 0,
        "notional_inr": round(notional, 2),
        "market_value_inr": market_value_inr,
        "stop_loss": round(stop_f, 2) if stop_f is not None else None,
        "stop_cushion_pct": stop_cushion_pct,
        "realized_inr": round(realized, 2),
        "unrealized_inr": round(unrealized, 2),
        "total_inr": round(realized + unrealized, 2),
        "return_pct": return_pct if status == "open" else (
            round(100.0 * float(p["raw_return"]), 2) if p.get("raw_return") is not None else None
        ),
        "exit_reason": p.get("exit_reason"),
        "outcome": p.get("outcome"),
        "signal_summary": _signal_summary(desk_id, p),
        "ai_rating": p.get("ai_rating"),
        "phase": p.get("phase"),
    }


def _pending_count(desk_id: str) -> int:
    home = Path(os.path.expanduser("~/.tradingagents")) / desk_id
    path = home / "pending_replacements.json"
    if not path.exists():
        return 0
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        items = raw if isinstance(raw, list) else raw.get("proposals", [])
        return sum(1 for x in items if isinstance(x, dict) and not x.get("approved"))
    except Exception:  # noqa: BLE001
        return 0


def _risk_flags(positions: List[dict], desk_meta: List[dict]) -> List[dict]:
    flags: List[dict] = []
    desk_by_id = {d["id"]: d for d in desk_meta}

    for d in desk_meta:
        if d["open_count"] >= d["max_positions"]:
            flags.append({
                "id": f"desk_full|{d['id']}",
                "desk": d["id"],
                "ticker": None,
                "severity": "medium",
                "fact": f"{d['label']} book full ({d['open_count']}/{d['max_positions']})",
                "suggested_action": f"Review pending replacements on {d['id']} desk",
            })
        if d.get("pending_replacements", 0) > 0:
            flags.append({
                "id": f"pending|{d['id']}",
                "desk": d["id"],
                "ticker": None,
                "severity": "low",
                "fact": f"{d['pending_replacements']} unapproved replacement proposal(s)",
                "suggested_action": f"Run tradingagents {d['cli_prefix']}-approve",
            })

    for p in positions:
        if p["status"] != "open":
            continue
        if p.get("stop_cushion_pct") is not None and p["stop_cushion_pct"] < 2.0:
            flags.append({
                "id": f"stop_tight|{p['id']}",
                "desk": p["desk"],
                "ticker": p["ticker"],
                "severity": "high",
                "fact": (
                    f"{p['symbol']} stop cushion {p['stop_cushion_pct']:.1f}% "
                    f"(stop {p['stop_loss']}, now {p['current_price']})"
                ),
                "suggested_action": f"Monitor or tighten risk on {p['symbol']} ({p['desk']})",
            })
        if p.get("return_pct") is not None and p["return_pct"] <= -3.0:
            flags.append({
                "id": f"drawdown|{p['id']}",
                "desk": p["desk"],
                "ticker": p["ticker"],
                "severity": "medium",
                "fact": f"{p['symbol']} open return {p['return_pct']:+.1f}%",
                "suggested_action": f"Revisit thesis for {p['symbol']} on {p['desk']} desk",
            })

    return flags


CLI_PREFIX = {
    "swing": "swing",
    "momentum": "momentum",
    "nss": "nss",
    "supertrend_rsi": "supertrend-rsi",
    "trama": "trama",
    "nw_envelope": "nw-envelope",
    "pattern_forecast": "pattern-forecast",
}


def collect_portfolio_facts(config: dict, as_of: Optional[str] = None) -> dict:
    """Build a JSON-serializable facts packet from all desks."""
    as_of = as_of or datetime.now().strftime("%Y-%m-%d")
    desk_capital = float(config.get("desk_capital", 100_000.0))

    all_positions: List[dict] = []
    desk_meta: List[dict] = []
    total_realized = total_unrealized = 0.0

    for desk_id, label, class_path in DESK_BOOKS:
        book_cls = _import_book(class_path)
        book = book_cls(config)
        mtm = book.mark_to_market()
        stats = book.stats()
        overall = stats.get("overall", {})

        realized = float(overall.get("total_pnl") or 0)
        unrealized = float(mtm.get("unrealized_pnl") or 0)
        total_realized += realized
        total_unrealized += unrealized

        open_count = int(stats.get("open_positions") or 0)
        max_pos = int(getattr(book, "max_positions", 20))

        desk_meta.append({
            "id": desk_id,
            "label": label,
            "cli_prefix": CLI_PREFIX.get(desk_id, desk_id),
            "open_count": open_count,
            "max_positions": max_pos,
            "closed_count": int(stats.get("closed_positions") or 0),
            "realized_inr": round(realized, 2),
            "unrealized_inr": round(unrealized, 2),
            "total_inr": round(realized + unrealized, 2),
            "win_rate_pct": overall.get("win_rate"),
            "pending_replacements": _pending_count(desk_id),
            "capital_inr": desk_capital,
            "utilization_pct": round(100.0 * open_count / max_pos, 1) if max_pos else 0,
        })

        for p in book.positions:
            price = book.latest_price(p["ticker"]) if p.get("status") == "open" else p.get("exit_price")
            if p.get("status") == "closed" and price is not None:
                price = float(price)
            elif p.get("status") == "open":
                price = float(price) if price is not None else None
            else:
                price = None
            all_positions.append(
                _position_facts(desk_id, label, p, as_of=as_of, price=price)
            )

    open_positions = [p for p in all_positions if p["status"] == "open"]
    closed_positions = [p for p in all_positions if p["status"] == "closed"]

    by_total = sorted(open_positions, key=lambda x: x["total_inr"], reverse=True)
    top = by_total[:5]
    bottom = sorted(open_positions, key=lambda x: x["total_inr"])[:5]

    flags = _risk_flags(all_positions, desk_meta)

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "as_of_date": as_of,
        "summary": {
            "desks_tracked": len(desk_meta),
            "desk_capital_inr": desk_capital,
            "open_positions": len(open_positions),
            "closed_positions": len(closed_positions),
            "total_realized_inr": round(total_realized, 2),
            "total_unrealized_inr": round(total_unrealized, 2),
            "total_pnl_inr": round(total_realized + total_unrealized, 2),
        },
        "desks": desk_meta,
        "positions": all_positions,
        "top_contributors": [
            {"id": p["id"], "desk": p["desk"], "ticker": p["ticker"], "total_inr": p["total_inr"], "return_pct": p["return_pct"]}
            for p in top
        ],
        "top_detractors": [
            {"id": p["id"], "desk": p["desk"], "ticker": p["ticker"], "total_inr": p["total_inr"], "return_pct": p["return_pct"]}
            for p in bottom
        ],
        "risk_flags": flags,
    }
