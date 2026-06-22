"""Batch daily-price download for screening.

Screening needs cheap, bulk OHLCV history for hundreds of tickers at once,
which is a different access pattern from the per-ticker tool calls in
``dataflows``. We use yfinance's bulk download and normalise the awkward
multi-index result into a plain ``{symbol: DataFrame}`` mapping.
"""

from __future__ import annotations

import logging
from typing import Dict, List

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


def download_history(
    tickers: List[str],
    period: str = "1y",
    interval: str = "1d",
    batch_size: int = 100,
) -> Dict[str, pd.DataFrame]:
    """Return ``{symbol: OHLCV DataFrame}`` for the given tickers.

    Tickers with no data (delisted, bad symbol, network gap) are simply
    omitted from the result rather than raising, so a few bad symbols never
    sink a whole screen. Columns are normalised to
    ``Open/High/Low/Close/Volume`` with a tz-naive DatetimeIndex.
    """
    out: Dict[str, pd.DataFrame] = {}
    if not tickers:
        return out

    for start in range(0, len(tickers), batch_size):
        batch = tickers[start : start + batch_size]
        try:
            raw = yf.download(
                batch,
                period=period,
                interval=interval,
                group_by="ticker",
                auto_adjust=True,
                progress=False,
                threads=True,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("yfinance batch download failed (%s); skipping batch", e)
            continue

        if raw is None or raw.empty:
            continue

        for sym in batch:
            df = _extract(raw, sym)
            if df is not None:
                out[sym] = df

    return out


def _extract(raw: pd.DataFrame, symbol: str):
    """Pull one ticker's OHLCV frame out of a yfinance download result.

    yfinance returns MultiIndex columns even for a single ticker. The ticker
    can sit on either column level depending on ``group_by`` and version, so
    we locate it on whichever level it appears."""
    cols = raw.columns
    if not isinstance(cols, pd.MultiIndex):
        # Flat columns: a true single-ticker frame already (Open/High/...).
        return _clean(raw)

    for level in range(cols.nlevels):
        if symbol in cols.get_level_values(level):
            df = raw.xs(symbol, axis=1, level=level)
            return _clean(df)
    return None


def _clean(df: pd.DataFrame):
    """Drop empty frames and tz info; require a usable Close column."""
    if df is None or df.empty or "Close" not in df.columns:
        return None
    df = df.dropna(subset=["Close"])
    if len(df) < 2:
        return None
    if df.index.tz is not None:
        df = df.copy()
        df.index = df.index.tz_localize(None)
    return df
