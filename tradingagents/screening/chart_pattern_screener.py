"""Universe screener for classic chart pattern setups."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

import pandas as pd

from tradingagents.screening.chart_pattern_engine import (
    PATTERN_CATALOG,
    STRATEGY_ID,
    STRATEGY_NAME,
    STRATEGY_VERSION,
    ChartPatternSignal,
    scan_chart_patterns,
)
from tradingagents.screening.screener_snapshot import save_screener_snapshot
from tradingagents.screening.universe import load_universe, load_universe_metadata

logger = logging.getLogger(__name__)


@dataclass
class ChartPatternPick:
    signal: ChartPatternSignal
    stock_name: str = ""
    sector: str = ""

    @property
    def symbol(self) -> str:
        return self.signal.symbol

    @property
    def pattern_id(self) -> str:
        return self.signal.pattern_id

    @property
    def bias(self) -> str:
        return self.signal.bias

    @property
    def remark(self) -> str:
        return self.signal.remark


def group_chart_pattern_picks(
    picks: List[ChartPatternPick],
) -> List[tuple[str, List[ChartPatternPick]]]:
    """Group picks by pattern id in catalog order (reliability tier)."""
    by_id: Dict[str, List[ChartPatternPick]] = {}
    for pick in picks:
        by_id.setdefault(pick.pattern_id, []).append(pick)

    grouped: List[tuple[str, List[ChartPatternPick]]] = []
    for pattern_id in PATTERN_CATALOG:
        group = by_id.get(pattern_id)
        if not group:
            continue
        group.sort(
            key=lambda p: (
                -p.signal.actionability_score,
                p.signal.distance_to_trigger_pct,
                p.signal.pattern_age,
            )
        )
        grouped.append((pattern_id, group))
    return grouped


def screen_chart_patterns(
    config: dict,
    progress: Optional[Callable[[str], None]] = None,
    price_data: Optional[Dict[str, pd.DataFrame]] = None,
) -> List[ChartPatternPick]:
    """Screen the NSE universe for active chart patterns on daily charts."""

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

    period = config.get("chart_pattern_history_period", "2y")
    if price_data is None:
        _log(f"Downloading {period} history for {len(universe)} tickers...")
        from tradingagents.screening.prices import download_history

        price_data = download_history(universe, period=period)

    top_n = int(config.get("chart_pattern_top_n", 100))
    bullish_only = bool(config.get("chart_pattern_bullish_only", False))
    bearish_only = bool(config.get("chart_pattern_bearish_only", False))

    picks: List[ChartPatternPick] = []
    n_checked = 0
    n_hits = 0

    for sym in universe:
        df = price_data.get(sym)
        if df is None:
            continue
        n_checked += 1
        hits = scan_chart_patterns(df, config, symbol=sym)
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
            picks.append(ChartPatternPick(signal=hit, stock_name=name, sector=sector))
            n_hits += 1

    grouped = group_chart_pattern_picks(picks)
    capped: List[ChartPatternPick] = []
    for _, group in grouped:
        capped.extend(group[:top_n])

    _log(
        f"{STRATEGY_NAME}: {n_hits} pattern hit(s) across {len(picks)} row(s) "
        f"in {len(grouped)} pattern table(s) (checked {n_checked} tickers)"
    )

    snapshot_path = config.get("chart_pattern_screener_snapshot_path")
    if snapshot_path:
        groups_out = []
        for pattern_id, group in grouped:
            meta = PATTERN_CATALOG[pattern_id]
            capped_group = group[:top_n]
            rows = []
            for i, p in enumerate(capped_group, 1):
                s = p.signal
                row = {
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
                    "trigger_level": s.trigger_level,
                    "support_level": s.support_level,
                    "resistance_level": s.resistance_level,
                    "detail": s.detail,
                    "entry_level": s.entry_level,
                    "stop_loss": s.stop_loss,
                    "target_1": s.target_1,
                    "target_2": s.target_2,
                    "risk_reward_ratio": s.risk_reward_ratio,
                    "risk_reward_market": s.risk_reward_market,
                    "entry_type": s.entry_type,
                    "market_entry": s.market_entry,
                    "measured_move": s.measured_move,
                    "levels_valid": s.levels_valid,
                    "geometry_lines": s.geometry_lines,
                    "pattern_window_start": s.pattern_window_start,
                    "pattern_window_end": s.pattern_window_end,
                    "pivots": s.pivots,
                }
                rows.append(row)
            groups_out.append({
                "pattern_id": pattern_id,
                "pattern_name": meta["label"],
                "bias": meta["bias"],
                "stars": meta["stars"],
                "count": len(rows),
                "picks": rows,
            })
        save_screener_snapshot(snapshot_path, {
            "strategy_id": STRATEGY_ID,
            "strategy_name": STRATEGY_NAME,
            "version": STRATEGY_VERSION,
            "filters": {
                "max_age_days": config.get("chart_pattern_max_age_days"),
                "max_distance_to_trigger_pct": config.get("chart_pattern_max_distance_to_trigger_pct"),
                "min_confidence": config.get("chart_pattern_min_confidence"),
                "exclude_today": config.get("chart_pattern_exclude_today", True),
            },
            "checked": n_checked,
            "total_hits": n_hits,
            "group_count": len(groups_out),
            "groups": groups_out,
        })

    return capped


__all__ = [
    "ChartPatternPick",
    "group_chart_pattern_picks",
    "screen_chart_patterns",
    "STRATEGY_ID",
    "STRATEGY_NAME",
]
