"""Canonical daily OHLCV cache for the Nifty 500 universe.

One CSV per symbol (``{SYMBOL}.csv``) plus a ``manifest.json`` that tracks
last bar dates. Incremental sync fetches only the tail from Yahoo when data
is more than ~2 calendar days behind today.
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from glob import glob
from pathlib import Path
from typing import Dict, List, Literal, Optional

import pandas as pd
import yfinance as yf

from tradingagents.dataflows.config import get_config
from tradingagents.dataflows.nse_calendar import is_nse_trading_day
from tradingagents.dataflows.utils import symbol_cache_filename

logger = logging.getLogger(__name__)

MANIFEST_VERSION = 1
OHLCV_COLUMNS = ["Date", "Open", "High", "Low", "Close", "Volume"]
_STALE_DAYS = 2
_PERIOD_RE = re.compile(r"^(\d+)(y|mo|d)$", re.IGNORECASE)


@dataclass
class SyncReport:
    mode: str
    symbols_total: int = 0
    synced: int = 0
    skipped: int = 0
    failed: int = 0
    errors: List[str] = field(default_factory=list)


def _default_cache_dir(cache_dir: Optional[str] = None) -> str:
    if cache_dir is not None:
        return cache_dir
    return get_config()["data_cache_dir"]


def canonical_csv_path(symbol: str, cache_dir: Optional[str] = None) -> Path:
    """Return ``{cache_dir}/{SAFE_SYMBOL}.csv``."""
    safe = symbol_cache_filename(symbol)
    return Path(_default_cache_dir(cache_dir)) / f"{safe}.csv"


def legacy_csv_paths(symbol: str, cache_dir: Optional[str] = None) -> List[Path]:
    """Glob legacy ``*-YFin-data-*.csv`` files for *symbol*."""
    safe = symbol_cache_filename(symbol)
    pattern = str(Path(_default_cache_dir(cache_dir)) / f"{safe}-YFin-data-*.csv")
    return [Path(p) for p in glob(pattern)]


def _atomic_write_csv(df: pd.DataFrame, data_file: str | Path) -> None:
    """Write *df* atomically via a unique temp file in the same directory."""
    data_file = str(data_file)
    directory = os.path.dirname(data_file) or "."
    fd, tmp_file = tempfile.mkstemp(dir=directory, suffix=".tmp")
    os.close(fd)
    try:
        df.to_csv(tmp_file, index=False, encoding="utf-8")
        os.replace(tmp_file, data_file)
    except BaseException:
        try:
            os.remove(tmp_file)
        except OSError:
            pass
        raise


def _manifest_path(cache_dir: Optional[str] = None) -> Path:
    return Path(_default_cache_dir(cache_dir)) / "manifest.json"


def _load_manifest(cache_dir: Optional[str] = None) -> dict:
    path = _manifest_path(cache_dir)
    if not path.exists():
        return {"version": MANIFEST_VERSION, "symbols": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Could not read manifest %s (%s); starting fresh", path, e)
        return {"version": MANIFEST_VERSION, "symbols": {}}
    if "symbols" not in data:
        data["symbols"] = {}
    data["version"] = MANIFEST_VERSION
    return data


def _today_iso() -> str:
    return pd.Timestamp.today().normalize().strftime("%Y-%m-%d")


def expected_completed_session(now: Optional[pd.Timestamp] = None) -> pd.Timestamp:
    """Latest completed NSE session in IST (market close buffer: 16:00).

    Skips weekends and known NSE holidays from ``nse_calendar``.
    """
    current = now if now is not None else pd.Timestamp.now(tz="Asia/Kolkata")
    if current.tzinfo is None:
        current = current.tz_localize("Asia/Kolkata")
    else:
        current = current.tz_convert("Asia/Kolkata")
    session = current.normalize()
    if current.hour < 16:
        session -= pd.Timedelta(days=1)
    # Walk back until we land on a real NSE cash session.
    while True:
        day = session.date() if hasattr(session, "date") else session
        if is_nse_trading_day(day):
            break
        session -= pd.Timedelta(days=1)
    return session.tz_localize(None)


def manifest_eod_ran_today(cache_dir: Optional[str] = None) -> bool:
    """True when ``last_eod_run`` covers the latest completed NSE session."""
    manifest = _load_manifest(cache_dir)
    expected = expected_completed_session().strftime("%Y-%m-%d")
    return manifest.get("last_eod_run") == expected


def set_manifest_eod_run(cache_dir: Optional[str] = None) -> str:
    """Record the latest completed NSE session as the last successful EOD run."""
    manifest = _load_manifest(cache_dir)
    session = expected_completed_session().strftime("%Y-%m-%d")
    manifest["last_eod_run"] = session
    _save_manifest(manifest, cache_dir)
    return session


def get_manifest_eod_status(cache_dir: Optional[str] = None) -> dict:
    """Return manifest fields useful for dashboard EOD status."""
    manifest = _load_manifest(cache_dir)
    symbols = manifest.get("symbols", {})
    return {
        "last_eod_run": manifest.get("last_eod_run"),
        "symbol_count": len(symbols),
        "version": manifest.get("version", MANIFEST_VERSION),
    }


def _save_manifest(manifest: dict, cache_dir: Optional[str] = None) -> None:
    path = _manifest_path(cache_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    directory = str(path.parent)
    fd, tmp_file = tempfile.mkstemp(dir=directory, suffix=".tmp")
    os.close(fd)
    try:
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
            f.write("\n")
        os.replace(tmp_file, path)
    except BaseException:
        try:
            os.remove(tmp_file)
        except OSError:
            pass
        raise


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _normalise_bars(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure Date + OHLCV columns, sorted ascending, tz-naive dates."""
    if df is None or df.empty:
        return pd.DataFrame(columns=OHLCV_COLUMNS)

    out = df.copy()
    if "Date" not in out.columns:
        if isinstance(out.index, pd.DatetimeIndex):
            out = out.reset_index()
            if "Date" not in out.columns:
                for candidate in ("index", "Datetime", "datetime", "date"):
                    if candidate in out.columns:
                        out = out.rename(columns={candidate: "Date"})
                        break
        else:
            for candidate in ("index", "Datetime", "datetime", "date"):
                if candidate in out.columns:
                    out = out.rename(columns={candidate: "Date"})
                    break

    if "Date" not in out.columns:
        raise KeyError("Date column missing from OHLCV frame")

    out["Date"] = pd.to_datetime(out["Date"], errors="coerce")
    out = out.dropna(subset=["Date"])
    if out["Date"].dt.tz is not None:
        out["Date"] = out["Date"].dt.tz_localize(None)

    for col in ["Open", "High", "Low", "Close", "Volume"]:
        if col not in out.columns:
            out[col] = pd.NA
        out[col] = pd.to_numeric(out[col], errors="coerce")

    out = out.dropna(subset=["Close"])
    out = out[OHLCV_COLUMNS].drop_duplicates(subset=["Date"], keep="last")
    out = out.sort_values("Date").reset_index(drop=True)
    return out


