"""Clear closed P&L history and resize open positions to current desk capital rules.

Uses DEFAULT_CONFIG desk_capital (INR 2L) and each book's max_positions (20 x INR 10k).
Also covers gap_fill and tech_desk.

  python scripts/reset_paper_capital.py

For exit-oversize + top-up + screener fill, prefer:
  python scripts/enforce_desk_slots.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.gap_fill.book import GapFillPositionBook
from tradingagents.momentum.book import MomentumPositionBook
from tradingagents.nss.book import NSSPositionBook
from tradingagents.nw_envelope.book import NwEnvelopePositionBook
from tradingagents.paper.sizing import clear_closed_and_resize_open
from tradingagents.pattern_forecast.book import PatternForecastPositionBook
from tradingagents.supertrend_rsi.book import SuperTrendRSIPositionBook
from tradingagents.swing.book import SwingPositionBook
from tradingagents.tech_desk.book import TechDeskPositionBook
from tradingagents.trama.book import TramaPositionBook

BOOKS = [
    ("swing", SwingPositionBook, "swing_max_positions"),
    ("momentum", MomentumPositionBook, "momentum_max_positions"),
    ("nss", NSSPositionBook, "nss_max_positions"),
    ("supertrend_rsi", SuperTrendRSIPositionBook, "strsi_max_positions"),
    ("trama", TramaPositionBook, "trama_max_positions"),
    ("gap_fill", GapFillPositionBook, "gap_fill_max_positions"),
    ("nw_envelope", NwEnvelopePositionBook, "nwe_max_positions"),
    ("pattern_forecast", PatternForecastPositionBook, "pattern_forecast_max_positions"),
    ("tech_desk", TechDeskPositionBook, "tech_desk_max_positions"),
]


def main() -> None:
    config = DEFAULT_CONFIG.copy()
    print(f"Desk capital: INR {config['desk_capital']:,.0f} per strategy\n")

    for name, book_cls, _max_key in BOOKS:
        book = book_cls(config)
        open_before = book.open_count()
        closed_before = sum(1 for p in book.positions if p.get("status") == "closed")
        cleared, resized = clear_closed_and_resize_open(
            book.positions,
            book.desk_capital,
            book.max_positions,
        )
        dropped = 0
        kept = []
        for p in book.positions:
            if p.get("status") == "open" and int(p.get("shares") or 0) < 1:
                dropped += 1
                continue
            kept.append(p)
        book.positions[:] = kept
        book._save()
        print(
            f"  {name:<16} cleared={cleared} (was {closed_before} closed) "
            f"open={open_before}->{book.open_count()} resized={resized} "
            f"dropped_unfit={dropped} max_positions={book.max_positions} "
            f"alloc/slot=INR {book.desk_capital / max(book.max_positions, 1):,.0f}"
        )

    print("\nDone — closed history removed, open positions resized.")


if __name__ == "__main__":
    main()
