"""Emit daily OHLCV bars as JSON for the dashboard chart API (SQLite-first read path)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tradingagents.dataflows.ohlcv_store import read_bars
from tradingagents.screening.universe import _normalise_symbol


def _float_or(value, fallback: float) -> float:
    try:
        if pd.isna(value):
            return fallback
        return float(value)
    except (TypeError, ValueError):
        return fallback


def main() -> None:
    if len(sys.argv) < 2:
        print("[]")
        sys.exit(1)

    symbol = _normalise_symbol(sys.argv[1])
    if not symbol:
        print("[]")
        sys.exit(1)

    df = read_bars(symbol)
    if df.empty:
        print("[]")
        return

    bars = []
    for _, row in df.iterrows():
        dt = row["Date"]
        time = dt.strftime("%Y-%m-%d") if hasattr(dt, "strftime") else str(dt)[:10]
        close = _float_or(row["Close"], 0.0)
        if not time or close <= 0:
            continue
        open_ = _float_or(row["Open"], close)
        high = _float_or(row["High"], close)
        low = _float_or(row["Low"], close)
        vol = _float_or(row["Volume"], 0.0)
        bars.append(
            {
                "time": time,
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": vol,
            }
        )

    print(json.dumps(bars))


if __name__ == "__main__":
    main()
