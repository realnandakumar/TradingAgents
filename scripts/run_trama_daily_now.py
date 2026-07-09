"""Run TRAMA daily portfolio job immediately."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.trama import run_trama_daily


def main() -> None:
    report = run_trama_daily(
        DEFAULT_CONFIG.copy(), progress=lambda m: print(f"  {m}"), force=True
    )
    if report.get("skipped"):
        print(f"Skipped: {report.get('reason')}")
        return
    print(f"\nDate: {report.get('date')}")
    print(
        f"BUY picks: {report.get('screener_picks')} · "
        f"Opened: {report.get('opened')} · Exits: {len(report.get('exits', []))}"
    )
    print(f"Open positions: {report.get('open_positions')}")


if __name__ == "__main__":
    main()
