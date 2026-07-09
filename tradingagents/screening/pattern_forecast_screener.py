"""Universe screener for Pattern Forecast v1."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

import pandas as pd

from tradingagents.screening.pattern_forecast_engine import (
    STRATEGY_ID,
    STRATEGY_NAME,
    PatternForecastSignal,
    evaluate_pattern_forecast,
    nifty_regime_ok,
)
from tradingagents.screening.prices import download_history
from tradingagents.screening.universe import load_universe, load_universe_metadata

logger = logging.getLogger(__name__)


@dataclass
class PatternForecastPick:
    signal: PatternForecastSignal
    stock_name: str = ""
    sector: str = ""

    @property
    def symbol(self) -> str:
        return self.signal.symbol

    @property
    def direction(self) -> str:
        return self.signal.direction

    @property
    def probability(self) -> float:
        return self.signal.probability

    @property
    def composite_score(self) -> float:
        return self.signal.composite_score

    @property
    def remark(self) -> str:
        return self.signal.remark


def screen_pattern_forecast(
    config: dict,
    progress: Optional[Callable[[str], None]] = None,
    price_data: Optional[Dict[str, pd.DataFrame]] = None,
    benchmark_df: Optional[pd.DataFrame] = None,
) -> List[PatternForecastPick]:
    """Screen NSE universe; return top-N picks ranked by correlation strength."""

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

    period = config.get("pattern_forecast_history_period", "2y")
    benchmark = config.get("paper_benchmark", "^NSEI")

    if benchmark_df is None and price_data is not None:
        benchmark_df = price_data.get(benchmark)

    if price_data is None:
        _log(f"Downloading {period} history for {len(universe)} tickers + benchmark...")
        tickers = list(universe)
        if benchmark not in tickers:
            tickers.append(benchmark)
        price_data = download_history(tickers, period=period)
        benchmark_df = price_data.get(benchmark)

    if bool(config.get("pattern_forecast_require_nifty_above_ma", True)):
        ma = int(config.get("pattern_forecast_nifty_ma_period", 20))
        ok, note = nifty_regime_ok(benchmark_df, ma_period=ma)
        if not ok:
            _log(f"Nifty regime gate closed: {note}")
            return []

    top_n = int(config.get("pattern_forecast_top_n", 10))
    directions = str(config.get("pattern_forecast_directions", "UP")).upper()
    allow_up = "UP" in directions
    allow_down = "DOWN" in directions

    picks: List[PatternForecastPick] = []
    n_checked = 0
    n_reject = 0

    for sym in universe:
        if sym == benchmark:
            continue
        df = price_data.get(sym) if price_data else None
        if df is None:
            continue
        n_checked += 1
        sig = evaluate_pattern_forecast(df, config, symbol=sym, benchmark_df=benchmark_df)
        if sig.rejected or sig.direction == "NONE":
            n_reject += 1
            continue
        if sig.direction == "UP" and not allow_up:
            continue
        if sig.direction == "DOWN" and not allow_down:
            continue

        meta = metadata.get(sym, {})
        name = meta.get("name") or sym.replace(".NS", "").replace(".BO", "")
        sector = meta.get("sector") or "—"
        sig.stock_name = name
        sig.sector = sector
        picks.append(PatternForecastPick(signal=sig, stock_name=name, sector=sector))

    use_v17 = bool(config.get("pattern_forecast_use_v17", False))
    use_consensus = bool(config.get("pattern_forecast_use_consensus", True))
    if use_v17 or use_consensus or bool(config.get("pattern_forecast_bullish_only", True)):
        picks.sort(key=lambda p: p.composite_score, reverse=True)
    else:
        picks.sort(key=lambda p: p.signal.correlation, reverse=True)
    _log(
        f"{STRATEGY_NAME} v1.1: {len(picks)} candidate(s) "
        f"(checked {n_checked}, rejected {n_reject})"
    )
    return picks[:top_n]


__all__ = ["PatternForecastPick", "screen_pattern_forecast", "STRATEGY_ID", "STRATEGY_NAME"]
