"""Run NSS screener only (no portfolio job)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.nss import NSSPositionBook
from tradingagents.screening.nss_screener import screen_nss


def main() -> None:
    config = DEFAULT_CONFIG.copy()
    print("NSS screener (daily 1D) - structure-first swing\n")
    picks = screen_nss(config, progress=lambda m: print(f"  {m}"))

    print()
    if not picks:
        print("SCREENER RESULT: 0 pick(s)")
        return

    fmt = (
        f"{{:>2}}  {{:<12}} {{:<22}} {{:>5}} {{:>8}} {{:>7}} {{:>6}} "
        f"{{:>9}} {{:>6}} {{:>4}} {{:>5}} {{:>6}}"
    )
    print("=" * 100)
    print(f"SCREENER RESULT: {len(picks)} pick(s)")
    print("=" * 100)
    print(fmt.format("#", "Ticker", "Stock", "Score", "Entry", "Stop", "Risk%", "T2", "T2%", "RSI", "ADX", "Vol"))
    print("-" * 100)
    for i, p in enumerate(picks, 1):
        print(
            fmt.format(
                i,
                p.symbol.replace(".NS", ""),
                p.stock_name[:22],
                f"{p.composite_score:.0f}",
                f"{p.entry_price:.2f}",
                f"{p.stop_loss:.2f}",
                f"{abs(p.stop_loss_pct):.1f}%",
                f"{p.target_2:.2f}",
                f"+{p.target_2_pct:.1f}%",
                f"{p.rsi:.1f}",
                f"{p.adx:.1f}",
                f"{p.relative_volume:.2f}x",
            )
        )

    book = NSSPositionBook(config)
    open_count = book.open_count()
    held = [p["ticker"].replace(".NS", "") for p in book.positions if p.get("status") == "open"]
    print(f"\nOpen portfolio: {open_count}/20")
    if held:
        print(f"Held: {', '.join(held)}")


if __name__ == "__main__":
    main()
