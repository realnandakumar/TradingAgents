"""Walk-forward accuracy audit for Chart Patterns."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.screening.chart_pattern_audit import audit_universe
from tradingagents.screening.prices import download_history
from tradingagents.screening.universe import load_universe


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Chart Patterns walk-forward audit")
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

    period = config.get("chart_pattern_history_period", "2y")
    print(f"Downloading {period} for {len(universe)} tickers...")
    price_data = download_history(universe, period=period)
    print(f"Auditing {len(universe)} symbols (step={args.step}d, horizon={args.horizon}d)...")
    summary = audit_universe(config, price_data, step=args.step, horizon=args.horizon)
    payload = summary.to_dict()
    print(json.dumps(payload, indent=2))

    out_path = args.out or config.get("chart_pattern_audit_path")
    if out_path:
        path = Path(out_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
