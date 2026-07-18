"""Universe screener for confirmed Japanese candlestick setups."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

import pandas as pd

from tradingagents.screening.candle_engine import (
    PATTERN_CATALOG,
    STRATEGY_ID,
    STRATEGY_NAME,
    STRATEGY_VERSION,
    CandleSignal,
    scan_candlesticks,
)
from tradingagents.screening.screener_snapshot import save_screener_snapshot
from tradingagents.screening.universe import load_universe, load_universe_metadata

logger = logging.getLogger(__name__)


@dataclass
class CandlePick:
    signal: CandleSignal
    stock_name: str = ""
    sector: str = ""


def group_candle_picks(picks: List[CandlePick]) -> List[tuple[str, List[CandlePick]]]:
    by_id: Dict[str, List[CandlePick]] = {}
    for pick in picks:
        by_id.setdefault(pick.signal.pattern_id, []).append(pick)

    grouped: List[tuple[str, List[CandlePick]]] = []
    for pattern_id in PATTERN_CATALOG:
        group = by_id.get(pattern_id)
        if not group:
            continue
        group.sort(key=lambda p: (-p.signal.actionability_score, p.signal.pattern_age))
        grouped.append((pattern_id, group))
    return grouped


def screen_candlesticks(
    config: dict,
    progress: Optional[Callable[[str], None]] = None,
    price_data: Optional[Dict[str, pd.DataFrame]] = None,
) -> List[CandlePick]:
    """Screen the NSE universe for freshly confirmed candlestick patterns."""

    def _log(msg: str) -> None:
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

    period = config.get("candle_history_period", "1y")
    if price_data is None:
        _log(f"Downloading {period} history for {len(universe)} tickers...")
        from tradingagents.screening.prices import download_history

        price_data = download_history(universe, period=period)

    top_n = int(config.get("candle_top_n", 40))
    bullish_only = bool(config.get("candle_bullish_only", False))
    bearish_only = bool(config.get("candle_bearish_only", False))

    picks: List[CandlePick] = []
    n_checked = 0
    n_hits = 0

    for sym in universe:
        df = price_data.get(sym)
        if df is None:
            continue
        n_checked += 1
        hits = scan_candlesticks(df, config, symbol=sym)
        if not hits:
            continue

        meta = metadata.get(sym, {})
        name = meta.get("name") or sym.replace(".NS", "").replace(".BO", "")
        sector = meta.get("sector") or "—"

        for hit in hits:
            if bullish_only and hit.bias != "BULLISH":
                continue
            if bearish_only and hit.bias != "BEARISH":
                continue
            hit.stock_name = name
            hit.sector = sector
            picks.append(CandlePick(signal=hit, stock_name=name, sector=sector))
            n_hits += 1

    grouped = group_candle_picks(picks)
    capped: List[CandlePick] = []
    for _, group in grouped:
        capped.extend(group[:top_n])

    _log(
        f"{STRATEGY_NAME}: {n_hits} hit(s) across {len(picks)} row(s) "
        f"in {len(grouped)} pattern table(s) (checked {n_checked} tickers)"
    )

    snapshot_path = config.get("candle_screener_snapshot_path")
    if snapshot_path:
        groups_out = []
        for pattern_id, group in grouped:
            meta = PATTERN_CATALOG[pattern_id]
            rows = []
            for i, p in enumerate(group[:top_n], 1):
                s = p.signal
                rows.append(
                    {
                        "rank": i,
                        "symbol": s.symbol,
                        "ticker": s.symbol.replace(".NS", "").replace(".BO", ""),
                        "stock_name": p.stock_name,
                        "sector": p.sector,
                        "pattern_id": s.pattern_id,
                        "pattern_name": s.pattern_name,
                        "bias": s.bias,
                        "reliability": s.reliability,
                        "pattern_age": s.pattern_age,
                        "setup_status": s.setup_status,
                        "distance_to_trigger_pct": s.distance_to_trigger_pct,
                        "actionability_score": s.actionability_score,
                        "confidence": s.confidence,
                        "close": s.close,
                        "entry_level": s.entry_level,
                        "stop_loss": s.stop_loss,
                        "target_1": s.target_1,
                        "target_2": s.target_2,
                        "risk_reward_ratio": s.risk_reward_ratio,
                        "levels_valid": s.levels_valid,
                        "detail": s.detail,
                        "pattern_window_start": s.pattern_window_start,
                        "pattern_window_end": s.pattern_window_end,
                    }
                )
            groups_out.append(
                {
                    "pattern_id": pattern_id,
                    "pattern_name": meta["label"],
                    "bias": meta["bias"],
                    "stars": meta["stars"],
                    "count": len(rows),
                    "picks": rows,
                }
            )
        save_screener_snapshot(
            snapshot_path,
            {
                "strategy_id": STRATEGY_ID,
                "strategy_name": STRATEGY_NAME,
                "version": STRATEGY_VERSION,
                "filters": {
                    "require_confirm_bar": True,
                    "max_age_days": config.get("candle_max_age_days"),
                    "min_confidence": config.get("candle_min_confidence"),
                    "enabled": config.get("candle_enabled", "all"),
                },
                "checked": n_checked,
                "total_hits": n_hits,
                "group_count": len(groups_out),
                "groups": groups_out,
            },
        )

    return capped


__all__ = [
    "CandlePick",
    "group_candle_picks",
    "screen_candlesticks",
    "STRATEGY_ID",
    "STRATEGY_NAME",
    "STRATEGY_VERSION",
]
