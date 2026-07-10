"""Run Chart Patterns screener immediately (no paper book update)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.screening.chart_pattern_engine import PATTERN_CATALOG
from tradingagents.screening.chart_pattern_screener import (
    group_chart_pattern_picks,
    screen_chart_patterns,
)


def main() -> None:
    config = DEFAULT_CONFIG.copy()
    picks = screen_chart_patterns(config, progress=lambda m: print(f"  {m}"))
    groups = group_chart_pattern_picks(picks)
    print(f"\n{len(picks)} row(s) across {len(groups)} pattern table(s)\n")
    for pattern_id, group in groups:
        meta = PATTERN_CATALOG[pattern_id]
        print(f"=== {meta['label']} ({meta['bias']}, *{meta['stars']}) - {len(group)} hit(s) ===")
        for i, p in enumerate(group, 1):
            s = p.signal
            print(
                f"{i:>2}  {s.symbol.replace('.NS', ''):<14} "
                f"age={s.pattern_age:>2}d {s.setup_status:<12} "
                f"dist={s.distance_to_trigger_pct:>4.1f}% score={s.actionability_score:.0f}  "
                f"close={s.close:,.2f} trigger={s.trigger_level:,.2f}"
            )
        print()


if __name__ == "__main__":
    main()
