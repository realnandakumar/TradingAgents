"""Walk-forward chart-pattern backtest (next-day open fill, SQLite-first prices)."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.dataflows.ohlcv_store import read_history
from tradingagents.screening.chart_pattern_backtest import (
    backtest_report_payload,
    backtest_universe,
    default_backtest_output_path,
)
from tradingagents.screening.universe import load_universe


def _timestamped_path(base_dir: Path) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return base_dir / f"chart_pattern_backtest_{stamp}.json"


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Chart Patterns walk-forward backtest (next-day open fill)"
    )
    parser.add_argument(
        "--period",
        type=str,
        default="5y",
        help="History window from SQLite/CSV (default: 5y; use 10y after full sync)",
    )
    parser.add_argument("--sample", type=int, default=80, help="Max tickers (0 = full universe)")
    parser.add_argument("--step", type=int, default=5, help="Walk-forward step in trading days")
    parser.add_argument("--horizon", type=int, default=20, help="Forward evaluation horizon")
    parser.add_argument("--out", type=str, default="", help="Optional JSON output path")
    args = parser.parse_args()

    config = DEFAULT_CONFIG.copy()
    universe = load_universe(
        csv_path=config.get("screen_universe_csv"),
        cache_dir=config.get("data_cache_dir"),
    )
    if args.sample > 0:
        universe = universe[: args.sample]

    print(f"Loading {args.period} OHLCV for {len(universe)} tickers (SQLite first)...")
    price_data = read_history(universe, period=args.period, cache_dir=config.get("data_cache_dir"))
    loaded = len(price_data)
    print(
        f"Backtesting {loaded} symbols with data "
        f"(step={args.step}d, horizon={args.horizon}d, fill=next_open)..."
    )
    if loaded == 0:
        print(
            "No price data found. Run: python scripts/run_full_10y_sync.py "
            "or python scripts/sync_price_cache.py --mode full --period 10y"
        )
        sys.exit(1)

    summary = backtest_universe(
        config,
        price_data,
        step=args.step,
        horizon=args.horizon,
    )
    payload = backtest_report_payload(
        summary,
        period=args.period,
        step=args.step,
        horizon=args.horizon,
    )
    print(json.dumps({k: v for k, v in payload.items() if k != "trades"}, indent=2))
    print(f"Trades recorded: {len(payload.get('trades', []))}")

    out_path = args.out or default_backtest_output_path(config)
    if out_path:
        path = Path(out_path)
    else:
        backtests_dir = Path(config.get("data_cache_dir", "")).parent / "backtests"
        if not str(backtests_dir).strip():
            backtests_dir = Path.home() / ".tradingagents" / "backtests"
        path = _timestamped_path(backtests_dir)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
