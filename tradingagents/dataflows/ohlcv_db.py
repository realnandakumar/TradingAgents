"""SQLite backing store for canonical daily OHLCV bars."""

from __future__ import annotations

import logging
import os
import sqlite3
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from tradingagents.dataflows.config import get_config
from tradingagents.dataflows.ohlcv_store import (
    OHLCV_COLUMNS,
    _normalise_bars,
    _period_to_start,
    _to_screener_frame,
    canonical_csv_path,
)
from tradingagents.dataflows.utils import symbol_cache_filename

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ohlcv_daily (
    symbol TEXT NOT NULL,
    date TEXT NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume REAL,
    PRIMARY KEY (symbol, date)
);
CREATE INDEX IF NOT EXISTS idx_ohlcv_daily_symbol_date ON ohlcv_daily(symbol, date);

CREATE TABLE IF NOT EXISTS sync_meta (
    symbol TEXT PRIMARY KEY,
    last_bar TEXT,
    rows INTEGER,
    synced_at TEXT,
    active INTEGER DEFAULT 1,
    sources TEXT
);
"""


def _default_db_path(db_path: Optional[str] = None) -> Path:
    if db_path is not None:
        return Path(db_path).expanduser()
    cfg = get_config()
    configured = cfg.get("prices_db_path")
    if configured:
        return Path(configured).expanduser()
    home = os.path.join(os.path.expanduser("~"), ".tradingagents")
    return Path(home) / "prices.db"


def _connect(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = _default_db_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(_SCHEMA)
    return conn


def upsert_bars(
    symbol: str,
    df: pd.DataFrame,
    *,
    db_path: Optional[str] = None,
    sources: Optional[str] = None,
) -> None:
    """Upsert daily OHLCV bars and sync metadata for *symbol*."""
    bars = _normalise_bars(df)
    if bars.empty:
        return

    sym = symbol.strip().upper()
    with _connect(db_path) as conn:
        rows = [
            (
                sym,
                pd.Timestamp(row["Date"]).strftime("%Y-%m-%d"),
                float(row["Open"]) if pd.notna(row["Open"]) else None,
                float(row["High"]) if pd.notna(row["High"]) else None,
                float(row["Low"]) if pd.notna(row["Low"]) else None,
                float(row["Close"]) if pd.notna(row["Close"]) else None,
                float(row["Volume"]) if pd.notna(row["Volume"]) else None,
            )
            for _, row in bars.iterrows()
        ]
        conn.executemany(
            """
            INSERT INTO ohlcv_daily(symbol, date, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(symbol, date) DO UPDATE SET
                open=excluded.open,
                high=excluded.high,
                low=excluded.low,
                close=excluded.close,
                volume=excluded.volume
            """,
            rows,
        )
        last_bar = pd.Timestamp(bars["Date"].iloc[-1]).strftime("%Y-%m-%d")
        conn.execute(
            """
            INSERT INTO sync_meta(symbol, last_bar, rows, synced_at, active, sources)
            VALUES (?, ?, ?, datetime('now'), 1, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                last_bar=excluded.last_bar,
                rows=excluded.rows,
                synced_at=excluded.synced_at,
                active=1,
                sources=COALESCE(excluded.sources, sync_meta.sources)
            """,
            (sym, last_bar, len(bars), sources),
        )
        conn.commit()


def read_bars_db(
    symbol: str,
    *,
    start: Optional[str] = None,
    end: Optional[str] = None,
    db_path: Optional[str] = None,
) -> pd.DataFrame:
    """Read OHLCV bars for *symbol* from SQLite (empty frame if missing)."""
    sym = symbol.strip().upper()
    query = (
        "SELECT date, open, high, low, close, volume FROM ohlcv_daily "
        "WHERE symbol = ?"
    )
    params: List[str] = [sym]
    if start:
        query += " AND date >= ?"
        params.append(start)
    if end:
        query += " AND date <= ?"
        params.append(end)
    query += " ORDER BY date ASC"

    with _connect(db_path) as conn:
        cur = conn.execute(query, params)
        fetched = cur.fetchall()

    if not fetched:
        return pd.DataFrame(columns=OHLCV_COLUMNS)

    df = pd.DataFrame(fetched, columns=["Date", "Open", "High", "Low", "Close", "Volume"])
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    return _normalise_bars(df)


def read_history_db(
    tickers: List[str],
    period: str = "1y",
    *,
    db_path: Optional[str] = None,
) -> Dict[str, pd.DataFrame]:
    """Read OHLCV from SQLite filtered to *period* (screener frame shape)."""
    out: Dict[str, pd.DataFrame] = {}
    if not tickers:
        return out

    start = _period_to_start(period).strftime("%Y-%m-%d")
    for sym in tickers:
        try:
            bars = read_bars_db(sym, start=start, db_path=db_path)
        except ValueError:
            continue
        if bars.empty:
            continue
        frame = _to_screener_frame(bars)
        if frame is not None:
            out[sym] = frame
    return out


def export_symbol_csv(
    symbol: str,
    cache_dir: str,
    *,
    db_path: Optional[str] = None,
) -> Optional[Path]:
    """Export SQLite bars for *symbol* to the canonical CSV path."""
    try:
        symbol_cache_filename(symbol)
    except ValueError:
        logger.warning("Skipping CSV export for unsafe symbol %s", symbol)
        return None

    bars = read_bars_db(symbol, db_path=db_path)
    if bars.empty:
        return None

    path = canonical_csv_path(symbol, cache_dir=cache_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    directory = str(path.parent)
    fd, tmp_file = tempfile.mkstemp(dir=directory, suffix=".tmp")
    os.close(fd)
    try:
        bars.to_csv(tmp_file, index=False, encoding="utf-8")
        os.replace(tmp_file, path)
    except BaseException:
        try:
            os.remove(tmp_file)
        except OSError:
            pass
        raise
    return path


def count_symbols(db_path: Optional[str] = None) -> int:
    with _connect(db_path) as conn:
        row = conn.execute("SELECT COUNT(*) FROM sync_meta WHERE active = 1").fetchone()
    return int(row[0]) if row else 0


def count_stale_symbols(
    stale_days: int = 2,
    *,
    db_path: Optional[str] = None,
) -> int:
    cutoff = (pd.Timestamp.today().normalize() - pd.Timedelta(days=stale_days)).strftime(
        "%Y-%m-%d"
    )
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM sync_meta WHERE active = 1 AND (last_bar IS NULL OR last_bar < ?)",
            (cutoff,),
        ).fetchone()
    return int(row[0]) if row else 0
