"""Walk-forward backtest for Chart Patterns with next-day open fill."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict

import pandas as pd

from tradingagents.screening.chart_pattern_audit import (
    ChartPatternAuditSummary,
    audit_universe,
)


def backtest_universe(
    config: dict,
    price_data: Dict[str, pd.DataFrame],
    *,
    step: int = 5,
    horizon: int = 20,
) -> ChartPatternAuditSummary:
    """Run chart-pattern walk-forward backtest with next-day open execution."""
    return audit_universe(
        config,
        price_data,
        step=step,
        horizon=horizon,
        fill_mode="next_open",
    )


def backtest_report_payload(
    summary: ChartPatternAuditSummary,
    *,
    period: str,
    step: int,
    horizon: int,
) -> dict:
    """Serialize backtest summary plus run metadata for JSON export."""
    payload = summary.to_dict()
    payload["run_type"] = "chart_pattern_backtest"
    payload["period"] = period
    payload["step_days"] = step
    payload["horizon_days"] = horizon
    payload["generated_at"] = (
        datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    )
    payload["trades"] = [
        {
            "symbol": t.symbol,
            "pattern_id": t.pattern_id,
            "as_of_date": t.as_of_date,
            "setup_status": t.setup_status,
            "confidence": t.confidence,
            "entry_fill": round(t.entry_fill, 2),
            "close": round(t.close, 2),
            "stop": round(t.stop, 2),
            "target_1": round(t.target_1, 2),
            "target_2": round(t.target_2, 2),
            "outcome": t.outcome,
            "return_pct": round(t.return_pct, 2),
        }
        for t in summary.trades
    ]
    return payload


def default_backtest_output_path(config: dict) -> str:
    return config.get(
        "chart_pattern_backtest_path",
        "",
    ) or ""
