"""Universe screener for LuxAlgo TRAMA close crossovers."""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

import pandas as pd

from tradingagents.screening.prices import download_history
from tradingagents.screening.trama_engine import (
    STRATEGY_ID,
    STRATEGY_NAME,
    TramaSignal,
    evaluate_trama,
)
from tradingagents.screening.universe import load_universe, load_universe_metadata

logger = logging.getLogger(__name__)


@dataclass
class TramaPick:
    signal: TramaSignal
    stock_name: str = ""
    sector: str = ""

    @property
    def symbol(self) -> str:
        return self.signal.symbol

    @property
    def direction(self) -> str:
        return self.signal.direction

    @property
    def cross_age(self) -> int:
        return self.signal.cross_age

    @property
    def remark(self) -> str:
        return self.signal.remark


def screen_trama(
    config: dict,
    progress: Optional[Callable[[str], None]] = None,
    price_data: Optional[Dict[str, pd.DataFrame]] = None,
) -> List[TramaPick]:
    """Screen the NSE universe for TRAMA close crossovers within max age."""

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

    period = config.get("trama_history_period", "1y")
    if price_data is None:
        _log(f"Downloading {period} history for {len(universe)} tickers...")
        price_data = download_history(universe, period=period)

    max_age = int(config.get("trama_cross_max_age", 3))
    top_n = int(config.get("trama_top_n", 20))
    max_per_sector = int(config.get("trama_max_per_sector", 4))
    directions = str(config.get("trama_directions", "BUY,SELL")).upper()
    allow_buy = "BUY" in directions
    allow_sell = "SELL" in directions

    picks: List[TramaPick] = []
    n_checked = 0
    n_reject = 0

    for sym in universe:
        df = price_data.get(sym)
        if df is None:
            continue
        n_checked += 1
        sig = evaluate_trama(df, config, symbol=sym)
        if sig.rejected or sig.direction == "NONE":
            n_reject += 1
            continue
        if sig.direction == "BUY" and not allow_buy:
            continue
        if sig.direction == "SELL" and not allow_sell:
            continue

        meta = metadata.get(sym, {})
        name = meta.get("name") or sym.replace(".NS", "").replace(".BO", "")
        sector = meta.get("sector") or "—"
        sig.stock_name = name
        sig.sector = sector
        picks.append(TramaPick(signal=sig, stock_name=name, sector=sector))

    # Freshest first, then larger distance from TRAMA (stronger post-cross).
    picks.sort(key=lambda p: (p.cross_age, -abs(p.signal.dist_pct)))

    sells = [p for p in picks if p.direction == "SELL"]
    buys = [p for p in picks if p.direction == "BUY"]
    if max_per_sector > 0:
        sector_counts: Counter[str] = Counter()
        capped_buys: List[TramaPick] = []
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
    result.sort(key=lambda p: (p.cross_age, -abs(p.signal.dist_pct)))
    _log(
        f"{STRATEGY_NAME}: {len(buys)} BUY (max {max_per_sector}/sector) + {len(sells)} SELL "
        f"in last {max_age} days (checked {n_checked}, rejected {n_reject})"
    )
    return result


__all__ = ["TramaPick", "screen_trama", "STRATEGY_ID", "STRATEGY_NAME"]
