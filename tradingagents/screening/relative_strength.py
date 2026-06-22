"""Relative Strength (RS) ranking versus a benchmark index.

"Relative strength" here is price momentum measured *against the market*: a
stock that rose more than the Nifty over the lookback is strong. We blend
multiple lookbacks (weighted toward recent action, IBD-style) so a stock that
is accelerating ranks above one that merely drifted up months ago.

Pure pandas/yfinance -- no LLM, fast and free.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd

from .prices import download_history

logger = logging.getLogger(__name__)

# (trading-day lookback, weight). Weights favour recent strength.
_RS_WINDOWS = [(21, 0.4), (63, 0.3), (126, 0.2), (252, 0.1)]


@dataclass
class RSResult:
    symbol: str
    rs_score: float          # blended excess return vs benchmark (e.g. 0.18 = +18%)
    rs_rank: int             # 1 = strongest
    rs_percentile: float     # 0-100, 100 = strongest
    close: float             # latest close (entry-price reference)
    ret_blended: float       # stock's own blended return
    bench_blended: float     # benchmark's blended return


def _blended_return(close: pd.Series) -> Optional[float]:
    """Weighted multi-window trailing return; None if too little history."""
    if len(close) < 22:  # need at least the shortest window + 1
        return None
    total_w = 0.0
    acc = 0.0
    last = float(close.iloc[-1])
    for window, weight in _RS_WINDOWS:
        if len(close) <= window:
            continue
        past = float(close.iloc[-(window + 1)])
        if past <= 0:
            continue
        acc += weight * (last / past - 1.0)
        total_w += weight
    if total_w == 0:
        return None
    return acc / total_w


def compute_relative_strength(
    tickers: List[str],
    benchmark: str = "^NSEI",
    period: str = "1y",
    price_data: Optional[Dict[str, pd.DataFrame]] = None,
) -> List[RSResult]:
    """Compute RS for each ticker vs ``benchmark`` and return them ranked.

    Args:
        tickers: ``.NS`` symbols to rank.
        benchmark: index symbol for the market baseline (Nifty 50 by default).
        period: yfinance history window to download.
        price_data: pre-downloaded ``{symbol: DataFrame}`` to reuse (the batch
            runner downloads once and shares it across RS + pattern scoring).
            When provided, only the benchmark is fetched here.

    Returns RSResults sorted strongest-first.
    """
    if price_data is None:
        price_data = download_history(tickers, period=period)

    bench_data = download_history([benchmark], period=period)
    bench_df = bench_data.get(benchmark)
    bench_ret = _blended_return(bench_df["Close"]) if bench_df is not None else None
    if bench_ret is None:
        logger.warning("Benchmark %s unavailable; RS falls back to raw return", benchmark)
        bench_ret = 0.0

    results: List[RSResult] = []
    for sym in tickers:
        df = price_data.get(sym)
        if df is None:
            continue
        ret = _blended_return(df["Close"])
        if ret is None:
            continue
        results.append(
            RSResult(
                symbol=sym,
                rs_score=ret - bench_ret,
                rs_rank=0,  # filled after sort
                rs_percentile=0.0,
                close=float(df["Close"].iloc[-1]),
                ret_blended=ret,
                bench_blended=bench_ret,
            )
        )

    results.sort(key=lambda r: r.rs_score, reverse=True)
    n = len(results)
    for i, r in enumerate(results):
        r.rs_rank = i + 1
        r.rs_percentile = round(100.0 * (n - i) / n, 1) if n else 0.0
    return results


def rank_by_relative_strength(
    tickers: List[str],
    benchmark: str = "^NSEI",
    top_n: Optional[int] = None,
    min_percentile: float = 0.0,
    period: str = "1y",
    price_data: Optional[Dict[str, pd.DataFrame]] = None,
) -> List[RSResult]:
    """Convenience wrapper: compute RS then keep the strongest names.

    ``min_percentile`` keeps only stocks at/above that RS percentile (e.g. 70
    = top 30% strongest). ``top_n`` then caps the count.
    """
    ranked = compute_relative_strength(
        tickers, benchmark=benchmark, period=period, price_data=price_data
    )
    if min_percentile > 0:
        ranked = [r for r in ranked if r.rs_percentile >= min_percentile]
    if top_n is not None:
        ranked = ranked[:top_n]
    return ranked
