"""Run momentum-daily once and print summary (mirrors run_swing_daily_now.py)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.momentum import run_momentum_daily


def main() -> None:
    config = DEFAULT_CONFIG.copy()
    report = run_momentum_daily(
        config,
        progress=lambda m: print(f"  {m}"),
        approve=lambda _p: False,
        force=True,
    )

    print()
    print("=" * 72)
    if report.get("skipped"):
        print("SKIPPED:", report.get("reason"))
    else:
        print(
            f"momentum_trade_positional daily | {report.get('date')} "
            f"| chart: {report.get('chart_timeframe')}"
        )
        opened = report.get("opened", [])
        exits = report.get("exits", [])
        print(
            f"Screener picks: {report.get('screener_picks')} | "
            f"Opened: {len(opened)} | Exits: {len(exits)} | "
            f"Open now: {report.get('open_positions')}"
        )
        if exits:
            print("\nExits:")
            for e in exits:
                r = e.get("raw_return")
                rp = f"{r * 100:+.1f}%" if r is not None else "n/a"
                print(f"  {e['ticker']} | {e['reason']} | {rp}")
        if opened:
            print("\nOpened:", ", ".join(opened))
        if report.get("skipped_duplicate"):
            print(
                "\nAlready held (first entry kept):",
                ", ".join(report["skipped_duplicate"]),
            )
        if report.get("proposals"):
            print(f"\nPending replacements: {len(report['proposals'])}")
            for p in report["proposals"][:5]:
                print(f"  Replace {p['close_stock_name']} -> {p['new_stock_name']}")
    print("=" * 72)


if __name__ == "__main__":
    main()
