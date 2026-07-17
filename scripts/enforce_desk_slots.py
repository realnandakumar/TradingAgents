"""Enforce ₹2L desks: 20 slots × ₹10k (strict never exceed).

1. Report open positions that are over slot or cannot fit (no forced exits).
2. Top up eligible opens to floor(₹10k / entry) shares at purchase price.
3. Re-screen and fill vacancies up to 20 per desk.

Usage:
  python scripts/enforce_desk_slots.py
  python scripts/enforce_desk_slots.py --dry-run
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.gap_fill import GapFillPaperTradeManager
from tradingagents.gap_fill.book import GapFillPositionBook
from tradingagents.momentum import MomentumPaperTradeManager
from tradingagents.momentum.book import MomentumPositionBook
from tradingagents.nss import NSSPaperTradeManager
from tradingagents.nss.book import NSSPositionBook
from tradingagents.nw_envelope import NwEnvelopePaperTradeManager
from tradingagents.nw_envelope.book import NwEnvelopePositionBook
from tradingagents.paper.sizing import compute_position_size, resize_open_position
from tradingagents.pattern_forecast import PatternForecastPaperTradeManager
from tradingagents.pattern_forecast.book import PatternForecastPositionBook
from tradingagents.screening.gap_fill_screener import screen_gap_fill
from tradingagents.screening.momentum_screener import screen_momentum
from tradingagents.screening.nss_screener import screen_nss
from tradingagents.screening.nw_envelope_screener import screen_nw_envelope
from tradingagents.screening.pattern_forecast_screener import screen_pattern_forecast
from tradingagents.screening.prices import read_history
from tradingagents.screening.supertrend_rsi_screener import screen_supertrend_rsi
from tradingagents.screening.swing_screener import screen_swing
from tradingagents.screening.trama_screener import screen_trama
from tradingagents.screening.universe import load_universe
from tradingagents.supertrend_rsi import SuperTrendRSIPaperTradeManager
from tradingagents.supertrend_rsi.book import SuperTrendRSIPositionBook
from tradingagents.swing import PortfolioPaperTradeManager as SwingPaperTradeManager
from tradingagents.swing.book import SwingPositionBook
from tradingagents.tech_desk.book import TechDeskPositionBook
from tradingagents.trama import TramaPaperTradeManager
from tradingagents.trama.book import TramaPositionBook

SLOT_EPS = 0.01  # treat notional > alloc + eps as oversize


DESKS = [
    ("swing", SwingPositionBook, SwingPaperTradeManager, screen_swing, "swing_max_positions"),
    ("momentum", MomentumPositionBook, MomentumPaperTradeManager, screen_momentum, "momentum_max_positions"),
    ("nss", NSSPositionBook, NSSPaperTradeManager, screen_nss, "nss_max_positions"),
    ("supertrend_rsi", SuperTrendRSIPositionBook, SuperTrendRSIPaperTradeManager, screen_supertrend_rsi, "strsi_max_positions"),
    ("trama", TramaPositionBook, TramaPaperTradeManager, screen_trama, "trama_max_positions"),
    ("gap_fill", GapFillPositionBook, GapFillPaperTradeManager, screen_gap_fill, "gap_fill_max_positions"),
    ("nw_envelope", NwEnvelopePositionBook, NwEnvelopePaperTradeManager, screen_nw_envelope, "nwe_max_positions"),
    ("pattern_forecast", PatternForecastPositionBook, PatternForecastPaperTradeManager, screen_pattern_forecast, "pattern_forecast_max_positions"),
]


def _notional(p: dict) -> float:
    if p.get("notional") is not None:
        return float(p["notional"])
    return float(p.get("shares") or 0) * float(p.get("entry_price") or 0)


def _classify(p: dict, slot: float) -> str:
    entry = float(p.get("entry_price") or 0)
    if entry <= 0:
        return "bad"
    if entry > slot:
        return "unfit"
    if _notional(p) > slot + SLOT_EPS:
        return "over"
    target = compute_position_size(slot * 20, 20, entry)  # relative only for shares
    # Use actual desk sizing below; here just under check vs slot
    if _notional(p) < slot * 0.99 and int(p.get("shares") or 0) < int(
        compute_position_size(200_000, 20, entry)["shares"]
    ):
        return "under"
    return "ok"


def enforce_book(book, *, dry_run: bool, today: str) -> dict:
    slot = book.desk_capital / max(book.max_positions, 1)
    summary = {
        "open_before": book.open_count(),
        "exited": [],
        "blocked": [],
        "topped_up": [],
        "unchanged": [],
        "slot": slot,
        "max_positions": book.max_positions,
        "desk_capital": book.desk_capital,
    }

    opens = [p for p in book.positions if p.get("status") == "open"]
    for p in list(opens):
        entry = float(p.get("entry_price") or 0)
        notion = _notional(p)
        ticker = p["ticker"]
        kind = "ok"
        if entry <= 0:
            kind = "bad"
        elif entry > slot:
            kind = "unfit"
        elif notion > slot + SLOT_EPS:
            kind = "over"

        if kind in {"unfit", "over", "bad"}:
            summary["blocked"].append(f"{ticker}({kind},n={notion:.0f})")
            continue

        before_sh = int(p.get("shares") or 0)
        before_n = notion
        if dry_run:
            sizing = compute_position_size(book.desk_capital, book.max_positions, entry)
            if sizing["shares"] != before_sh or abs(sizing["notional"] - before_n) > SLOT_EPS:
                summary["topped_up"].append(
                    f"{ticker}:{before_sh}->{sizing['shares']} (INR {before_n:.0f}->INR {sizing['notional']:.0f})"
                )
            else:
                summary["unchanged"].append(ticker)
        else:
            resize_open_position(p, book.desk_capital, book.max_positions)
            if int(p.get("shares") or 0) != before_sh or abs(float(p.get("notional") or 0) - before_n) > SLOT_EPS:
                summary["topped_up"].append(
                    f"{ticker}:{before_sh}->{p['shares']} (INR {before_n:.0f}->INR {p['notional']:.0f})"
                )
            else:
                summary["unchanged"].append(ticker)

    if not dry_run:
        book._save()
    summary["open_after_resize"] = (
        summary["open_before"] - len(summary["exited"])
        if dry_run
        else book.open_count()
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Enforce 20×₹10k desk slots")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-fill", action="store_true", help="Only exit/top-up, do not re-screen")
    args = parser.parse_args()

    config = DEFAULT_CONFIG.copy()
    today = datetime.now().strftime("%Y-%m-%d")
    capital = float(config["desk_capital"])
    print(
        f"Desk capital INR {capital:,.0f} · target 20 x INR {capital/20:,.0f} slots"
        f"{' [DRY RUN]' if args.dry_run else ''}\n"
    )

    # --- Phase 1: exit oversize / top-up under ---
    book_summaries = {}
    for name, book_cls, _mgr, _screen, _max_key in DESKS:
        book = book_cls(config)
        summary = enforce_book(book, dry_run=args.dry_run, today=today)
        book_summaries[name] = summary
        print(
            f"  {name:<18} open {summary['open_before']:>2} → {summary['open_after_resize']:>2}  "
            f"exit={len(summary['exited'])} topup={len(summary['topped_up'])} ok={len(summary['unchanged'])}"
        )
        if summary["exited"]:
            print(f"      exited: {', '.join(summary['exited'][:12])}")
        if summary["topped_up"][:5]:
            print(f"      top-up: {', '.join(summary['topped_up'][:5])}"
                  + ("…" if len(summary["topped_up"]) > 5 else ""))

    # Tech desk: resize / exit only (no screener fill here)
    tech = TechDeskPositionBook(config)
    tech_summary = enforce_book(tech, dry_run=args.dry_run, today=today)
    book_summaries["tech_desk"] = tech_summary
    print(
        f"  {'tech_desk':<18} open {tech_summary['open_before']:>2} → {tech_summary['open_after_resize']:>2}  "
        f"exit={len(tech_summary['exited'])} topup={len(tech_summary['topped_up'])} "
        f"ok={len(tech_summary['unchanged'])}  (fill via Command Center / tech reports)"
    )

    if args.dry_run or args.skip_fill:
        print("\nDone (no fill).")
        return

    # --- Phase 2: screen + fill vacancies ---
    print("\nLoading price history for fill…")
    universe = load_universe(
        csv_path=config.get("screen_universe_csv"),
        cache_dir=config.get("data_cache_dir"),
        allow_download=True,
    )
    price_data = read_history(universe, period="2y", cache_dir=config.get("data_cache_dir"))
    print(f"  history for {len(price_data)} symbols\n")

    for name, book_cls, mgr_cls, screen_fn, _max_key in DESKS:
        book = book_cls(config)
        vacancies = book.max_positions - book.open_count()
        if vacancies <= 0:
            print(f"  {name:<18} full ({book.open_count()}/{book.max_positions})")
            continue
        print(f"  {name:<18} filling {vacancies} slots…")
        picks = screen_fn(config, price_data=price_data)
        mgr = mgr_cls(config)
        report = mgr.run_daily(picks, screen_date=today, approve=None)
        print(
            f"      picks={len(picks)} opened={len(report.get('opened', []))} "
            f"open_now={report.get('open_positions', book.open_count())}"
        )

    print("\n=== Final open counts ===")
    for name, book_cls, *_ in DESKS:
        book = book_cls(config)
        overs = []
        for p in book.positions:
            if p.get("status") != "open":
                continue
            slot = book.desk_capital / book.max_positions
            n = _notional(p)
            if n > slot + SLOT_EPS or float(p.get("entry_price") or 0) > slot:
                overs.append(f"{p['ticker']}={n:.0f}")
        print(
            f"  {name:<18} {book.open_count():>2}/{book.max_positions}  "
            f"slot=INR {book.desk_capital/book.max_positions:,.0f}"
            + (f"  OVER: {', '.join(overs)}" if overs else "  OK all <= slot")
        )
    tech = TechDeskPositionBook(config)
    print(f"  {'tech_desk':<18} {tech.open_count():>2}/{tech.max_positions}  (manual fill)")
    print("\nDone.")


if __name__ == "__main__":
    main()
