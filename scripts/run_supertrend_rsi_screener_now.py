"""Run SuperTrend + RSI screener."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.supertrend_rsi import screen_supertrend_rsi


def main() -> None:
    config = DEFAULT_CONFIG.copy()
    print("SuperTrend + RSI screener v1.0\n")
    picks = screen_supertrend_rsi(config, progress=lambda m: print(f"  {m}"))

    print()
    if not picks:
        print("SCREENER RESULT: 0 signal(s)")
        return

    fmt = "{:>2}  {:<12} {:<5} {:>5} {:<12} {:>5} {:>4}"
    print("=" * 60)
    print(f"SCREENER RESULT: {len(picks)} signal(s)")
    print("=" * 60)
    print(fmt.format("#", "Ticker", "Dir", "Score", "Grade", "RSI", "Age"))
    print("-" * 60)
    for i, p in enumerate(picks, 1):
        s = p.signal
        print(fmt.format(
            i,
            s.symbol.replace(".NS", ""),
            s.direction,
            s.score,
            s.grade[:12],
            f"{s.rsi:.1f}",
            s.flip_age,
        ))


if __name__ == "__main__":
    main()
