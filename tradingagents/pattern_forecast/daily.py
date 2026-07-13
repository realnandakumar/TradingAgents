"""Daily Pattern Forecast portfolio run."""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Dict, Optional, TYPE_CHECKING

from tradingagents.screening.pattern_forecast_screener import screen_pattern_forecast
from tradingagents.pattern_forecast.manager import PatternForecastPaperTradeManager, ReplacementProposal

if TYPE_CHECKING:
    import pandas as pd


def run_pattern_forecast_daily(
    config: dict,
    progress: Optional[Callable[[str], None]] = None,
    approve: Optional[Callable[[ReplacementProposal], bool]] = None,
    force: bool = False,
    price_data: Optional[Dict[str, "pd.DataFrame"]] = None,
) -> dict:
    def _log(msg: str):
        if progress:
            progress(msg)

    _log("Running Pattern Forecast screener (2y analogue, 5d projection)...")
    cfg = config.copy()
    cfg["pattern_forecast_directions"] = "UP"
    picks = screen_pattern_forecast(cfg, progress=progress, price_data=price_data)

    manager = PatternForecastPaperTradeManager(config)
    screen_date = datetime.now().strftime("%Y-%m-%d")
    report = manager.run_daily(picks, screen_date=screen_date, approve=approve)
    report["skipped"] = False
    report["picks"] = [p.symbol for p in picks if p.direction == "UP"]
    return report
