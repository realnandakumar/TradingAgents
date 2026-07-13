"""Pending entry lifecycle — peak tracking, exhaustion, invalidation, dismissal."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from .exits import zone_fill_price


def target_path_fraction(peak: float, zone_high: float, target_1: float) -> float:
    span = target_1 - zone_high
    if span <= 0:
        return 0.0
    return max(0.0, (peak - zone_high) / span)


def update_pending_peak(entry: dict, hist: pd.DataFrame) -> dict:
    """Update peak_since_added / peak_date from OHLC since plan_date."""
    if hist is None or hist.empty:
        return entry
    peak = float(hist["High"].max())
    peak_idx = hist["High"].idxmax()
    peak_date = peak_idx.strftime("%Y-%m-%d") if hasattr(peak_idx, "strftime") else str(peak_idx)[:10]
    prev_peak = float(entry.get("peak_since_added") or 0)
    if peak > prev_peak:
        entry = dict(entry)
        entry["peak_since_added"] = round(peak, 2)
        entry["peak_date"] = peak_date
    return entry


def is_pending_invalidated(entry: dict, hist: pd.DataFrame, config: dict) -> tuple[bool, str]:
    if not config.get("tech_desk_invalidate_on_stop_break", True):
        return False, ""
    stop = float(entry.get("stop_loss") or 0)
    if stop <= 0 or hist is None or hist.empty:
        return False, ""
    if float(hist["Close"].min()) < stop:
        return True, "invalidated_stop"
    return False, ""


def is_pending_expired(entry: dict, as_of: str, config: dict) -> bool:
    max_days = int(config.get("tech_desk_pending_max_days", 10))
    plan_date = entry.get("plan_date") or entry.get("added_at", "")[:10]
    if not plan_date:
        return False
    try:
        start = datetime.strptime(plan_date, "%Y-%m-%d")
        end = datetime.strptime(as_of, "%Y-%m-%d")
    except ValueError:
        return False
    return (end - start).days > max_days


def is_setup_exhausted(
    entry: dict,
    hist: pd.DataFrame,
    config: dict,
) -> tuple[bool, str]:
    """Skip zone fill when price ran >= threshold of zone→T1 path before pulling back."""
    zone_low = float(entry.get("zone_low") or 0)
    zone_high = float(entry.get("zone_high") or 0)
    target_1 = float(entry.get("target_1") or 0)
    threshold = float(config.get("tech_desk_target_path_skip_pct", 0.80))

    if zone_low <= 0 or zone_high <= zone_low or target_1 <= zone_high:
        return False, ""
    if hist is None or hist.empty:
        return False, ""

    peak = float(hist["High"].max())
    path = target_path_fraction(peak, zone_high, target_1)
    if path < threshold:
        return False, ""

    last = hist.iloc[-1]
    if zone_fill_price(last, zone_low, zone_high) is None:
        return False, ""

    return True, "post_target_pullback"


def history_from_plan_date(
    hist: Optional[pd.DataFrame],
    plan_date: str,
    as_of: str,
) -> Optional[pd.DataFrame]:
    if hist is None or hist.empty:
        return hist
    try:
        start = datetime.strptime(plan_date, "%Y-%m-%d")
        end = datetime.strptime(as_of, "%Y-%m-%d") + timedelta(days=1)
    except ValueError:
        return hist
    mask = (hist.index >= pd.Timestamp(start)) & (hist.index < pd.Timestamp(end))
    sliced = hist.loc[mask]
    return sliced if not sliced.empty else hist
