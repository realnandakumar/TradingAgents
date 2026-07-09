"""Run NSS scanner diagnostics (waterfall + near misses)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.screening.nss_diagnostics import run_scan_diagnostics


def main() -> None:
    config = DEFAULT_CONFIG.copy()
    print("NSS scanner diagnostics v1.1\n")
    report = run_scan_diagnostics(config, progress=lambda m: print(f"  {m}"))

    print()
    print(f"Universe: {report.universe_size}  Picks: {len(report.picks)}  Rejected: {report.rejected_count}")
    if report.market_health:
        h = report.market_health
        print(
            f"Market health: trend={h.get('trend_stocks')} consolidating={h.get('consolidating_stocks')} "
            f"breakout={h.get('breakout_candidates')} vol={h.get('volume_confirmed')} picks={h.get('final_picks')}"
        )

    print("\n--- Waterfall (in / out / rejected %) ---")
    for step in report.waterfall:
        rej = f"  -{step.rejection_count} ({step.rejection_pct:.1f}%)" if step.rejection_count else ""
        print(f"  {step.label:<28} {step.input_count:>4} -> {step.output_count:>4}{rej}")

    print("\n--- Rejections by stage ---")
    for stage, count in sorted(report.rejection_by_stage.items(), key=lambda x: -x[1]):
        print(f"  {stage:<22} {count}")

    print(f"\n--- Near miss (top {min(10, len(report.near_misses))}) ---")
    for n in report.near_misses[:10]:
        print(f"  {n.rank:>2}  {n.symbol.replace('.NS', ''):<12} score={n.partial_score:5.1f} gap={n.score_gap:4.1f}")
        print(f"      failed: {n.failure_stage}  need={n.threshold_required}  actual={n.threshold_actual}")
        print(f"      dist: {n.threshold_distance}  -> {n.watch_action}")

    if report.picks:
        print(f"\nPicks: {', '.join(p.replace('.NS', '') for p in report.picks)}")

    out_path = Path.home() / ".tradingagents" / "nss" / "diagnostics_latest.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report.to_dict(include_rejections=True), indent=2), encoding="utf-8")
    print(f"\nFull report: {out_path}")


if __name__ == "__main__":
    main()
