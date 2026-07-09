"""Run the swing screener and print the ranked shortlist."""

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.screening.swing_screener import screen_swing


def main():
    config = DEFAULT_CONFIG.copy()
    print("Swing screener (early entry, top 10, no AI)...\n")
    picks = screen_swing(config, progress=lambda m: print(f"  {m}"))

    print("\n" + "=" * 96)
    print(f"TOP {len(picks)} PICK(S)")
    print("=" * 96)

    if not picks:
        print("No matches today.")
        return

    fmt = (
        f"{{:>2}}  {{:<12}} {{:<22}} {{:>9}} {{:>7}} {{:>6}} {{:>9}} {{:>6}} "
        f"{{:>9}} {{:>6}} {{:>7}} {{:>5}} {{:>5}} {{:>5}}"
    )
    print(
        fmt.format(
            "#", "Ticker", "Stock", "Entry", "Stop", "Stop%",
            "T1", "T1%", "T2", "T2%", "R:R", "RSI", "ADX", "Vol%",
        )
    )
    print("-" * 108)
    for i, p in enumerate(picks, 1):
        print(
            fmt.format(
                i,
                p.symbol.replace(".NS", ""),
                p.stock_name[:22],
                f"{p.entry_price:.2f}",
                f"{p.stop_loss:.2f}",
                f"{p.stop_loss_pct:.1f}%",
                f"{p.target_1:.2f}",
                f"+{p.target_1_pct:.1f}%",
                f"{p.target_2:.2f}",
                f"+{p.target_2_pct:.1f}%",
                f"{p.risk_reward_ratio:.1f}",
                f"{p.rsi:.1f}",
                f"{p.adx:.1f}",
                f"+{p.volume_spike_pct:.0f}%",
            )
        )
    print("\nAnalyze a pick: tradingagents analyze <TICKER>")


if __name__ == "__main__":
    main()
