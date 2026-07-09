"""Universe screener for LuxAlgo Nadaraya-Watson Envelope contrarian crosses."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

import pandas as pd

from tradingagents.screening.nw_envelope_engine import (
    STRATEGY_ID,
    STRATEGY_NAME,
    NwEnvelopeSignal,
    evaluate_nw_envelope,
)
from tradingagents.screening.prices import download_history
from tradingagents.screening.universe import load_universe, load_universe_metadata

logger = logging.getLogger(__name__)


@dataclass
class NwEnvelopePick:
    signal: NwEnvelopeSignal
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


def screen_nw_envelope(
    config: dict,
    progress: Optional[Callable[[str], None]] = None,
    price_data: Optional[Dict[str, pd.DataFrame]] = None,
) -> List[NwEnvelopePick]:
    """Screen the NSE universe for NWE contrarian crosses within max age."""

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

    period = config.get("nwe_history_period", "2y")
    if price_data is None:
        _log(f"Downloading {period} history for {len(universe)} tickers...")
        price_data = download_history(universe, period=period)

    max_age = int(config.get("nwe_cross_max_age", 3))
    top_n = int(config.get("nwe_top_n", 20))
    directions = str(config.get("nwe_directions", "BUY")).upper()
    allow_buy = "BUY" in directions
    allow_sell = "SELL" in directions

    picks: List[NwEnvelopePick] = []
    n_checked = 0
    n_reject = 0

    for sym in universe:
        df = price_data.get(sym)
        if df is None:
            continue
        n_checked += 1
        sig = evaluate_nw_envelope(df, config, symbol=sym)
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
        picks.append(NwEnvelopePick(signal=sig, stock_name=name, sector=sector))

    picks.sort(key=lambda p: (p.cross_age, -abs(p.signal.dist_pct)))
    _log(
        f"{STRATEGY_NAME}: {len(picks)} crossover(s) in last {max_age} days "
        f"(checked {n_checked}, rejected {n_reject})"
    )
    return picks[:top_n]


__all__ = ["NwEnvelopePick", "screen_nw_envelope", "STRATEGY_ID", "STRATEGY_NAME"]
