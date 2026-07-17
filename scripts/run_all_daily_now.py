"""Run all daily paper-trade jobs from a single shared price store.

When the EOD pipeline already ran today, skips re-sync and reads from cache.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.gap_fill import run_gap_fill_daily
from tradingagents.momentum import run_momentum_daily
from tradingagents.nss import run_nss_daily
from tradingagents.dataflows.ohlcv_store import manifest_eod_ran_today, sync_price_cache
from tradingagents.dataflows.sync_symbols import collect_sync_symbols
from tradingagents.screening.prices import read_history
from tradingagents.nw_envelope import run_nw_envelope_daily
from tradingagents.pattern_forecast import run_pattern_forecast_daily
from tradingagents.supertrend_rsi import run_supertrend_rsi_daily
from tradingagents.swing import run_swing_daily
from tradingagents.tech_desk import run_tech_desk_daily
from tradingagents.trama import run_trama_daily

SHARED_PERIOD = "2y"


def _summary(name: str, report: dict) -> None:
    if report.get("skipped"):
        print(f"  {name:<16} skipped ({report.get('reason')})")
        return
    print(
        f"  {name:<16} picks={report.get('screener_picks', 0):<3} "
        f"opened={len(report.get('opened', []))} "
        f"exits={len(report.get('exits', []))} "
        f"open_now={report.get('open_positions', 0)} "
        f"pending={len(report.get('proposals', []))}"
    )


def main() -> None:
    config = DEFAULT_CONFIG.copy()
    cache_dir = config.get("data_cache_dir")
    symbols = collect_sync_symbols(config)

    if manifest_eod_ran_today(cache_dir):
        print(f"EOD ran today — skipping sync, loading {SHARED_PERIOD} history for {len(symbols)} tickers...")
    else:
        print(f"Syncing price cache (incremental) for {len(symbols)} tickers...")
        sync_report = sync_price_cache(
            symbols,
            mode="incremental",
            cache_dir=cache_dir,
        )
        print(
            f"Cache sync: synced={sync_report.synced} skipped={sync_report.skipped} "
            f"failed={sync_report.failed}"
        )
        print(f"Loading {SHARED_PERIOD} history from cache...")

    price_data = read_history(symbols, period=SHARED_PERIOD, cache_dir=cache_dir)
    print(f"Got usable history for {len(price_data)} tickers.\n")

    print("Syncing paper books:")
    swing = run_swing_daily(config, price_data=price_data)
    _summary("swing", swing)

    momentum = run_momentum_daily(config, price_data=price_data)
    _summary("momentum", momentum)

    nss = run_nss_daily(config, price_data=price_data)
    _summary("nss", nss)

    strsi = run_supertrend_rsi_daily(config, price_data=price_data)
    _summary("supertrend_rsi", strsi)

    trama = run_trama_daily(config, price_data=price_data)
    _summary("trama", trama)

    nwe = run_nw_envelope_daily(config, price_data=price_data)
    _summary("nw_envelope", nwe)

    pf = run_pattern_forecast_daily(config, price_data=price_data)
    _summary("pattern_forecast", pf)

    gap_fill = run_gap_fill_daily(config, price_data=price_data)
    _summary("gap_fill", gap_fill)

    from tradingagents.rs_desk import run_rs_desk_daily

    rs_desk = run_rs_desk_daily(config)
    _summary("rs_desk", rs_desk)

    tech_desk = run_tech_desk_daily(config)
    if tech_desk.get("skipped"):
        print(f"  {'tech_desk':<16} skipped ({tech_desk.get('reason')})")
    else:
        print(
            f"  {'tech_desk':<16} exits={len(tech_desk.get('exits', []))} "
            f"fills={len(tech_desk.get('zone_fills', []))} "
            f"open_now={tech_desk.get('open_positions', 0)}"
        )

    print("\nDone. Any pending replacements need approval via the *-approve commands.")


if __name__ == "__main__":
    main()
