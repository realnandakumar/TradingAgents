"""Run all daily paper-trade jobs from a single shared Yahoo download.

Downloads 2y of daily history once for the shared NSE universe, then runs
each strategy's daily job (screen -> process exits -> open/replace) against
that data. All strategy paper books are synced in one pass.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.momentum import run_momentum_daily
from tradingagents.nss import run_nss_daily
from tradingagents.screening.prices import download_history
from tradingagents.screening.universe import load_universe
from tradingagents.gap_fill import run_gap_fill_daily
from tradingagents.nw_envelope import run_nw_envelope_daily
from tradingagents.pattern_forecast import run_pattern_forecast_daily
from tradingagents.supertrend_rsi import run_supertrend_rsi_daily
from tradingagents.swing import run_swing_daily
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
    if report.get("opened"):
        print(f"      opened: {', '.join(report['opened'])}")


def main() -> None:
    config = DEFAULT_CONFIG.copy()
    universe = load_universe(
        csv_path=config.get("screen_universe_csv"),
        cache_dir=config.get("data_cache_dir"),
    )

    print(f"Downloading {SHARED_PERIOD} history once for {len(universe)} tickers...")
    price_data = download_history(universe, period=SHARED_PERIOD)
    print(f"Got usable history for {len(price_data)} tickers.\n")

    print("Syncing paper books (force=True):")
    swing = run_swing_daily(config, force=True, price_data=price_data)
    _summary("swing", swing)

    momentum = run_momentum_daily(config, force=True, price_data=price_data)
    _summary("momentum", momentum)

    nss = run_nss_daily(config, force=True, price_data=price_data)
    _summary("nss", nss)

    strsi = run_supertrend_rsi_daily(config, force=True, price_data=price_data)
    _summary("supertrend_rsi", strsi)

    trama = run_trama_daily(config, force=True, price_data=price_data)
    _summary("trama", trama)

    gap_fill = run_gap_fill_daily(config, force=True, price_data=price_data)
    _summary("gap_fill", gap_fill)

    nwe = run_nw_envelope_daily(config, force=True, price_data=price_data)
    _summary("nw_envelope", nwe)

    pf = run_pattern_forecast_daily(config, force=True, price_data=price_data)
    _summary("pattern_forecast", pf)

    print("\nDone. Any pending replacements need approval via the *-approve commands.")


if __name__ == "__main__":
    main()
