"""Run swing screener only and print results."""

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.screening.swing_screener import screen_swing
from tradingagents.swing import SwingPositionBook

config = DEFAULT_CONFIG.copy()
print("Swing screener (daily 1D) - RSI 50-65, ST flip within 3d\n")
picks = screen_swing(config, progress=lambda m: print(f"  {m}"))

print("\n" + "=" * 88)
print(f"SCREENER RESULT: {len(picks)} pick(s)")
print("=" * 88)

if picks:
    fmt = (
        f"{{:>2}}  {{:<12}} {{:<24}} {{:>8}} {{:>7}} {{:>6}} {{:>9}} {{:>6}} "
        f"{{:>4}} {{:>5}} {{:>5}}"
    )
    print(
        fmt.format(
            "#", "Ticker", "Stock", "Entry", "Stop", "Risk%",
            "T2", "T2%", "R:R", "RSI", "ADX",
        )
    )
    print("-" * 88)
    for i, p in enumerate(picks, 1):
        print(
            fmt.format(
                i,
                p.symbol.replace(".NS", ""),
                p.stock_name[:24],
                f"{p.entry_price:.2f}",
                f"{p.stop_loss:.2f}",
                f"{p.risk_pct:.1f}%",
                f"{p.target_2:.2f}",
                f"+{p.target_2_pct:.1f}%",
                f"{p.risk_reward_ratio:.1f}",
                f"{p.rsi:.1f}",
                f"{p.adx:.1f}",
            )
        )
else:
    print("No stocks matched all criteria today.")

book = SwingPositionBook(config)
open_n = book.open_count()
print(f"\nOpen portfolio: {open_n}/20")
if open_n:
    print("Held:", ", ".join(p["ticker"].replace(".NS", "") for p in book.positions if p.get("status") == "open"))
