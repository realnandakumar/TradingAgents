"""Run the EOD pipeline if today's sync has not completed yet.

Used by Windows Task Scheduler at user logon to catch up when the machine
was powered off at the scheduled 4:10 PM IST run.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.dataflows.ohlcv_store import manifest_eod_ran_today


def main() -> int:
    config = DEFAULT_CONFIG.copy()
    cache_dir = config.get("data_cache_dir")

    if manifest_eod_ran_today(cache_dir):
        print("EOD already completed today — catch-up not needed.")
        return 0

    print("EOD not run today — starting catch-up pipeline...")
    script = Path(__file__).resolve().parent / "run_eod_pipeline.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
