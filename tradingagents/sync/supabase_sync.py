"""Best-effort Supabase publisher for dashboard snapshots.

Data contract -- a single ``snapshots`` table:

    create table snapshots (
        id          bigint generated always as identity primary key,
        kind        text not null,          -- 'screen' | 'paper'
        created_at  timestamptz not null default now(),
        data        jsonb not null
    );

The dashboard reads the latest ``kind='paper'`` row for P&L/stats and all
``kind='screen'`` rows for run history. We only ever INSERT (append-only), so
history is preserved and there is no update contention.

Credentials come from the environment:
- ``SUPABASE_URL``         e.g. https://abcd.supabase.co
- ``SUPABASE_SERVICE_KEY`` the service_role key (server-side only, never shipped
  to the browser; the frontend uses the anon key instead).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)


class SupabaseSync:
    """Thin client that inserts snapshot rows into the ``snapshots`` table."""

    def __init__(self, url: Optional[str] = None, service_key: Optional[str] = None,
                 table: str = "snapshots"):
        self.url = (url or os.getenv("SUPABASE_URL") or "").rstrip("/")
        # Accept the new secret key name (sb_secret_...) or the legacy service_role key.
        self.service_key = (
            service_key
            or os.getenv("SUPABASE_SECRET_KEY")
            or os.getenv("SUPABASE_SERVICE_KEY")
        )
        self.table = table

    @property
    def configured(self) -> bool:
        return bool(self.url and self.service_key)

    def push(self, kind: str, data: dict) -> bool:
        """Insert one snapshot row. Returns True on success, False otherwise.

        Never raises: network/credential problems are logged and swallowed so a
        sync failure can't break a screening run.
        """
        if not self.configured:
            logger.info("Supabase not configured (SUPABASE_URL/SERVICE_KEY); skipping sync")
            return False
        try:
            import requests

            resp = requests.post(
                f"{self.url}/rest/v1/{self.table}",
                headers={
                    "apikey": self.service_key,
                    "Authorization": f"Bearer {self.service_key}",
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal",
                },
                json={"kind": kind, "data": data},
                timeout=15,
            )
            if resp.status_code >= 300:
                logger.warning("Supabase sync failed (%s): %s", resp.status_code, resp.text[:200])
                return False
            logger.info("Synced %s snapshot to Supabase", kind)
            return True
        except Exception as e:  # noqa: BLE001 - sync must never break a run
            logger.warning("Supabase sync error: %s", e)
            return False


# --------------------------------------------------------------------------
# Snapshot serializers — turn in-memory objects into JSON-safe dicts.
# --------------------------------------------------------------------------

def screen_snapshot(trade_date: str, candidates: List, opened: Optional[List[str]] = None) -> dict:
    """Serialize a screen run (list of Candidate objects) for the dashboard."""
    opened = opened or []
    return {
        "trade_date": trade_date,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "opened": opened,
        "candidates": [
            {
                "rank": i + 1,
                "symbol": c.symbol,
                "rs_percentile": c.rs.rs_percentile,
                "rs_score": round(c.rs.rs_score, 4),
                "close": c.rs.close,
                "composite": round(c.composite, 3),
                "signals": c.fired_signals,
                "rating": c.decision_rating,
                "opened": c.symbol in opened,
            }
            for i, c in enumerate(candidates)
        ],
    }


def paper_snapshot(book) -> dict:
    """Serialize the paper book (positions + reliability stats)."""
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "capital": book.capital,
        "positions": book.positions,
        "stats": book.stats(),
    }


def sync_results(config: dict, trade_date: str, candidates: List,
                 opened: Optional[List[str]], book) -> bool:
    """Push both a screen snapshot and a paper snapshot. Returns True if both
    were sent (or short-circuits False if Supabase isn't configured)."""
    client = SupabaseSync()
    if not client.configured:
        return False
    ok1 = client.push("screen", screen_snapshot(trade_date, candidates, opened))
    ok2 = client.push("paper", paper_snapshot(book))
    return ok1 and ok2
