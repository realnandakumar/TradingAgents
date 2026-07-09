"""Run Pattern Forecast screener immediately (Phase 1 — no paper book)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.screening.pattern_forecast_screener import screen_pattern_forecast


def main() -> None:
    config = DEFAULT_CONFIG.copy()
    picks = screen_pattern_forecast(config, progress=lambda m: print(f"  {m}"))
    print(f"\n{len(picks)} Pattern Forecast pick(s)")
    for i, p in enumerate(picks, 1):
        s = p.signal
        print(
            f"{i:>2}  {s.symbol.replace('.NS', ''):<14} {s.direction:<4} "
            f"prob={s.probability:>5.1f}%  close={s.close:>10.2f}  "
            f"proj5d={s.projected_close_5d:>10.2f}  max5d={s.projected_max_high_5d:>10.2f}  "
            f"move={s.projected_move_pct:+.1f}%  max={s.projected_max_pct:+.1f}%  "
            f"consensus={s.consensus_count}  analogue={s.analogue_end_date}"
        )


if __name__ == "__main__":
    main()
