"""Walk-forward accuracy audit for Pattern Forecast v1.5."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.screening.pattern_forecast_audit import audit_universe
from tradingagents.screening.prices import download_history
from tradingagents.screening.universe import load_universe


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Pattern Forecast v1.5 walk-forward audit")
    parser.add_argument("--sample", type=int, default=100, help="Max tickers (0 = full universe)")
    parser.add_argument("--step", type=int, default=5, help="Walk-forward step in trading days")
    args = parser.parse_args()

    config = DEFAULT_CONFIG.copy()
    universe = load_universe(
        csv_path=config.get("screen_universe_csv"),
        cache_dir=config.get("data_cache_dir"),
    )
    benchmark = config.get("paper_benchmark", "^NSEI")
    if args.sample > 0:
        universe = universe[: args.sample]

    period = config.get("pattern_forecast_history_period", "2y")
    tickers = list(universe)
    if benchmark not in tickers:
        tickers.append(benchmark)

    print(f"Downloading {period} for {len(tickers)} tickers (v1.6.1 Spearman + consensus 2/5)...")
    price_data = download_history(tickers, period=period)
    print(f"Auditing {len(universe)} symbols (step={args.step}d)...")
    summary = audit_universe(
        config,
        price_data,
        step=args.step,
        up_only=True,
        benchmark_df=price_data.get(benchmark),
    )
    print(json.dumps(summary.to_dict(), indent=2))


if __name__ == "__main__":
    main()
