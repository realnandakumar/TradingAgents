"""SuperTrend + RSI universe screener."""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from tradingagents.screening.prices import download_history
from tradingagents.screening.supertrend_rsi_engine import (
    STRATEGY_ID,
    STRATEGY_NAME,
    SuperTrendRSISignal,
    evaluate_supertrend_rsi,
)
from tradingagents.screening.swing_screener import _CRORE, _fetch_market_caps
from tradingagents.screening.universe import load_universe, load_universe_metadata

logger = logging.getLogger(__name__)


@dataclass
class SuperTrendRSIPick:
    signal: SuperTrendRSISignal
    market_cap_cr: Optional[float] = None
    avg_traded_value_cr: Optional[float] = None

    @property
    def symbol(self) -> str:
        return self.signal.symbol

    @property
    def direction(self) -> str:
        return self.signal.direction

    @property
    def score(self) -> int:
        return self.signal.score


def screen_supertrend_rsi(
    config: dict,
    progress: Optional[Callable[[str], None]] = None,
    price_data: Optional[Dict[str, "pd.DataFrame"]] = None,
) -> List[SuperTrendRSIPick]:
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
    )

    period = config.get("strsi_history_period", "1y")
    if price_data is None:
        _log(f"Downloading {period} history for {len(universe)} tickers...")
        price_data = download_history(universe, period=period)

    min_cap_inr = float(config.get("strsi_min_market_cap_cr", 500.0)) * _CRORE
    min_traded_inr = float(config.get("strsi_min_avg_traded_value_cr", 1.0)) * _CRORE
    min_score = int(config.get("strsi_min_score", 0))

    candidates: List[tuple[str, SuperTrendRSISignal, float]] = []

    for sym in universe:
        df = price_data.get(sym)
        if df is None:
            continue
        sig = evaluate_supertrend_rsi(df, config, symbol=sym)
        if sig.rejected or sig.direction == "NONE":
            continue
        if min_score > 0 and sig.score < min_score:
            continue
        traded = float((df["Close"].iloc[-20:] * df["Volume"].iloc[-20:]).mean())
        if traded < min_traded_inr:
            continue
        meta = metadata.get(sym, {})
        sig.stock_name = meta.get("name") or sym.replace(".NS", "")
        sig.sector = meta.get("sector") or "—"
        candidates.append((sym, sig, traded))

    _log(f"{len(candidates)} raw signal(s) before market-cap filter")

    if not candidates:
        return []

    caps = _fetch_market_caps([s for s, _, _ in candidates])
    picks: List[SuperTrendRSIPick] = []
    for sym, sig, traded in candidates:
        cap = caps.get(sym)
        if cap is None or cap < min_cap_inr:
            continue
        picks.append(
            SuperTrendRSIPick(
                signal=sig,
                market_cap_cr=round(cap / _CRORE, 1),
                avg_traded_value_cr=round(traded / _CRORE, 2),
            )
        )

    picks.sort(key=lambda p: p.score, reverse=True)
    top_n = int(config.get("strsi_top_n", 20))
    max_per_sector = int(config.get("strsi_max_per_sector", 4))
    total = len(picks)

    # Keep all SELL signals (used to close open longs); sector-cap BUY shortlist.
    sells = [p for p in picks if p.direction == "SELL"]
    buys = [p for p in picks if p.direction == "BUY"]
    if max_per_sector > 0:
        sector_counts: Counter[str] = Counter()
        capped_buys: List[SuperTrendRSIPick] = []
        for pick in buys:
            sector = (pick.signal.sector if pick.signal else None) or "—"
            if sector_counts[sector] >= max_per_sector:
                continue
            capped_buys.append(pick)
            sector_counts[sector] += 1
            if len(capped_buys) >= top_n:
                break
        buys = capped_buys
    else:
        buys = buys[:top_n]

    picks = buys + sells
    picks.sort(key=lambda p: p.score, reverse=True)
    _log(
        f"{total} signal(s) after filters; "
        f"{len(buys)} BUY (max {max_per_sector}/sector) + {len(sells)} SELL"
    )
    return picks


def explain_supertrend_rsi(
    symbol: str,
    config: dict,
) -> SuperTrendRSISignal:
    """Full signal breakdown for one ticker (including rejected/filtered)."""
    sym = symbol.upper().strip()
    if not sym.endswith(".NS") and not sym.endswith(".BO"):
        sym = f"{sym}.NS"

    metadata = load_universe_metadata(
        csv_path=config.get("screen_universe_csv"),
        cache_dir=config.get("data_cache_dir"),
    )
    meta = metadata.get(sym, {})
    period = config.get("strsi_history_period", "1y")
    data = download_history([sym], period=period)
    df = data.get(sym)
    if df is None:
        return SuperTrendRSISignal(
            symbol=sym,
            direction="NONE",
            score=0,
            grade="Ignore",
            grade_stars="★",
            rejected=True,
            reject_reason="no price history",
            stock_name=meta.get("name") or sym.replace(".NS", ""),
            sector=meta.get("sector") or "—",
        )

    sig = evaluate_supertrend_rsi(df, config, symbol=sym)
    sig.stock_name = meta.get("name") or sym.replace(".NS", "")
    sig.sector = meta.get("sector") or "—"
    return sig
