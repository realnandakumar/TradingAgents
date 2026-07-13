import time
import logging
import tempfile

import pandas as pd
import yfinance as yf
from yfinance.exceptions import YFRateLimitError
from stockstats import wrap
from typing import Annotated
import os
from .config import get_config
from .ohlcv_store import read_bars, sync_symbol
from .utils import safe_ticker_component, symbol_cache_filename

logger = logging.getLogger(__name__)


def _atomic_write_csv(data: pd.DataFrame, data_file: str) -> None:
    """Write ``data`` to ``data_file`` atomically using a *unique* temp file.

    A shared ``{data_file}.tmp`` name caused a race: when two tool calls for
    the same symbol fetched concurrently (the ToolNode can run get_stock_data
    and get_indicators in parallel), both wrote the same temp path and the
    second ``os.replace`` hit ``FileNotFoundError`` after the first consumed
    it. ``mkstemp`` gives each writer its own temp file in the same directory,
    keeping the final replace atomic and collision-free.
    """
    directory = os.path.dirname(data_file) or "."
    fd, tmp_file = tempfile.mkstemp(dir=directory, suffix=".tmp")
    os.close(fd)
    try:
        data.to_csv(tmp_file, index=False, encoding="utf-8")
        os.replace(tmp_file, data_file)
    except BaseException:
        try:
            os.remove(tmp_file)
        except OSError:
            pass
        raise


def yf_retry(func, max_retries=3, base_delay=2.0):
    """Execute a yfinance call with exponential backoff on rate limits.

    yfinance raises YFRateLimitError on HTTP 429 responses but does not
    retry them internally. This wrapper adds retry logic specifically
    for rate limits. Other exceptions propagate immediately.
    """
    for attempt in range(max_retries + 1):
        try:
            return func()
        except YFRateLimitError:
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                logger.warning(f"Yahoo Finance rate limited, retrying in {delay:.0f}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(delay)
            else:
                raise


def _clean_dataframe(data: pd.DataFrame) -> pd.DataFrame:
    """Normalize a stock DataFrame for stockstats: parse dates, drop invalid rows, fill price gaps."""
    if "Date" not in data.columns:
        candidate_date_cols = ["index", "Datetime", "datetime", "date"]
        found_col = next((c for c in candidate_date_cols if c in data.columns), None)
        if found_col is not None:
            data = data.rename(columns={found_col: "Date"})
        else:
            raise KeyError("Date")

    data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
    data = data.dropna(subset=["Date"])

    price_cols = [c for c in ["Open", "High", "Low", "Close", "Volume"] if c in data.columns]
    data[price_cols] = data[price_cols].apply(pd.to_numeric, errors="coerce")
    data = data.dropna(subset=["Close"])
    data[price_cols] = data[price_cols].ffill().bfill()

    return data


def load_ohlcv(symbol: str, curr_date: str) -> pd.DataFrame:
    """Fetch OHLCV data with caching, filtered to prevent look-ahead bias.

    Reads from the canonical OHLCV store and incrementally syncs from Yahoo
    when data is missing or stale. Rows after *curr_date* are filtered out
    so backtests never see future prices.
    """
    symbol_cache_filename(symbol)

    config = get_config()
    cache_dir = config["data_cache_dir"]
    curr_date_dt = pd.to_datetime(curr_date)

    os.makedirs(cache_dir, exist_ok=True)
    data = read_bars(symbol, cache_dir=cache_dir)

    today = pd.Timestamp.today().normalize()
    cutoff = today - pd.Timedelta(days=2)
    last_bar = pd.to_datetime(data["Date"].iloc[-1]).normalize() if not data.empty else None
    if data.empty or last_bar is None or last_bar <= cutoff:
        sync_symbol(symbol, mode="incremental", period="5y", cache_dir=cache_dir)
        data = read_bars(symbol, cache_dir=cache_dir)

    data = _clean_dataframe(data)
    data = data[data["Date"] <= curr_date_dt]
    return data


def filter_financials_by_date(data: pd.DataFrame, curr_date: str) -> pd.DataFrame:
    """Drop financial statement columns (fiscal period timestamps) after curr_date.

    yfinance financial statements use fiscal period end dates as columns.
    Columns after curr_date represent future data and are removed to
    prevent look-ahead bias.
    """
    if not curr_date or data.empty:
        return data
    cutoff = pd.Timestamp(curr_date)
    mask = pd.to_datetime(data.columns, errors="coerce") <= cutoff
    return data.loc[:, mask]


class StockstatsUtils:
    @staticmethod
    def get_stock_stats(
        symbol: Annotated[str, "ticker symbol for the company"],
        indicator: Annotated[
            str, "quantitative indicators based off of the stock data for the company"
        ],
        curr_date: Annotated[
            str, "curr date for retrieving stock price data, YYYY-mm-dd"
        ],
    ):
        data = load_ohlcv(symbol, curr_date)
        df = wrap(data)
        df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
        curr_date_str = pd.to_datetime(curr_date).strftime("%Y-%m-%d")

        df[indicator]  # trigger stockstats to calculate the indicator
        matching_rows = df[df["Date"].str.startswith(curr_date_str)]

        if not matching_rows.empty:
            indicator_value = matching_rows[indicator].values[0]
            return indicator_value
        else:
            return "N/A: Not a trading day (weekend or holiday)"
