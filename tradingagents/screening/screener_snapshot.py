"""Write screener results to JSON for the Next.js dashboard."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any


def save_screener_snapshot(path: str, payload: dict[str, Any]) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    out = dict(payload)
    out["updated_at"] = datetime.now(timezone.utc).isoformat()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    return path
