"""Clear closed P&L history and resize open positions to ₹1L desk capital rules."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.momentum.book import MomentumPositionBook
from tradingagents.nss.book import NSSPositionBook
from tradingagents.pattern_forecast.book import PatternForecastPositionBook
from tradingagents.paper.sizing import clear_closed_and_resize_open
from tradingagents.supertrend_rsi.book import SuperTrendRSIPositionBook
from tradingagents.swing.book import SwingPositionBook
from tradingagents.trama.book import TramaPositionBook
from tradingagents.nw_envelope.book import NwEnvelopePositionBook

BOOKS = [
    ("swing", SwingPositionBook, "swing_max_positions"),
    ("momentum", MomentumPositionBook, "momentum_max_positions"),
    ("nss", NSSPositionBook, "nss_max_positions"),
    ("supertrend_rsi", SuperTrendRSIPositionBook, "strsi_max_positions"),
    ("trama", TramaPositionBook, "trama_max_positions"),
    ("nw_envelope", NwEnvelopePositionBook, "nwe_max_positions"),
    ("pattern_forecast", PatternForecastPositionBook, "pattern_forecast_max_positions"),
]


def main() -> None:
    config = DEFAULT_CONFIG.copy()
    print(f"Desk capital: INR {config['desk_capital']:,.0f} per strategy\n")

    for name, book_cls, max_key in BOOKS:
        book = book_cls(config)
        open_before = book.open_count()
        closed_before = sum(1 for p in book.positions if p.get("status") == "closed")
        cleared, resized = clear_closed_and_resize_open(
            book.positions,
            book.desk_capital,
            book.max_positions,
        )
        book._save()
        print(
            f"  {name:<16} cleared={cleared} (was {closed_before} closed) "
            f"open={open_before} resized={resized} "
            f"max_positions={book.max_positions} "
            f"alloc/slot=INR {book.desk_capital / max(book.max_positions, 1):,.0f}"
        )
        if open_before:
            sample = next(p for p in book.positions if p.get("status") == "open")
            print(
                f"      sample {sample['ticker']}: "
                f"shares={sample.get('shares')} notional=INR {sample.get('notional')}"
            )

    print("\nDone — closed history removed, open positions resized.")


if __name__ == "__main__":
    main()
