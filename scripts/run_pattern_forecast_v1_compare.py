"""Quick v1 vs v1.1 direction-accuracy compare."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.screening.pattern_forecast_audit import audit_universe
from tradingagents.screening.prices import download_history
from tradingagents.screening.universe import load_universe

V1 = {
    "pattern_forecast_bullish_only": False,
    "pattern_forecast_use_consensus": False,
    "pattern_forecast_min_correlation": 0.55,
    "pattern_forecast_min_projected_move_pct": 0.5,
    "pattern_forecast_max_projected_move_pct": 50.0,
    "pattern_forecast_min_max_touch_pct": 0.5,
    "pattern_forecast_min_risk_reward": 0.5,
    "pattern_forecast_require_positive_20d_return": False,
    "pattern_forecast_use_consensus_dispersion": False,
    "pattern_forecast_recency_weight": 0.0,
}


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=30)
    parser.add_argument("--step", type=int, default=20)
    args = parser.parse_args()

    v11 = DEFAULT_CONFIG.copy()
    cfg_v1 = {**v11, **V1}
    universe = load_universe(cache_dir=v11["data_cache_dir"])[: args.sample]
    bench = v11.get("paper_benchmark", "^NSEI")
    data = download_history(list(universe) + [bench], period="2y")
    b = data[bench]

    print(f"Compare v1 vs v1.1 ({args.sample} tickers, step={args.step})...\n")
    for label, cfg in [("v1", cfg_v1), ("v1.1", v11)]:
        s = audit_universe(cfg, data, step=args.step, benchmark_df=b, version=label)
        d = s.to_dict()
        print(
            f"{label}: signals={d['signals']}  dir={d['direction_accuracy_pct']}%  "
            f"win={d['win_rate_pct']}%  stop={d['stop_hit_rate_pct']}%  "
            f"avg_ret={d['avg_return_pct']}%"
        )


if __name__ == "__main__":
    main()
