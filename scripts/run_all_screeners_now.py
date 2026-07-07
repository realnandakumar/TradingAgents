"""Run all four screeners from a single shared Yahoo download.

Every strategy uses the same NSE universe, so we fetch 2y of daily history
once (a superset of each strategy's lookback) and pass it to all screeners.
This avoids downloading ~500 tickers four times.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.screening.momentum_screener import screen_momentum
from tradingagents.screening.nss_screener import screen_nss
from tradingagents.screening.prices import download_history
from tradingagents.screening.supertrend_rsi_screener import screen_supertrend_rsi
from tradingagents.screening.swing_screener import screen_swing
from tradingagents.screening.universe import load_universe

# Longest lookback any screener needs; a superset for the 1y ST+RSI screen too.
SHARED_PERIOD = "2y"


def _print_picks(title: str, picks: list, kind: str = "pick") -> None:
    print("\n" + "=" * 72)
    print(f"{title}: {len(picks)} {kind}(s)")
    print("=" * 72)
    for i, p in enumerate(picks, 1):
        sym = p.symbol.replace(".NS", "")
        if hasattr(p, "signal"):  # SuperTrend+RSI
            s = p.signal
            print(f"{i:>2}  {sym:<14} {s.direction:<4} score={s.score:<3} "
                  f"RSI={s.rsi:.1f} age={s.flip_age}")
        elif getattr(p, "composite_score", None) is not None:  # NSS
            print(f"{i:>2}  {sym:<14} score={p.composite_score:.0f} "
                  f"RSI={getattr(p, 'rsi', 0):.1f}")
        else:  # Swing / Momentum
            entry = getattr(p, "entry_price", 0)
            print(f"{i:>2}  {sym:<14} entry={entry:<10.2f} "
                  f"RSI={getattr(p, 'rsi', 0):.1f} ADX={getattr(p, 'adx', 0):.1f}")


def main() -> None:
    config = DEFAULT_CONFIG.copy()
    universe = load_universe(
        csv_path=config.get("screen_universe_csv"),
        cache_dir=config.get("data_cache_dir"),
    )

    print(f"Downloading {SHARED_PERIOD} history once for {len(universe)} tickers...")
    price_data = download_history(universe, period=SHARED_PERIOD)
    print(f"Got usable history for {len(price_data)} tickers.\n")

    swing = screen_swing(config, price_data=price_data)
    _print_picks("SWING", swing)

    momentum = screen_momentum(config, price_data=price_data)
    _print_picks("MOMENTUM", momentum)

    nss = screen_nss(config, price_data=price_data)
    _print_picks("NSS", nss)

    strsi = screen_supertrend_rsi(config, price_data=price_data)
    _print_picks("SUPERTREND+RSI", strsi, kind="signal")

    print("\n" + "=" * 72)
    print(f"TOTAL: swing={len(swing)} momentum={len(momentum)} "
          f"nss={len(nss)} supertrend_rsi={len(strsi)}")
    print("=" * 72)


if __name__ == "__main__":
    main()
