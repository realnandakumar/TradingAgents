"""Universe screener for Gap Fill setups."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

import pandas as pd

from tradingagents.screening.gap_fill_engine import (
    STRATEGY_ID,
    STRATEGY_NAME,
    GapFillSignal,
    evaluate_gap_fill,
)
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
        allow_download=False,
    )

    period = config.get("gap_fill_history_period", "1y")
    if price_data is None:
        _log(f"Downloading {period} history for {len(universe)} tickers...")
        from tradingagents.screening.prices import download_history

        price_data = download_history(universe, period=period)

    max_age = int(config.get("gap_fill_max_age", 30))
    top_n = int(config.get("gap_fill_top_n", 20))
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
    _log(
        f"{STRATEGY_NAME}: {len(picks)} active gap(s) in last {max_age} days "
        f"(checked {n_checked}, no gap {n_reject})"
    )
    return picks[:top_n]


__all__ = ["GapFillPick", "screen_gap_fill", "STRATEGY_ID", "STRATEGY_NAME"]
