"""Run Gap Fill screener immediately (no paper book update)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.screening.gap_fill_screener import screen_gap_fill


def main() -> None:
    config = DEFAULT_CONFIG.copy()
    picks = screen_gap_fill(config, progress=lambda m: print(f"  {m}"))
    print(f"\n{len(picks)} Gap Fill setup(s)")
    for i, p in enumerate(picks, 1):
        s = p.signal
        print(
            f"{i:>2}  {s.symbol.replace('.NS', ''):<14} {s.direction:<4} "
            f"age={s.gap_age} gap={s.gap_pct:+.1f}% fill={s.fill_pct:.0f}%  {s.remark}"
        )


if __name__ == "__main__":
    main()
