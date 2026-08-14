"""Strict JSON helpers for paper books the dashboard must parse."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Optional


def sanitize_for_json(value: Any) -> Any:
    """Replace non-finite floats so dumps stay valid JSON (no bare NaN)."""
    if isinstance(value, float):
        return None if not math.isfinite(value) else value
    if isinstance(value, dict):
        return {key: sanitize_for_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_for_json(item) for item in value]
    return value


def dumps_json(payload: Any, *, default=None) -> str:
    return json.dumps(
        sanitize_for_json(payload),
        indent=2,
        allow_nan=False,
        default=default,
    ) + "\n"


def dump_json(path: Path, payload: Any, *, default=None) -> None:
    cleaned = dumps_json(payload, default=default)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(cleaned, encoding="utf-8")
    tmp.replace(path)


def finite_number(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def bar_ohlc_finite(bar: Any) -> Optional[tuple[float, float, float]]:
    try:
        low = float(bar["Low"])
        high = float(bar["High"])
        close = float(bar["Close"])
    except (TypeError, ValueError, KeyError):
        return None
    if not all(math.isfinite(v) for v in (low, high, close)):
        return None
    return low, high, close


def aggregate_closed_trades(
    trades: list[dict],
    *,
    win_by_outcome: bool = True,
) -> dict:
    """Desk stats that ignore non-finite returns (NaN is truthy in Python)."""
    n = len(trades)
    if n == 0:
        return {
            "trades": 0,
            "win_rate": None,
            "avg_return": None,
            "avg_alpha": None,
            "total_pnl": 0.0,
        }
    rets = [finite_number(t.get("raw_return")) for t in trades]
    rets_f = [r for r in rets if r is not None]
    if win_by_outcome:
        wins = sum(1 for t in trades if t.get("outcome") == "success")
    else:
        wins = sum(1 for r in rets_f if r > 0)
    avg_ret = sum(rets_f) / len(rets_f) if rets_f else None
    alphas = [finite_number(t.get("alpha_return")) for t in trades]
    alphas_f = [a for a in alphas if a is not None]
    pnl = sum(finite_number(t.get("rupee_pnl")) or 0.0 for t in trades)
    return {
        "trades": n,
        "win_rate": round(100 * wins / n, 1),
        "avg_return": round(100 * avg_ret, 2) if avg_ret is not None else None,
        "avg_alpha": round(100 * sum(alphas_f) / len(alphas_f), 2) if alphas_f else None,
        "total_pnl": round(pnl, 2),
    }
