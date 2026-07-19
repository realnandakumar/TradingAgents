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


def peak_history_start(
    entry: dict,
    config: Optional[dict] = None,
) -> str:
    """Start date for T1/peak checks: report_date (preferred) or plan_date, minus lookback."""
    cfg = config or {}
    anchor = (
        entry.get("report_date")
        or entry.get("plan_date")
        or entry.get("added_at", "")[:10]
        or ""
    )
    if not anchor:
        return ""
    lookback = int(cfg.get("tech_desk_t1_lookback_days", 45))
    try:
        start = datetime.strptime(anchor[:10], "%Y-%m-%d") - timedelta(days=max(0, lookback))
        return start.strftime("%Y-%m-%d")
    except ValueError:
        return anchor[:10]


def hist_peak_high(hist: Optional[pd.DataFrame]) -> float:
    if hist is None or hist.empty or "High" not in hist.columns:
        return 0.0
    return float(hist["High"].max())


def t1_already_achieved(peak: float, target_1: float) -> bool:
    """True when peak has reached (or essentially touched) target_1."""
    if target_1 <= 0 or peak <= 0:
        return False
    return peak + 1e-9 >= float(target_1)


def setup_peak(
    entry: dict,
    hist: Optional[pd.DataFrame] = None,
    current_price: Optional[float] = None,
) -> float:
    peak = hist_peak_high(hist)
    stored = float(entry.get("peak_since_added") or 0)
    peak = max(peak, stored)
    if current_price is not None and current_price > 0:
        peak = max(peak, float(current_price))
    return peak


def price_in_entry_zone(
    price: Optional[float],
    zone_low: float,
    zone_high: float,
) -> bool:
    if price is None or price <= 0:
        return False
    return float(zone_low) <= float(price) <= float(zone_high)


def post_target_entry_block_reason(
    *,
    zone_low: float,
    zone_high: float,
    target_1: float,
    current_price: Optional[float] = None,
    hist: Optional[pd.DataFrame] = None,
    peak: Optional[float] = None,
    config: Optional[dict] = None,
) -> Optional[str]:
    """
    Reject new zone waits / opens when T1 was already achieved, or when price
    ran far toward T1 and is already back in the pullback zone.
    """
    cfg = config or {}
    if zone_low <= 0 or zone_high <= zone_low or target_1 <= zone_high:
        return None

    if peak is None:
        peak = setup_peak({}, hist, current_price)

    # Hard: T1 already hit — never re-enter this setup on a later pullback.
    if t1_already_achieved(peak, target_1):
        return "post_target_pullback"
    if current_price is not None and current_price > 0 and t1_already_achieved(
        float(current_price), target_1
    ):
        return "post_target_pullback"

    threshold = float(cfg.get("tech_desk_target_path_skip_pct", 0.80))
    path = target_path_fraction(peak, zone_high, target_1)
    if path < threshold:
        return None

    # Soft: ran >= threshold of zone→T1 and already sitting in the zone.
    in_zone = price_in_entry_zone(current_price, zone_low, zone_high)
    if not in_zone and hist is not None and not hist.empty:
        in_zone = zone_fill_price(hist.iloc[-1], zone_low, zone_high) is not None
    if in_zone:
        return "post_target_pullback"
    return None


def update_pending_peak(entry: dict, hist: pd.DataFrame) -> dict:
    """Update peak_since_added / peak_date from OHLC since lookback start."""
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
    """
    Exhaust a pending setup when:
    - Hard: peak already reached target_1 (do not wait for a later zone fill), or
    - Soft: price ran >= threshold of zone→T1 and the last bar is back in the zone.
    """
    zone_low = float(entry.get("zone_low") or 0)
    zone_high = float(entry.get("zone_high") or 0)
    target_1 = float(entry.get("target_1") or 0)
    threshold = float(config.get("tech_desk_target_path_skip_pct", 0.80))

    if zone_low <= 0 or zone_high <= zone_low or target_1 <= zone_high:
        return False, ""
    if hist is None or hist.empty:
        # Still honour stored peak (e.g. T1 hit earlier, no new bars yet).
        peak = float(entry.get("peak_since_added") or 0)
        if t1_already_achieved(peak, target_1):
            return True, "post_target_pullback"
        return False, ""

    peak = setup_peak(entry, hist)
    if t1_already_achieved(peak, target_1):
        return True, "post_target_pullback"

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
