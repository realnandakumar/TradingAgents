"""CLI to sync the canonical daily OHLCV price cache from Yahoo Finance."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.dataflows.ohlcv_store import migrate_legacy_cache, sync_price_cache
from tradingagents.dataflows.sync_symbols import collect_sync_symbols


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync canonical OHLCV price cache")
    parser.add_argument(
        "--mode",
        choices=["incremental", "full"],
        default="incremental",
        help="incremental: fetch tail when stale; full: re-download period",
    )
    parser.add_argument(
        "--period",
        default="5y",
        help="History window for full sync or cold-start incremental (default: 5y)",
    )
    parser.add_argument(
        "--migrate-legacy",
        action="store_true",
        help="Merge legacy *-YFin-data-*.csv files into canonical store first",
    )
    args = parser.parse_args()

    config = DEFAULT_CONFIG.copy()
    cache_dir = config.get("data_cache_dir")

    if args.migrate_legacy:
        n = migrate_legacy_cache(cache_dir)
        print(f"Migrated {n} legacy cache file(s)")

    symbols = collect_sync_symbols(config)
    print(f"Syncing {len(symbols)} tickers ({args.mode}, period={args.period})...")
    report = sync_price_cache(
        symbols,
        mode=args.mode,
        period=args.period,
        cache_dir=cache_dir,
    )
    print(
        f"Done: synced={report.synced} skipped={report.skipped} "
        f"failed={report.failed} total={report.symbols_total}"
    )
    if report.errors:
        print("Errors:")
        for err in report.errors[:20]:
            print(f"  {err}")
        if len(report.errors) > 20:
            print(f"  ... and {len(report.errors) - 20} more")


if __name__ == "__main__":
    main()
