"""PM-facing excerpts and structured summaries from tech-analyze reports."""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_SECTION_DOT_RE = re.compile(r"^##\s+(\d+)\.\s+", re.MULTILINE)
_SECTION_PAREN_RE = re.compile(r"^##\s+(\d+)\)\s+", re.MULTILINE)
_CLOSE_PRICE_RE = re.compile(
    r"Closing Price[^:\n]*:\s*\**([₹$]?\s*[\d,]+\.?\d*)",
    re.IGNORECASE,
)
_MA_50_TABLE_RE = re.compile(r"\|\s*\*\*50 SMA\*\*\s*\|\s*₹?\s*([\d,.]+)", re.IGNORECASE)
_MA_200_TABLE_RE = re.compile(r"\|\s*\*\*200 SMA\*\*\s*\|\s*₹?\s*([\d,.]+)", re.IGNORECASE)
_ATR_TABLE_RE = re.compile(r"\|\s*\*\*ATR\*\*\s*\|\s*([\d,.]+)", re.IGNORECASE)
_ATR_SECTION_RE = re.compile(
    r"\|\s*(?:July\s+\d+|Date)\s*\|\s*\*\*([\d,.]+)\*\*",
    re.IGNORECASE,
)
_SUPPORT_TABLE_RE = re.compile(
    r"\|\s*\*\*Next Support\*\*\s*\|\s*([^\|]+)",
    re.IGNORECASE,
)
_RESISTANCE_TABLE_RE = re.compile(
    r"\|\s*\*\*Next Resistance\*\*\s*\|\s*([^\|]+)",
    re.IGNORECASE,
)
_MA_50_INLINE_RE = re.compile(
    r"(?:50\s*(?:SMA|EMA)|close_50_sma)[^~\d]{0,40}~?\s*₹?\s*([\d,.]+)",
    re.IGNORECASE,
)
_MA_200_INLINE_RE = re.compile(
    r"(?:200\s*(?:SMA|EMA)|close_200_sma)[^~\d]{0,40}~?\s*₹?\s*([\d,.]+)",
    re.IGNORECASE,
)
_ATR_INLINE_RE = re.compile(
    r"\bATR[^~\d]{0,20}~?\s*([\d,.]+)",
    re.IGNORECASE,
)
_PROPOSAL_RE = re.compile(
    r"FINAL TRANSACTION PROPOSAL:\s*\*\*([A-Z]+)\*\*",
    re.IGNORECASE,
)
_PM_SUMMARY_FENCE_RE = re.compile(
    r"```(?:yaml|json)?\s*pm_summary\s*\n(.*?)```",
    re.IGNORECASE | re.DOTALL,
)
_ANCHOR_PATTERNS = (
    re.compile(r"^##\s+8[\.)]\s+", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^##\s+Summary\s+table", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^##\s+Actionable\s+levels", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^##\s+Practical\s+actionable\s+levels", re.MULTILINE | re.IGNORECASE),
    re.compile(r"FINAL TRANSACTION PROPOSAL:", re.IGNORECASE),
    re.compile(r"^```(?:yaml|json)?\s*pm_summary", re.MULTILINE | re.IGNORECASE),
)


def _find_section_start(market_text: str, section_num: int) -> Optional[int]:
    for match in _SECTION_DOT_RE.finditer(market_text):
        if int(match.group(1)) == section_num:
            return match.start()
    for match in _SECTION_PAREN_RE.finditer(market_text):
        if int(match.group(1)) == section_num:
            return match.start()
    return None


def _find_excerpt_start(market_text: str) -> Optional[int]:
    """Pick the earliest high-signal anchor (§8+, summary, proposal, pm_summary)."""
    starts = [m.start() for pat in _ANCHOR_PATTERNS if (m := pat.search(market_text))]
    if starts:
        return min(starts)
    return _find_section_start(market_text, 8)


def extract_report_close_price(market_text: str) -> Optional[str]:
    match = _CLOSE_PRICE_RE.search(market_text)
    if not match:
        return None
    return match.group(1).replace(",", "").strip()


def _clean_level_cell(raw: str) -> str:
    return re.sub(r"\s+", " ", raw.strip().strip("|").strip())


def parse_key_levels(market_text: str) -> Dict[str, str]:
    """Parse ATR, MAs, support, resistance from tables or inline prose."""
    levels: Dict[str, str] = {}

    if match := _MA_50_TABLE_RE.search(market_text):
        levels["50_sma"] = match.group(1).replace(",", "")
    elif match := _MA_50_INLINE_RE.search(market_text):
        levels["50_sma"] = match.group(1).replace(",", "")

    if match := _MA_200_TABLE_RE.search(market_text):
        levels["200_sma"] = match.group(1).replace(",", "")
    elif match := _MA_200_INLINE_RE.search(market_text):
        levels["200_sma"] = match.group(1).replace(",", "")

    if match := _ATR_TABLE_RE.search(market_text):
        levels["atr"] = match.group(1).replace(",", "")
    elif match := _ATR_INLINE_RE.search(market_text):
        levels["atr"] = match.group(1).replace(",", "")
    else:
        section_six = _find_section_start(market_text, 6)
        if section_six is not None:
            section_text = market_text[section_six:]
            section_end = _find_section_start(section_text[10:], 7)
            atr_block = section_text if section_end is None else section_text[: section_end + 10]
            rows = list(_ATR_SECTION_RE.finditer(atr_block))
            if rows:
                levels["atr"] = rows[-1].group(1).replace(",", "")

    if match := _SUPPORT_TABLE_RE.search(market_text):
        levels["key_support"] = _clean_level_cell(match.group(1))
    if match := _RESISTANCE_TABLE_RE.search(market_text):
        levels["key_resistance"] = _clean_level_cell(match.group(1))

    return levels


def extract_final_proposal(market_text: str) -> Optional[str]:
    match = _PROPOSAL_RE.search(market_text)
    return match.group(1).upper() if match else None


def _parse_pm_summary_payload(raw: str) -> Optional[Dict[str, Any]]:
    text = raw.strip()
    if not text:
        return None
    try:
        data = json.loads(text)
        if isinstance(data, dict) and "pm_summary" in data:
            inner = data["pm_summary"]
            return inner if isinstance(inner, dict) else None
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def extract_pm_summary(market_text: str) -> Optional[Dict[str, Any]]:
    """Parse embedded ```pm_summary block or build minimal summary from proposal + levels."""
    if not market_text:
        return None

    fence = _PM_SUMMARY_FENCE_RE.search(market_text)
    if fence:
        parsed = _parse_pm_summary_payload(fence.group(1))
        if parsed:
            return parsed

    proposal = extract_final_proposal(market_text)
    levels = parse_key_levels(market_text)
    if not proposal and not levels:
        return None

    summary: Dict[str, Any] = {}
    if proposal:
        summary["proposal"] = proposal
    if levels.get("atr"):
        summary["atr"] = float(levels["atr"])
    if levels.get("50_sma"):
        summary["sma_50"] = float(levels["50_sma"])
    if levels.get("200_sma"):
        summary["sma_200"] = float(levels["200_sma"])
    if levels.get("key_support"):
        summary["key_support"] = levels["key_support"]
    if levels.get("key_resistance"):
        summary["key_resistance"] = levels["key_resistance"]
    return summary or None


def format_pm_summary_block(summary: Optional[Dict[str, Any]]) -> str:
    if not summary:
        return ""
    lines = ["### PM summary (structured)"]
    for key in (
        "proposal",
        "bias",
        "confidence",
        "entry_zone_low",
        "entry_zone_high",
        "stop",
        "target_1",
        "target_2",
        "atr",
        "sma_50",
        "sma_200",
        "key_support",
        "key_resistance",
        "invalidation",
    ):
        if key in summary and summary[key] is not None:
            lines.append(f"- {key}: {summary[key]}")
    return "\n".join(lines)


def format_key_levels_block(levels: Dict[str, str]) -> str:
    if not levels:
        return ""
    lines = ["### Key levels (parsed from report)"]
    if "atr" in levels:
        lines.append(f"- ATR: {levels['atr']}")
    if "50_sma" in levels:
        lines.append(f"- 50 SMA: {levels['50_sma']}")
    if "200_sma" in levels:
        lines.append(f"- 200 SMA: {levels['200_sma']}")
    if "key_support" in levels:
        lines.append(f"- Key support: {levels['key_support']}")
    if "key_resistance" in levels:
        lines.append(f"- Key resistance: {levels['key_resistance']}")
    return "\n".join(lines)


def format_compact_header(
    ticker: str,
    report_date: str,
    close_price: Optional[str],
    *,
    report_age_days: Optional[int] = None,
) -> str:
    lines = ["### Report context"]
    if ticker:
        lines.append(f"- Ticker: {ticker}")
    if report_date:
        lines.append(f"- Report date: {report_date}")
    if report_age_days is not None:
        lines.append(f"- Report age: {report_age_days} calendar day(s)")
    if close_price:
        lines.append(f"- Report close: ₹{close_price.lstrip('₹$')}")
    return "\n".join(lines)


def format_report_excerpt(
    market_text: str,
    *,
    ticker: str = "",
    report_date: str = "",
    as_of: Optional[str] = None,
    pm_summary: Optional[Dict[str, Any]] = None,
) -> str:
    """Build PM-facing excerpt: header + pm_summary + key levels + tail anchor slice."""
    if not market_text:
        return ""

    start = _find_excerpt_start(market_text)
    body = market_text[start:] if start is not None else market_text[-2500:]

    close_price = extract_report_close_price(market_text)
    key_levels = format_key_levels_block(parse_key_levels(market_text))
    summary = pm_summary if pm_summary is not None else extract_pm_summary(market_text)

    report_age: Optional[int] = None
    if report_date and as_of:
        try:
            as_of_d = datetime.strptime(as_of, "%Y-%m-%d").date()
            report_d = datetime.strptime(report_date, "%Y-%m-%d").date()
            report_age = (as_of_d - report_d).days
        except ValueError:
            report_age = None

    header = format_compact_header(
        ticker,
        report_date,
        close_price,
        report_age_days=report_age,
    )

    parts = [header]
    summary_block = format_pm_summary_block(summary)
    if summary_block:
        parts.append(summary_block)
    if key_levels:
        parts.append(key_levels)
    parts.append(body)
    return "\n\n".join(p for p in parts if p)


def report_age_days(report_date: str, as_of: str) -> Optional[int]:
    try:
        as_of_d = datetime.strptime(as_of, "%Y-%m-%d").date()
        report_d = datetime.strptime(report_date, "%Y-%m-%d").date()
        return (as_of_d - report_d).days
    except ValueError:
        return None
