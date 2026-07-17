"""Load saved tech-analyze reports for Tech Desk processing."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from tradingagents.tech_desk.report_excerpt import extract_pm_summary

_REPORT_NAMES = ("market.md", "complete_report.md")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _ticker_match_keys(ticker: str) -> set[str]:
    """Match ``BHEL.NS`` folders to ``BHEL`` (and the reverse)."""
    u = (ticker or "").upper().strip()
    if not u:
        return set()
    keys = {u}
    for suf in (".NS", ".BO"):
        if u.endswith(suf):
            keys.add(u[: -len(suf)])
            return keys
    keys.add(f"{u}.NS")
    keys.add(f"{u}.BO")
    return keys


def _preferred_ticker(path_ticker: str, requested: Optional[List[str]]) -> str:
    """Prefer the caller’s symbol form (usually ``TICKER.NS``) over bare folder names."""
    path_keys = _ticker_match_keys(path_ticker)
    if requested:
        for wanted in requested:
            if path_keys & _ticker_match_keys(wanted):
                return wanted
    if "." not in path_ticker:
        return f"{path_ticker}.NS"
    return path_ticker


@dataclass
class TechReportSnapshot:
    ticker: str
    report_date: str
    report_dir: Path
    market_text: str
    source_file: str
    pm_summary: Optional[Dict[str, Any]] = None

    @property
    def report_path(self) -> str:
        return str(self.report_dir / self.source_file)


def _parse_date_from_path(path: Path) -> Optional[str]:
    """Extract YYYY-MM-DD from .../TICKER/DATE/... if present."""
    for part in reversed(path.parts):
        if _DATE_RE.match(part):
            return part
    return None


def _report_sort_key(snap: TechReportSnapshot) -> tuple:
    """Prefer path date, then complete report, then file mtime."""
    try:
        mtime = (snap.report_dir / snap.source_file).stat().st_mtime
    except OSError:
        mtime = 0.0
    source_priority = 1 if snap.source_file == "complete_report.md" else 0
    return (snap.report_date, source_priority, mtime)


def _read_report_file(report_dir: Path) -> Optional[tuple[str, str]]:
    for name in _REPORT_NAMES:
        path = report_dir / name
        if path.exists():
            try:
                return path.read_text(encoding="utf-8"), name
            except OSError:
                continue
    return None


def _report_age_days(report_date: str, as_of: str) -> int:
    as_of_d = datetime.strptime(as_of, "%Y-%m-%d").date()
    report_d = datetime.strptime(report_date, "%Y-%m-%d").date()
    return (as_of_d - report_d).days


def load_tech_reports(
    reports_dir: str | Path,
    *,
    tickers: Optional[List[str]] = None,
    max_report_age_days: Optional[int] = None,
    as_of: Optional[str] = None,
) -> Tuple[List[TechReportSnapshot], List[str]]:
    """Scan ``reports_dir`` recursively; return latest report per ticker.

    Expects layout ``TICKER/DATE/market.md`` or ``complete_report.md``.
    When duplicates exist, keeps the snapshot with the latest path date
    (or file mtime as tiebreaker). User deletes old reports manually.

    Returns ``(snapshots, stale_tickers)`` where stale tickers had a report
    but were skipped because ``max_report_age_days`` was exceeded.
    """
    root = Path(reports_dir).expanduser()
    if not root.exists():
        return [], []

    as_of = as_of or datetime.now().strftime("%Y-%m-%d")
    requested = list(tickers) if tickers else None
    filter_keys: Optional[set[str]] = None
    if tickers:
        filter_keys = set()
        for t in tickers:
            filter_keys |= _ticker_match_keys(t)
    by_ticker: dict[str, TechReportSnapshot] = {}
    stale_tickers: List[str] = []

    for report_path in root.rglob("*.md"):
        if report_path.name not in _REPORT_NAMES:
            continue

        report_dir = report_path.parent
        ticker = report_dir.parent.name if _DATE_RE.match(report_dir.name) else report_dir.name
        if not ticker or ticker.startswith("."):
            continue

        path_keys = _ticker_match_keys(ticker)
        if filter_keys is not None and not (path_keys & filter_keys):
            continue

        report_date = _parse_date_from_path(report_dir) or datetime.fromtimestamp(
            report_path.stat().st_mtime
        ).strftime("%Y-%m-%d")

        if max_report_age_days is not None:
            age = _report_age_days(report_date, as_of)
            if age > max_report_age_days:
                stale_tickers.append(ticker)
                continue

        content = report_path.read_text(encoding="utf-8")
        pm_summary = extract_pm_summary(content)
        summary_path = report_dir / "pm_summary.json"
        if summary_path.exists():
            try:
                import json as _json

                data = _json.loads(summary_path.read_text(encoding="utf-8"))
                if isinstance(data.get("pm_summary"), dict):
                    pm_summary = data["pm_summary"]
            except Exception:
                pass

        display_ticker = _preferred_ticker(ticker, requested)
        snap = TechReportSnapshot(
            ticker=display_ticker,
            report_date=report_date,
            report_dir=report_dir,
            market_text=content,
            source_file=report_path.name,
            pm_summary=pm_summary,
        )

        # Dedupe by exchange-stripped key so BHEL and BHEL.NS collapse
        dedupe_key = next(iter(sorted(k for k in path_keys if "." not in k)), display_ticker.upper())
        existing = by_ticker.get(dedupe_key)
        if existing is None or _report_sort_key(snap) > _report_sort_key(existing):
            by_ticker[dedupe_key] = snap

    stale_unique = sorted(
        {
            t
            for t in stale_tickers
            if not any(
                (_ticker_match_keys(t) & _ticker_match_keys(s.ticker)) for s in by_ticker.values()
            )
        }
    )
    return sorted(by_ticker.values(), key=lambda s: s.ticker), stale_unique
