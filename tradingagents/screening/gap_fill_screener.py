"""Universe screener for Gap Fill setups."""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

import pandas as pd

from tradingagents.screening.gap_fill_engine import (
    STRATEGY_ID,
    STRATEGY_NAME,
    STRATEGY_VERSION,
    GapFillSignal,
    evaluate_gap_fill,
    gap_trade_side,
    pick_passes_long_entry,
)
from tradingagents.screening.screener_snapshot import save_screener_snapshot
from tradingagents.screening.universe import load_universe, load_universe_metadata

logger = logging.getLogger(__name__)


@dataclass
class GapFillPick:
    signal: GapFillSignal
    stock_name: str = ""
    sector: str = ""

    @property
    def symbol(self) -> str:
        return self.signal.symbol

    @property
    def direction(self) -> str:
        return self.signal.direction

    @property
    def gap_age(self) -> int:
        return self.signal.gap_age

    @property
    def remark(self) -> str:
        return self.signal.remark

    @property
    def trade_side(self) -> Optional[str]:
        return gap_trade_side(self.direction)

    @property
    def is_long_candidate(self) -> bool:
        return self.trade_side == "BUY"

    def passes_long_entry(self, config: Optional[dict] = None) -> bool:
        ok, _ = pick_passes_long_entry(self.signal, config)
        return ok


def screen_gap_fill(
    config: dict,
    progress: Optional[Callable[[str], None]] = None,
    price_data: Optional[Dict[str, pd.DataFrame]] = None,
) -> List[GapFillPick]:
    """Screen the NSE universe for active true gaps on daily charts."""

    def _log(msg: str):
        logger.info(msg)
        if progress:
            progress(msg)

    universe = load_universe(
        csv_path=config.get("screen_universe_csv"),
        cache_dir=config.get("data_cache_dir"),
    )
    metadata = load_universe_metadata(
        csv_path=config.get("screen_universe_csv"),
        cache_dir=config.get("data_cache_dir"),
        allow_download=True,
    )

    period = config.get("gap_fill_history_period", "1y")
    if price_data is None:
        _log(f"Downloading {period} history for {len(universe)} tickers...")
        from tradingagents.screening.prices import download_history

        price_data = download_history(universe, period=period)

    max_age = int(config.get("gap_fill_max_age", 30))
    top_n = int(config.get("gap_fill_top_n", 20))
    max_per_sector = int(config.get("gap_fill_max_per_sector", 4))
    directions = str(config.get("gap_fill_directions", "UP,DOWN"))

    picks: List[GapFillPick] = []
    n_checked = 0
    n_reject = 0

    for sym in universe:
        df = price_data.get(sym)
        if df is None:
            continue
        n_checked += 1
        sig = evaluate_gap_fill(df, config, symbol=sym)
        if sig.rejected or sig.direction == "NONE":
            n_reject += 1
            continue

        meta = metadata.get(sym, {})
        name = meta.get("name") or sym.replace(".NS", "").replace(".BO", "")
        sector = meta.get("sector") or "—"
        sig.stock_name = name
        sig.sector = sector
        picks.append(GapFillPick(signal=sig, stock_name=name, sector=sector))

    picks.sort(key=lambda p: (p.gap_age, -abs(p.signal.gap_pct)))

    sells = [p for p in picks if gap_trade_side(p.direction) == "SELL"]
    buys = [p for p in picks if gap_trade_side(p.direction) == "BUY"]
    if max_per_sector > 0:
        sector_counts: Counter[str] = Counter()
        capped_buys: List[GapFillPick] = []
        for pick in buys:
            sector = pick.sector or "—"
            if sector_counts[sector] >= max_per_sector:
                continue
            capped_buys.append(pick)
            sector_counts[sector] += 1
            if len(capped_buys) >= top_n:
                break
        buys = capped_buys
    else:
        buys = buys[:top_n]

    result = buys + sells
    result.sort(key=lambda p: (p.gap_age, -abs(p.signal.gap_pct)))
    _log(
        f"{STRATEGY_NAME}: {len(buys)} DOWN/BUY (max {max_per_sector}/sector) + {len(sells)} UP/SELL "
        f"in last {max_age} days (checked {n_checked}, no gap {n_reject})"
    )

    snapshot_path = config.get("gap_fill_screener_snapshot_path")
    if snapshot_path:
        rows = []
        for i, p in enumerate(result, 1):
            s = p.signal
            rows.append({
                "rank": i,
                "symbol": s.symbol,
                "ticker": s.symbol.replace(".NS", "").replace(".BO", ""),
                "stock_name": p.stock_name,
                "sector": p.sector,
                "direction": s.direction,
                "gap_age": s.gap_age,
                "gap_pct": s.gap_pct,
                "fill_pct": s.fill_pct,
                "close": s.close,
                "rsi": s.rsi,
                "gap_low": s.gap_low,
                "gap_high": s.gap_high,
                "fill_target": s.fill_target,
                "remark": s.remark,
            })
        save_screener_snapshot(snapshot_path, {
            "strategy_id": STRATEGY_ID,
            "strategy_name": STRATEGY_NAME,
            "version": STRATEGY_VERSION,
            "filters": {
                "max_age": max_age,
                "min_pct": config.get("gap_fill_min_pct"),
                "max_fill_pct": config.get("gap_fill_max_progress"),
                "directions": directions,
                "exclude_today": config.get("gap_fill_exclude_today", True),
                "max_per_sector": max_per_sector,
            },
            "checked": n_checked,
            "total_hits": len(picks),
            "picks": rows,
        })

    return result


__all__ = ["GapFillPick", "screen_gap_fill", "STRATEGY_ID", "STRATEGY_NAME"]