def _last_bar_date(df: pd.DataFrame) -> Optional[pd.Timestamp]:
    if df is None or df.empty or "Date" not in df.columns:
        return None
    return pd.to_datetime(df["Date"].iloc[-1]).normalize()


def _needs_sync(
    symbol: str,
    manifest: dict,
    cache_dir: Optional[str] = None,
    *,
    mode: str = "incremental",
    require_through: Optional[pd.Timestamp] = None,
) -> bool:
    if mode == "full":
        return True

    today = pd.Timestamp.today().normalize()
    cutoff = today - pd.Timedelta(days=_STALE_DAYS)

    entry = manifest.get("symbols", {}).get(symbol, {})
    last_str = entry.get("last_bar")
    last: Optional[pd.Timestamp] = None
    if last_str:
        last = pd.to_datetime(last_str).normalize()

    # EOD / forced refresh: need bars through *require_through* (usually today).
    if require_through is not None:
        target = require_through.normalize()
        if last is not None and last >= target:
            return False
        path = canonical_csv_path(symbol, cache_dir)
        if path.exists():
            try:
                df = read_bars(symbol, cache_dir=cache_dir)
                last = _last_bar_date(df)
                if last is not None and last >= target:
                    return False
            except Exception:  # noqa: BLE001
                pass
        return True

    if last is not None and last > cutoff:
        return False

    path = canonical_csv_path(symbol, cache_dir)
    if path.exists():
        try:
            df = read_bars(symbol, cache_dir=cache_dir)
            last = _last_bar_date(df)
            if last is not None and last > cutoff:
                return False
        except Exception:  # noqa: BLE001
            pass
    return True


