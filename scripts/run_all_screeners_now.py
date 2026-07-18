"""Run all technical screeners from a single shared price store.

When the EOD pipeline already ran today, skips re-sync and reads from cache.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.dataflows.ohlcv_store import manifest_eod_ran_today, sync_price_cache
from tradingagents.dataflows.sync_symbols import collect_sync_symbols
from tradingagents.screening.momentum_screener import screen_momentum
from tradingagents.screening.nss_screener import screen_nss
from tradingagents.screening.prices import read_history
from tradingagents.screening.gap_fill_screener import screen_gap_fill
from tradingagents.screening.candle_screener import screen_candlesticks
from tradingagents.screening.chart_pattern_screener import screen_chart_patterns
from tradingagents.screening.nw_envelope_screener import screen_nw_envelope
from tradingagents.screening.pattern_forecast_screener import screen_pattern_forecast
from tradingagents.screening.supertrend_rsi_screener import screen_supertrend_rsi
from tradingagents.screening.swing_screener import screen_swing
from tradingagents.screening.trama_screener import screen_trama

SHARED_PERIOD = "2y"


def _print_picks(title: str, picks: list, kind: str = "pick") -> None:
    print("\n" + "=" * 72)
    print(f"{title}: {len(picks)} {kind}(s)")
    print("=" * 72)
    for i, p in enumerate(picks, 1):
        sym = p.symbol.replace(".NS", "")
        if hasattr(p, "signal") and hasattr(p.signal, "projected_close_5d"):
            s = p.signal
            print(f"{i:>2}  {sym:<14} {s.direction:<4} prob={s.probability:.1f}% "
                  f"proj5d={s.projected_close_5d:.2f} max5d={s.projected_max_high_5d:.2f}")
        elif hasattr(p, "signal") and hasattr(p.signal, "pattern_id"):
            s = p.signal
            print(f"{i:>2}  {sym:<14} {s.pattern_name:<22} {s.bias:<8} "
                  f"*{s.reliability} conf={s.confidence:.0f}")
        elif hasattr(p, "signal") and hasattr(p.signal, "gap_age"):
            s = p.signal
            print(f"{i:>2}  {sym:<14} {s.direction:<4} age={s.gap_age} "
                  f"gap={s.gap_pct:+.1f}% fill={s.fill_pct:.0f}%")
        elif hasattr(p, "signal") and hasattr(p.signal, "cross_age") and not hasattr(p.signal, "flip_age"):
            s = p.signal
            if hasattr(s, "fill_pct"):
                print(f"{i:>2}  {sym:<14} {s.direction:<4} age={s.gap_age} "
                      f"gap={s.gap_pct:+.1f}% fill={s.fill_pct:.0f}%")
            else:
                print(f"{i:>2}  {sym:<14} {s.direction:<4} age={s.cross_age} "
                      f"dist={s.dist_pct:+.1f}%")
        elif hasattr(p, "signal"):  # SuperTrend+RSI
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
    cache_dir = config.get("data_cache_dir")
    symbols = collect_sync_symbols(config)

    if manifest_eod_ran_today(cache_dir):
        print(f"EOD ran today — skipping sync, loading {SHARED_PERIOD} history for {len(symbols)} tickers...")
    else:
        print(f"Syncing price cache (incremental) for {len(symbols)} tickers...")
        sync_report = sync_price_cache(
            symbols,
            mode="incremental",
            cache_dir=cache_dir,
        )
        print(
            f"Cache sync: synced={sync_report.synced} skipped={sync_report.skipped} "
            f"failed={sync_report.failed}"
        )
        print(f"Loading {SHARED_PERIOD} history from cache...")

    price_data = read_history(symbols, period=SHARED_PERIOD, cache_dir=cache_dir)
    print(f"Got usable history for {len(price_data)} tickers.\n")

    swing = screen_swing(config, price_data=price_data)
    _print_picks("SWING", swing)

    momentum = screen_momentum(config, price_data=price_data)
    _print_picks("MOMENTUM", momentum)

    nss = screen_nss(config, price_data=price_data)
    _print_picks("NSS", nss)

    strsi = screen_supertrend_rsi(config, price_data=price_data)
    _print_picks("SUPERTREND+RSI", strsi, kind="signal")

    trama = screen_trama(config, price_data=price_data)
    _print_picks("TRAMA", trama, kind="signal")

    gap_fill = screen_gap_fill(config, price_data=price_data)
    _print_picks("GAP FILL", gap_fill, kind="signal")

    chart_patterns = screen_chart_patterns(config, price_data=price_data)
    _print_picks("CHART PATTERNS", chart_patterns, kind="signal")

    candles = screen_candlesticks(config, price_data=price_data)
    _print_picks("CANDLESTICKS", candles, kind="signal")

    nwe = screen_nw_envelope(config, price_data=price_data)
    _print_picks("NW ENVELOPE", nwe, kind="signal")

    pf = screen_pattern_forecast(config, price_data=price_data)
    _print_picks("PATTERN FORECAST", pf, kind="pick")

    print("\n" + "=" * 72)
    print(f"TOTAL: swing={len(swing)} momentum={len(momentum)} "
          f"nss={len(nss)} supertrend_rsi={len(strsi)} trama={len(trama)} "
          f"gap_fill={len(gap_fill)} chart_patterns={len(chart_patterns)} "
          f"candlesticks={len(candles)} "
          f"nw_envelope={len(nwe)} pattern_forecast={len(pf)}")
    print("=" * 72)


if __name__ == "__main__":
    main()
