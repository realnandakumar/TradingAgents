"""Print momentum paper portfolio snapshot as JSON."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.momentum import STRATEGY_NAME, MomentumPositionBook


def main() -> None:
    book = MomentumPositionBook(DEFAULT_CONFIG.copy())
    summary = book.mark_to_market()
    stats = book.stats()
    open_positions = [p for p in book.positions if p.get("status") == "open"]
    closed = [p for p in book.positions if p.get("status") == "closed"]

    rows = []
    for p in open_positions:
        price = book.latest_price(p["ticker"])
        entry = float(p["entry_price"])
        rem = float(p.get("remaining_pct", 100)) / 100
        pnl_pct = ((price - entry) / entry * 100) if price else None
        pnl_abs = (price - entry) * rem if price else None
        trail = float(p.get("trailing_stop", p["stop_loss"]))
        dist_stop = ((price - trail) / price * 100) if price else None
        dist_t2 = ((float(p["target_2"]) - price) / price * 100) if price else None
        rows.append(
            {
                "ticker": p["ticker"].replace(".NS", ""),
                "stock": p.get("stock_name", ""),
                "sector": p.get("sector", ""),
                "screen_date": p.get("screen_date"),
                "entry": entry,
                "last": price,
                "pnl_pct": round(pnl_pct, 2) if pnl_pct is not None else None,
                "pnl_abs": round(pnl_abs, 2) if pnl_abs is not None else None,
                "stop": trail,
                "stop_pct": p.get("stop_loss_pct"),
                "t1": float(p["target_1"]),
                "t1_pct": p.get("target_1_pct"),
                "t2": float(p["target_2"]),
                "t2_pct": p.get("target_2_pct"),
                "dist_stop_pct": round(dist_stop, 2) if dist_stop is not None else None,
                "dist_t2_pct": round(dist_t2, 2) if dist_t2 is not None else None,
                "phase": p.get("phase", "initial"),
                "remaining_pct": p.get("remaining_pct", 100),
                "rsi": p.get("rsi"),
                "adx": p.get("adx"),
                "macd": p.get("macd"),
                "volume_ratio_5_20": p.get("volume_ratio_5_20"),
                "rr": f"{p.get('risk_reward_ratio', 0)}:{p.get('risk_reward_ratio_2', 0)}",
            }
        )

    out = {
        "strategy": STRATEGY_NAME,
        "updated_at": book._state.get("updated_at"),
        "summary": summary,
        "stats": stats,
        "open": rows,
        "closed_count": len(closed),
        "max_positions": book.max_positions,
        "max_holding_days": book.max_holding_days,
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