def _merge_bars(existing: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    if existing is None or existing.empty:
        return _normalise_bars(new)
    if new is None or new.empty:
        return _normalise_bars(existing)
    combined = pd.concat([_normalise_bars(existing), _normalise_bars(new)], ignore_index=True)
    combined = combined.drop_duplicates(subset=["Date"], keep="last")
    return combined.sort_values("Date").reset_index(drop=True)


def _first_bar_date(df: pd.DataFrame) -> Optional[pd.Timestamp]:
    if df is None or df.empty or "Date" not in df.columns:
        return None
    return pd.to_datetime(df["Date"].iloc[0]).normalize()


def _update_manifest_symbol(
    manifest: dict,
    symbol: str,
    df: pd.DataFrame,
) -> None:
    last = _last_bar_date(df)
    first = _first_bar_date(df)
    manifest.setdefault("symbols", {})[symbol] = {
        "first_bar": first.strftime("%Y-%m-%d") if first is not None else None,
        "last_bar": last.strftime("%Y-%m-%d") if last is not None else None,
        "rows": len(df),
        "synced_at": _utc_now_iso(),
    }


def read_bars_as_of(
    symbol: str,
    as_of_date: str,
    *,
    start_date: Optional[str] = None,
    cache_dir: Optional[str] = None,
) -> pd.DataFrame:
    """Point-in-time OHLCV for *symbol* (SQLite first, CSV fallback)."""
    try:
        from tradingagents.dataflows.ohlcv_db import read_bars_as_of as read_bars_as_of_db

        db_bars = read_bars_as_of_db(
            symbol,
            as_of_date,
            start_date=start_date,
        )
        if db_bars is not None and not db_bars.empty:
            return db_bars
    except Exception as e:  # noqa: BLE001
        logger.debug("SQLite as-of read failed for %s (%s); falling back to CSV", symbol, e)

    bars = read_bars(symbol, cache_dir=cache_dir)
    if bars.empty:
        return bars
    as_of = pd.Timestamp(as_of_date).normalize()
    if start_date:
        start = pd.Timestamp(start_date).normalize()
        bars = bars[bars["Date"] >= start]
    return bars[bars["Date"] <= as_of].reset_index(drop=True)


def read_bars(symbol: str, cache_dir: Optional[str] = None) -> pd.DataFrame:
    """Read OHLCV for *symbol* (SQLite first, then canonical CSV)."""
    try:
        from tradingagents.dataflows.ohlcv_db import read_bars as read_bars_db

        db_bars = read_bars_db(symbol)
        if db_bars is not None and not db_bars.empty:
            return db_bars
    except Exception as e:  # noqa: BLE001
        logger.debug("SQLite read failed for %s (%s); falling back to CSV", symbol, e)

    path = canonical_csv_path(symbol, cache_dir)
    if not path.exists():
        return pd.DataFrame(columns=OHLCV_COLUMNS)
    try:
        raw = pd.read_csv(path, on_bad_lines="skip", encoding="utf-8")
    except pd.errors.EmptyDataError:
        return pd.DataFrame(columns=OHLCV_COLUMNS)
    return _normalise_bars(raw)


def write_bars(
    symbol: str,
    df: pd.DataFrame,
    cache_dir: Optional[str] = None,
) -> None:
    """Atomically write OHLCV bars for *symbol* (SQLite + CSV)."""
    cache_dir = _default_cache_dir(cache_dir)
    normalized = _normalise_bars(df)
    try:
        from tradingagents.dataflows.ohlcv_db import export_symbol_csv, upsert_bars

        upsert_bars(symbol, normalized)
        export_symbol_csv(symbol, cache_dir)
    except Exception as e:  # noqa: BLE001
        logger.warning("SQLite upsert/export failed for %s (%s)", symbol, e)

    path = canonical_csv_path(symbol, cache_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_csv(normalized, path)


def _period_to_start(period: str) -> pd.Timestamp:
    """Map yfinance-style period strings to a start date."""
    period = period.strip().lower()
    m = _PERIOD_RE.match(period)
    if not m:
        raise ValueError(f"Unsupported period: {period!r}")
    n, unit = int(m.group(1)), m.group(2).lower()
    today = pd.Timestamp.today().normalize()
    if unit == "y":
        return today - pd.DateOffset(years=n)
    if unit == "mo":
        return today - pd.DateOffset(months=n)
    return today - pd.Timedelta(days=n)


def _to_screener_frame(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """Convert canonical bars to the DatetimeIndex frame ``download_history`` returns."""
    if df is None or df.empty:
        return None
    out = df.copy()
    out = out.set_index("Date")
    if out.index.tz is not None:
        out.index = out.index.tz_localize(None)
    if len(out) < 2 or "Close" not in out.columns:
        return None
    return out


def read_history(
    tickers: List[str],
    period: str = "1y",
    cache_dir: Optional[str] = None,
) -> Dict[str, pd.DataFrame]:
    """Read OHLCV from the canonical store, filtered to *period*.

    Returns ``{symbol: DataFrame}`` in the same shape as ``download_history``.
    """
    out: Dict[str, pd.DataFrame] = {}
    if not tickers:
        return out

    start = _period_to_start(period)
    for sym in tickers:
        try:
            bars = read_bars(sym, cache_dir=cache_dir)
        except ValueError:
            continue
        if bars.empty:
            continue
        bars = bars[bars["Date"] >= start]
        frame = _to_screener_frame(bars)
        if frame is not None:
            out[sym] = frame
    return out


def _yf_retry(func, max_retries: int = 3, base_delay: float = 2.0):
    """Lazy import of ``yf_retry`` to avoid circular imports with stockstats_utils."""
    from tradingagents.dataflows.stockstats_utils import yf_retry

    return yf_retry(func, max_retries=max_retries, base_delay=base_delay)


def _extract_yf(raw: pd.DataFrame, symbol: str) -> Optional[pd.DataFrame]:
    """Pull one ticker from a yfinance batch download (mirrors prices._extract)."""
    cols = raw.columns
    if not isinstance(cols, pd.MultiIndex):
        df = raw
    else:
        df = None
        for level in range(cols.nlevels):
            if symbol in cols.get_level_values(level):
                df = raw.xs(symbol, axis=1, level=level)
                break
        if df is None:
            return None

    if df is None or df.empty or "Close" not in df.columns:
        return None
    df = df.dropna(subset=["Close"])
    if len(df) < 1:
        return None
    if isinstance(df.index, pd.DatetimeIndex) and df.index.tz is not None:
        df = df.copy()
        df.index = df.index.tz_localize(None)
    return df.reset_index()


def _download_batch(
    symbols: List[str],
    *,
    period: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> Dict[str, pd.DataFrame]:
    if not symbols:
        return {}

    def _fetch():
        kwargs: dict = {
            "interval": "1d",
            "group_by": "ticker",
            "auto_adjust": True,
            "progress": False,
            "threads": True,
        }
        if start is not None:
            kwargs["start"] = start
            if end is not None:
                kwargs["end"] = end
        else:
            kwargs["period"] = period or "5y"
        return yf.download(symbols, **kwargs)

    try:
        raw = _yf_retry(_fetch)
    except Exception as e:  # noqa: BLE001
        logger.warning("yfinance batch download failed (%s)", e)
        return {}

    if raw is None or raw.empty:
        return {}

    out: Dict[str, pd.DataFrame] = {}
    for sym in symbols:
        df = _extract_yf(raw, sym)
        if df is not None:
            out[sym] = _normalise_bars(df)
    return out


def sync_price_cache(
    universe: List[str],
    mode: Literal["incremental", "full"] = "incremental",
    period: str = "5y",
    batch_size: int = 100,
    cache_dir: Optional[str] = None,
    *,
    require_through: Optional[str] = None,
) -> SyncReport:
    """Sync canonical OHLCV CSVs from Yahoo for *universe*.

    When *require_through* is set (YYYY-MM-DD, usually today), symbols whose
    last bar is older than that date are refreshed — used by the EOD pipeline
    so a 15 Jul bar is not treated as fresh on 16 Jul evening.
    """
    cache_dir = _default_cache_dir(cache_dir)
    os.makedirs(cache_dir, exist_ok=True)

    report = SyncReport(mode=mode, symbols_total=len(universe))
    manifest = _load_manifest(cache_dir)
    through_ts = (
        pd.to_datetime(require_through).normalize() if require_through else None
    )

    to_sync: List[str] = []
    for sym in universe:
        try:
            symbol_cache_filename(sym)
        except ValueError as e:
            report.failed += 1
            report.errors.append(f"{sym}: {e}")
            continue
        if _needs_sync(sym, manifest, cache_dir, mode=mode, require_through=through_ts):
            to_sync.append(sym)
        else:
            report.skipped += 1

    today = pd.Timestamp.today().normalize()
    end_str = (today + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

    for start_idx in range(0, len(to_sync), batch_size):
        batch = to_sync[start_idx : start_idx + batch_size]
        if mode == "full":
            fetched = _download_batch(batch, period=period)
        else:
            # Incremental: fetch a short tail window per symbol batch.
            # Use the earliest last_bar in the batch minus a small buffer.
            starts: List[pd.Timestamp] = []
            for sym in batch:
                existing = read_bars(sym, cache_dir=cache_dir)
                last = _last_bar_date(existing)
                if last is not None:
                    starts.append(last - pd.Timedelta(days=5))
                else:
                    starts.append(_period_to_start(period))
            batch_start = min(starts).strftime("%Y-%m-%d")
            fetched = _download_batch(batch, start=batch_start, end=end_str)

        for sym in batch:
            new_bars = fetched.get(sym)
            if new_bars is None or new_bars.empty:
                report.failed += 1
                report.errors.append(f"{sym}: no data from Yahoo")
                continue
            try:
                if mode == "full":
                    merged = new_bars
                else:
                    existing = read_bars(sym, cache_dir=cache_dir)
                    merged = _merge_bars(existing, new_bars)
                from tradingagents.dataflows.ohlcv_db import upsert_bars

                upsert_bars(sym, merged)
                write_bars(sym, merged, cache_dir=cache_dir)
                _update_manifest_symbol(manifest, sym, merged)
                report.synced += 1
            except Exception as e:  # noqa: BLE001
                report.failed += 1
                report.errors.append(f"{sym}: {e}")

    _save_manifest(manifest, cache_dir)
    return report


def sync_symbol(
    symbol: str,
    mode: Literal["incremental", "full"] = "incremental",
    period: str = "5y",
    cache_dir: Optional[str] = None,
) -> SyncReport:
    """Sync a single symbol (used by ``load_ohlcv`` on cache miss/stale)."""
    return sync_price_cache(
        [symbol],
        mode=mode,
        period=period,
        batch_size=1,
        cache_dir=cache_dir,
    )


def migrate_legacy_cache(cache_dir: Optional[str] = None) -> int:
    """Merge legacy ``*-YFin-data-*.csv`` files into canonical ``{SYMBOL}.csv``.

    Returns the number of symbols migrated.
    """
    cache_dir = _default_cache_dir(cache_dir)
    cache_path = Path(cache_dir)
    if not cache_path.exists():
        return 0

    legacy_re = re.compile(r"^(.+)-YFin-data-.+\.csv$", re.IGNORECASE)
    by_symbol: Dict[str, List[Path]] = {}
    for file in cache_path.glob("*-YFin-data-*.csv"):
        m = legacy_re.match(file.name)
        if not m:
            continue
        sym = m.group(1)
        by_symbol.setdefault(sym, []).append(file)

    manifest = _load_manifest(cache_dir)
    migrated = 0

    for sym, paths in by_symbol.items():
        try:
            symbol_cache_filename(sym)
        except ValueError:
            logger.warning("Skipping legacy migration for unsafe symbol %s", sym)
            continue

        frames: List[pd.DataFrame] = []
        for p in sorted(paths):
            try:
                raw = pd.read_csv(p, on_bad_lines="skip", encoding="utf-8")
                frames.append(_normalise_bars(raw))
            except Exception as e:  # noqa: BLE001
                logger.warning("Could not read legacy cache %s (%s)", p, e)

        if not frames:
            continue

        merged = frames[0]
        for f in frames[1:]:
            merged = _merge_bars(merged, f)

        existing = read_bars(sym, cache_dir=cache_dir)
        if not existing.empty:
            merged = _merge_bars(existing, merged)

        write_bars(sym, merged, cache_dir=cache_dir)
        _update_manifest_symbol(manifest, sym, merged)

        for p in paths:
            try:
                p.unlink()
            except OSError as e:
                logger.warning("Could not delete legacy file %s (%s)", p, e)

        migrated += 1

    if migrated:
        _save_manifest(manifest, cache_dir)
    return migrated
