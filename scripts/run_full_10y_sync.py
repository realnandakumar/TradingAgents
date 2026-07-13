"""One-time full 10-year OHLCV sync for the trading universe into prices.db + CSV."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.dataflows.ohlcv_store import migrate_legacy_cache, sync_price_cache
from tradingagents.dataflows.sync_symbols import collect_sync_symbols


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Full 10y price sync (SQLite prices.db + per-symbol CSV)"
    )
    parser.add_argument(
        "--migrate-legacy",
        action="store_true",
        help="Merge legacy *-YFin-data-*.csv files into canonical store first",
    )
    parser.add_argument(
        "--period",
        default="10y",
        help="Yahoo history window (default: 10y)",
    )
    args = parser.parse_args()

    config = DEFAULT_CONFIG.copy()
    cache_dir = config.get("data_cache_dir")

    if args.migrate_legacy:
        n = migrate_legacy_cache(cache_dir)
        print(f"Migrated {n} legacy cache file(s)")

    symbols = collect_sync_symbols(config)
    print(f"Full sync: {len(symbols)} tickers, period={args.period} -> prices.db + CSV...")
    report = sync_price_cache(
        symbols,
        mode="full",
        period=args.period,
        cache_dir=cache_dir,
    )
    print(
        f"Done: synced={report.synced} skipped={report.skipped} "
        f"failed={report.failed} total={report.symbols_total}"
    )
    if report.errors:
        print("Errors (first 20):")
        for err in report.errors[:20]:
            print(f"  {err}")
        if len(report.errors) > 20:
            print(f"  ... and {len(report.errors) - 20} more")


if __name__ == "__main__":
    main()
