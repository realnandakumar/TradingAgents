"""NANDA Swing Scanner (NSS) — structure-first early swing screener."""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from tradingagents.screening.nss_pipeline import NSSSnapshot, StageResult, evaluate_nss
from tradingagents.screening.prices import download_history
from tradingagents.screening.swing_screener import (
    _CRORE,
    _fetch_market_caps,
)
from tradingagents.screening.universe import load_universe, load_universe_metadata

logger = logging.getLogger(__name__)


@dataclass
class NSSPick:
    symbol: str
    stock_name: str
    sector: str
    entry_price: float
    stop_loss: float
    target_1: float
    target_2: float
    stop_loss_pct: float
    target_1_pct: float
    target_2_pct: float
    risk_reward_ratio: float
    risk_reward_ratio_2: float
    composite_score: float
    confidence: str
    primary_reason: str
    rsi: float
    adx: float
    relative_volume: float
    range_pct: float
    atr_ratio: float
    risk_pct: float = 0.0
    market_cap_cr: Optional[float] = None
    avg_traded_value_cr: Optional[float] = None
    breakout_ok: bool = False
    volume_ok: bool = False
    stages: Dict[str, StageResult] = field(default_factory=dict)

    def stage_summary(self) -> str:
        return " · ".join(
            f"{k}:{'PASS' if s.passed else 'FAIL'}"
            for k, s in self.stages.items()
        )


def screen_nss(
    config: dict,
    progress: Optional[Callable[[str], None]] = None,
    price_data: Optional[Dict[str, "pd.DataFrame"]] = None,
) -> List[NSSPick]:
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

    period = config.get("nss_history_period", "2y")
    if price_data is None:
        _log(f"Downloading {period} history for {len(universe)} tickers...")
        price_data = download_history(universe, period=period)

    min_cap_inr = float(config.get("nss_min_market_cap_cr", 5000.0)) * _CRORE
    min_traded_inr = float(config.get("nss_min_avg_traded_value_cr", 10.0)) * _CRORE

    technical_hits: List[tuple[str, NSSSnapshot]] = []
    for sym in universe:
        df = price_data.get(sym)
        if df is None:
            continue
        snap = evaluate_nss(df, config)
        if snap is None:
            continue
        if snap.avg_traded_value_inr < min_traded_inr:
            continue
        technical_hits.append((sym, snap))

    _log(f"{len(technical_hits)} tickers pass NSS pipeline + liquidity")

    if not technical_hits:
        return []

    _log("Fetching market capitalizations...")
    caps = _fetch_market_caps([sym for sym, _ in technical_hits])

    picks: List[NSSPick] = []
    for sym, snap in technical_hits:
        cap = caps.get(sym)
        if cap is None or cap < min_cap_inr:
            continue
        meta = metadata.get(sym, {})
        picks.append(
            NSSPick(
                symbol=sym,
                stock_name=meta.get("name") or sym.replace(".NS", ""),
                sector=meta.get("sector") or "—",
                entry_price=snap.entry,
                stop_loss=snap.stop_loss,
                target_1=snap.target_1,
                target_2=snap.target_2,
                stop_loss_pct=snap.stop_loss_pct,
                target_1_pct=snap.target_1_pct,
                target_2_pct=snap.target_2_pct,
                risk_reward_ratio=snap.risk_reward_ratio,
                risk_reward_ratio_2=snap.risk_reward_ratio_2,
                composite_score=snap.composite_score,
                confidence=snap.confidence,
                primary_reason=snap.primary_reason,
                rsi=snap.rsi,
                adx=snap.adx,
                relative_volume=snap.relative_volume,
                range_pct=snap.range_pct,
                atr_ratio=snap.atr_ratio,
                risk_pct=snap.risk_pct,
                market_cap_cr=round(cap / _CRORE, 1),
                avg_traded_value_cr=round(snap.avg_traded_value_inr / _CRORE, 2),
                breakout_ok=snap.breakout_ok,
                volume_ok=snap.volume_ok,
                stages=snap.stages,
            )
        )

    picks.sort(key=lambda p: p.composite_score, reverse=True)
    top_n = int(config.get("nss_top_n", 20))
    total = len(picks)
    max_per_sector = int(config.get("nss_max_per_sector", 4))
    if max_per_sector > 0:
        sector_counts: Counter[str] = Counter()
        capped: List[NSSPick] = []
        for pick in picks:
            sector = pick.sector or "—"
            if sector_counts[sector] >= max_per_sector:
                continue
            capped.append(pick)
            sector_counts[sector] += 1
            if len(capped) >= top_n:
                break
        picks = capped
    else:
        picks = picks[:top_n]
    _log(
        f"{total} NSS candidate(s) after market-cap filter; "
        f"showing top {len(picks)} with max {max_per_sector} per sector"
    )
    return picks
