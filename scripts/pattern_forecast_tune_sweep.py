"""Sweep Pattern Forecast configs for 5-day direction accuracy."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.screening.pattern_forecast_audit import audit_universe
from tradingagents.screening.prices import download_history
from tradingagents.screening.universe import load_universe


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=80)
    parser.add_argument("--step", type=int, default=10)
    args = parser.parse_args()

    base = DEFAULT_CONFIG.copy()
    universe = load_universe(cache_dir=base["data_cache_dir"])[: args.sample]
    bench = base.get("paper_benchmark", "^NSEI")
    data = download_history(list(universe) + [bench], period="2y")
    b = data[bench]

    variants = {
        "v1_baseline": {},
        "bullish_1pct": {
            "pattern_forecast_bullish_only": True,
            "pattern_forecast_min_hist_fwd_pct": 1.0,
        },
        "bullish_consensus2": {
            "pattern_forecast_bullish_only": True,
            "pattern_forecast_min_hist_fwd_pct": 1.0,
            "pattern_forecast_use_consensus": True,
            "pattern_forecast_consensus_min_agree": 2,
        },
        "spearman_bull_cons2": {
            "pattern_forecast_correlation_method": "spearman",
            "pattern_forecast_bullish_only": True,
            "pattern_forecast_min_hist_fwd_pct": 1.0,
            "pattern_forecast_use_consensus": True,
            "pattern_forecast_consensus_min_agree": 2,
            "pattern_forecast_min_correlation": 0.60,
            "pattern_forecast_min_risk_reward": 1.5,
            "pattern_forecast_max_projected_move_pct": 15.0,
            "pattern_forecast_min_projected_move_pct": 2.0,
            "pattern_forecast_min_max_touch_pct": 3.0,
        },
        "pearson_bull_cons2": {
            "pattern_forecast_correlation_method": "pearson",
            "pattern_forecast_bullish_only": True,
            "pattern_forecast_min_hist_fwd_pct": 1.0,
            "pattern_forecast_use_consensus": True,
            "pattern_forecast_consensus_min_agree": 2,
            "pattern_forecast_min_correlation": 0.60,
            "pattern_forecast_min_risk_reward": 1.5,
            "pattern_forecast_max_projected_move_pct": 15.0,
            "pattern_forecast_min_projected_move_pct": 2.0,
            "pattern_forecast_min_max_touch_pct": 3.0,
        },
        "spearman_loose": {
            "pattern_forecast_correlation_method": "spearman",
            "pattern_forecast_bullish_only": True,
            "pattern_forecast_min_hist_fwd_pct": 0.5,
            "pattern_forecast_use_consensus": True,
            "pattern_forecast_consensus_min_agree": 2,
            "pattern_forecast_min_correlation": 0.58,
            "pattern_forecast_min_risk_reward": 1.2,
            "pattern_forecast_max_projected_move_pct": 20.0,
            "pattern_forecast_min_projected_move_pct": 1.0,
            "pattern_forecast_min_max_touch_pct": 2.0,
        },
    }

    hdr = f"{'variant':<24} {'signals':>8} {'dir%':>7} {'win%':>7} {'stop%':>7} {'avg%':>7}"
    print(hdr)
    print("-" * len(hdr))
    for name, ov in variants.items():
        cfg = {**base, **ov}
        s = audit_universe(cfg, data, step=args.step, benchmark_df=b, version=name)
        d = s.to_dict()
        print(
            f"{name:<24} {d['signals']:>8} "
            f"{d['direction_accuracy_pct']:>7.1f} "
            f"{d['win_rate_pct']:>7.1f} "
            f"{d['stop_hit_rate_pct']:>7.1f} "
            f"{d['avg_return_pct']:>7.2f}"
        )


if __name__ == "__main__":
    main()
