"""Run Pattern Forecast daily portfolio update."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.pattern_forecast import run_pattern_forecast_daily


def main() -> None:
    config = DEFAULT_CONFIG.copy()
    report = run_pattern_forecast_daily(config, force=True, progress=lambda m: print(f"  {m}"))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
