"""Ensure a single ticker is synced in the canonical OHLCV store."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.dataflows.ohlcv_store import read_bars, sync_symbol
from tradingagents.screening.universe import _normalise_symbol


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync one ticker into the price cache")
    parser.add_argument("ticker", help="Ticker symbol (e.g. RELIANCE or RELIANCE.NS)")
    parser.add_argument(
        "--mode",
        choices=["incremental", "full"],
        default="incremental",
        help="Sync mode (default: incremental)",
    )
    parser.add_argument(
        "--period",
        default="5y",
        help="History window for full sync or cold-start incremental",
    )
    args = parser.parse_args()

    symbol = _normalise_symbol(args.ticker)
    if not symbol:
        print("Invalid ticker", file=sys.stderr)
        sys.exit(1)

    config = DEFAULT_CONFIG.copy()
    cache_dir = config.get("data_cache_dir")

    report = sync_symbol(
        symbol,
        mode=args.mode,
        period=args.period,
        cache_dir=cache_dir,
    )
    bars = read_bars(symbol, cache_dir=cache_dir)
    last_bar = None
    if not bars.empty:
        last_bar = bars["Date"].iloc[-1].strftime("%Y-%m-%d")

    if report.synced:
        print(f"Synced {symbol} ({len(bars)} bars, last={last_bar})")
    elif report.skipped:
        print(f"Up to date {symbol} ({len(bars)} bars, last={last_bar})")
    else:
        print(f"Failed to sync {symbol}", file=sys.stderr)
        for err in report.errors:
            print(f"  {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
