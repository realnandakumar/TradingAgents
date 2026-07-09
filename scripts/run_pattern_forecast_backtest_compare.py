"""Compare Pattern Forecast v1.6.1 vs v1.7 walk-forward backtests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.screening.pattern_forecast_audit import audit_universe
from tradingagents.screening.prices import download_history
from tradingagents.screening.universe import load_universe

# v1.6.1 baseline (no v1.7 filters / exits)
V161_OVERRIDES = {
    "pattern_forecast_use_v17": False,
    "pattern_forecast_consensus_min_agree": 2,
    "pattern_forecast_min_hist_fwd_pct": 1.0,
    "pattern_forecast_min_risk_reward": 1.5,
    "pattern_forecast_max_projected_move_pct": 15.0,
    "pattern_forecast_max_stop_pct": 5.0,
    "pattern_forecast_stop_on_close_only": False,
    "pattern_forecast_breakeven_trigger_pct": 0.0,
    "pattern_forecast_require_stock_above_ma": False,
    "pattern_forecast_require_weekly_above_ma": False,
}


def _config(overrides: dict) -> dict:
    cfg = DEFAULT_CONFIG.copy()
    cfg.update(overrides)
    return cfg


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="v1.6.1 vs v1.7 backtest compare")
    parser.add_argument("--sample", type=int, default=100)
    parser.add_argument("--step", type=int, default=5)
    args = parser.parse_args()

    universe = load_universe(
        csv_path=DEFAULT_CONFIG.get("screen_universe_csv"),
        cache_dir=DEFAULT_CONFIG.get("data_cache_dir"),
    )
    benchmark = DEFAULT_CONFIG.get("paper_benchmark", "^NSEI")
    if args.sample > 0:
        universe = universe[: args.sample]

    tickers = list(universe)
    if benchmark not in tickers:
        tickers.append(benchmark)

    period = DEFAULT_CONFIG.get("pattern_forecast_history_period", "2y")
    print(f"Downloading {period} for {len(tickers)} tickers...")
    price_data = download_history(tickers, period=period)
    bench = price_data.get(benchmark)

    print(f"\nRunning v1.6.1 audit (step={args.step})...")
    v161 = audit_universe(
        _config(V161_OVERRIDES),
        price_data,
        step=args.step,
        benchmark_df=bench,
        version="1.6.1",
    )

    print(f"Running v1.7 audit (step={args.step})...")
    v17 = audit_universe(
        DEFAULT_CONFIG.copy(),
        price_data,
        step=args.step,
        benchmark_df=bench,
        version="1.7",
    )

    out = {"v1.6.1": v161.to_dict(), "v1.7": v17.to_dict()}
    print("\n" + "=" * 72)
    print("PATTERN FORECAST BACKTEST COMPARE")
    print("=" * 72)
    print(json.dumps(out, indent=2))

    print("\n" + "-" * 72)
    print(f"{'Metric':<28} {'v1.6.1':>12} {'v1.7':>12} {'Delta':>12}")
    print("-" * 72)
    rows = [
        ("Signals", "signals", "{:.0f}"),
        ("Direction accuracy %", "direction_accuracy_pct", "{:.1f}"),
        ("Win rate %", "win_rate_pct", "{:.1f}"),
        ("Stop hit rate %", "stop_hit_rate_pct", "{:.1f}"),
        ("Avg return %", "avg_return_pct", "{:.2f}"),
        ("Max touch rate %", "max_touch_rate_pct", "{:.1f}"),
    ]
    a, b = v161.to_dict(), v17.to_dict()
    for label, key, fmt in rows:
        va, vb = a[key], b[key]
        delta_s = ""
        if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
            delta = vb - va
            if key == "avg_return_pct":
                delta_s = f"{delta:+.2f}"
            elif fmt.endswith("f}"):
                delta_s = f"{delta:+.1f}"
            else:
                delta_s = f"{delta:+d}"
        print(f"{label:<28} {fmt.format(va):>12} {fmt.format(vb):>12} {delta_s:>12}")
    print("-" * 72)


if __name__ == "__main__":
    main()
