"""Map RS Desk config keys onto Tech Desk keys so book/manager/PM/rules are reused.

Reports stay on the shared ``tech_analyze_reports_dir``. Only book / pending /
daily / process paths differ.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

_DEFAULT_HOME = os.path.join(os.path.expanduser("~"), ".tradingagents")

# RS desk key → Tech Desk key consumed by TechDeskPositionBook / manager / rules / PM
_RS_TO_TECH = {
    "rs_desk_book_path": "tech_desk_book_path",
    "rs_desk_pending_path": "tech_desk_pending_path",
    "rs_desk_pending_dismissed_path": "tech_desk_pending_dismissed_path",
    "rs_desk_daily_dir": "tech_desk_daily_dir",
    "rs_desk_process_log_dir": "tech_desk_process_log_dir",
    "rs_desk_closed_history_path": "tech_desk_closed_history_path",
    "rs_desk_max_positions": "tech_desk_max_positions",
    "rs_desk_holding_days": "tech_desk_holding_days",
    "rs_desk_min_confidence": "tech_desk_min_confidence",
    "rs_desk_max_report_age_days": "tech_desk_max_report_age_days",
    "rs_desk_zone_proximity_pct": "tech_desk_zone_proximity_pct",
    "rs_desk_min_reward_to_zone_ratio": "tech_desk_min_reward_to_zone_ratio",
    "rs_desk_proximity_min_confidence": "tech_desk_proximity_min_confidence",
    "rs_desk_proximity_stop_at_zone_low": "tech_desk_proximity_stop_at_zone_low",
    "rs_desk_pending_max_days": "tech_desk_pending_max_days",
    "rs_desk_target_path_skip_pct": "tech_desk_target_path_skip_pct",
    "rs_desk_invalidate_on_stop_break": "tech_desk_invalidate_on_stop_break",
}

_RS_DEFAULTS = {
    "rs_desk_book_path": os.path.join(_DEFAULT_HOME, "rs_desk", "positions.json"),
    "rs_desk_pending_path": os.path.join(_DEFAULT_HOME, "rs_desk", "pending_entries.json"),
    "rs_desk_pending_dismissed_path": os.path.join(
        _DEFAULT_HOME, "rs_desk", "pending_dismissed.json"
    ),
    "rs_desk_daily_dir": os.path.join(_DEFAULT_HOME, "rs_desk", "daily"),
    "rs_desk_process_log_dir": os.path.join(_DEFAULT_HOME, "rs_desk", "process"),
    "rs_desk_closed_history_path": os.path.join(
        _DEFAULT_HOME, "rs_desk", "closed_history.json"
    ),
    "rs_desk_max_positions": 20,
    "rs_desk_holding_days": 20,
    "rs_desk_min_confidence": 60,
    "rs_desk_max_report_age_days": 14,
    "rs_desk_zone_proximity_pct": 1.5,
    "rs_desk_min_reward_to_zone_ratio": 2.5,
    "rs_desk_proximity_min_confidence": 65,
    "rs_desk_proximity_stop_at_zone_low": True,
    "rs_desk_pending_max_days": 10,
    "rs_desk_target_path_skip_pct": 0.80,
    "rs_desk_invalidate_on_stop_break": True,
}


def as_tech_desk_config(config: Optional[dict] = None) -> Dict[str, Any]:
    """Return a config dict Tech Desk classes understand, pointing at RS desk paths."""
    src = dict(config or {})
    out = dict(src)

    for rs_key, default in _RS_DEFAULTS.items():
        if rs_key not in out or out[rs_key] is None:
            out[rs_key] = src.get(rs_key, default)

    for rs_key, tech_key in _RS_TO_TECH.items():
        out[tech_key] = out[rs_key]

    out["tech_desk_strategy_name"] = "rs_desk"
    # Shared reports — never remap
    if not out.get("tech_analyze_reports_dir"):
        out["tech_analyze_reports_dir"] = os.path.join(_DEFAULT_HOME, "tech_reports")
    return out
