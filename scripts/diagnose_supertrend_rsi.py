"""Diagnose why SuperTrend+RSI produced zero signals."""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.screening.patterns import rsi
from tradingagents.screening.prices import download_history
from tradingagents.screening.supertrend_rsi_engine import (
    _apply_filters,
    _check_mandatory_buy,
    _check_mandatory_sell,
    evaluate_supertrend_rsi,
)
from tradingagents.screening.swing_indicators import supertrend
from tradingagents.screening.universe import load_universe


def main() -> None:
    config = DEFAULT_CONFIG.copy()
    universe = load_universe(
        csv_path=config.get("screen_universe_csv"),
        cache_dir=config.get("data_cache_dir"),
    )
    data = download_history(universe, period=config.get("strsi_history_period", "1y"))

    no_data = short = 0
    no_buy: Counter = Counter()
    no_sell: Counter = Counter()
    buy_mandatory = sell_mandatory = both_mandatory = 0
    filtered_buy = filtered_sell = 0
    passed_buy: list = []
    passed_sell: list = []
    recent_buy_flip = recent_sell_flip = 0
    min_score = int(config.get("strsi_min_score", 60))

    for sym in universe:
        df = data.get(sym)
        if df is None:
            no_data += 1
            continue
        if len(df) < int(config.get("strsi_min_bars", 60)):
            short += 1
            continue

        close = df["Close"]
        st_line, trend = supertrend(
            df,
            period=int(config.get("strsi_supertrend_period", 10)),
            multiplier=float(config.get("strsi_supertrend_multiplier", 3.0)),
        )
        rsi_s = rsi(close, int(config.get("strsi_rsi_period", 14)))

        b_ok, b_reason, _ = _check_mandatory_buy(close, st_line, trend, rsi_s, config)
        s_ok, s_reason, _ = _check_mandatory_sell(close, st_line, trend, rsi_s, config)

        if not b_ok:
            no_buy[b_reason[:55]] += 1
        if not s_ok:
            no_sell[s_reason[:55]] += 1
        if b_ok:
            buy_mandatory += 1
        if s_ok:
            sell_mandatory += 1
        if b_ok and s_ok:
            both_mandatory += 1

        for i in range(-5, 0):
            if int(trend.iloc[i - 1]) == -1 and int(trend.iloc[i]) == 1:
                recent_buy_flip += 1
                break
        for i in range(-5, 0):
            if int(trend.iloc[i - 1]) == 1 and int(trend.iloc[i]) == -1:
                recent_sell_flip += 1
                break

        sig = evaluate_supertrend_rsi(df, config, symbol=sym)
        if sig.mandatory_pass and not sig.rejected:
            if sig.direction == "BUY":
                passed_buy.append((sym, sig.score))
            elif sig.direction == "SELL":
                passed_sell.append((sym, sig.score))
        elif sig.mandatory_pass and sig.rejected:
            if sig.direction == "BUY":
                filtered_buy += 1
            else:
                filtered_sell += 1

    print("=== FUNNEL ===")
    print(f"Universe:           {len(universe)}")
    print(f"No data:            {no_data}")
    print(f"Short history:      {short}")
    print(f"ST buy flip (5d):   {recent_buy_flip}  (raw flips, no confirm required)")
    print(f"ST sell flip (5d):  {recent_sell_flip}")
    print(f"Mandatory BUY pass: {buy_mandatory}")
    print(f"Mandatory SELL pass:{sell_mandatory}")
    print(f"Both pass:          {both_mandatory}")
    print(f"Filtered BUY:       {filtered_buy}")
    print(f"Filtered SELL:      {filtered_sell}")
    print(f"Clean BUY signals:  {len(passed_buy)}")
    print(f"Clean SELL signals: {len(passed_sell)}")
    print(f"Min score gate:     {min_score}")

    print("\n=== TOP BUY FAIL REASONS ===")
    for reason, count in no_buy.most_common(12):
        print(f"  {count:4d}  {reason}")

    print("\n=== TOP SELL FAIL REASONS ===")
    for reason, count in no_sell.most_common(12):
        print(f"  {count:4d}  {reason}")

    near = []
    for sym in universe:
        df = data.get(sym)
        if df is None:
            continue
        sig = evaluate_supertrend_rsi(df, config, symbol=sym)
        if sig.mandatory_pass or sig.rejected:
            near.append(sig)
    near.sort(key=lambda s: s.score, reverse=True)

    print("\n=== HIGHEST SCORES (any state) top 15 ===")
    for sig in near[:15]:
        sym = sig.symbol.replace(".NS", "")
        state = "FILTERED" if sig.rejected else ("PASS" if sig.mandatory_pass else "NO-SIG")
        print(
            f"  {sym:<14} {sig.direction:<4} score={sig.score:3d} "
            f"raw={sig.components.raw_total:5.1f}  {state}"
            + (f"  {sig.reject_reason[:40]}" if sig.rejected else "")
        )

    # Filter-only breakdown for mandatory pass
    filter_reasons: Counter = Counter()
    for sym in universe:
        df = data.get(sym)
        if df is None:
            continue
        close = df["Close"]
        st_line, trend = supertrend(df, period=10, multiplier=3.0)
        rsi_s = rsi(close, 14)
        b_ok, _, bf = _check_mandatory_buy(close, st_line, trend, rsi_s, config)
        s_ok, _, sf = _check_mandatory_sell(close, st_line, trend, rsi_s, config)
        direction = None
        if b_ok and not s_ok:
            direction = "BUY"
        elif s_ok and not b_ok:
            direction = "SELL"
        elif b_ok and s_ok:
            direction = "BUY" if (len(df) - 1 - (bf or 99)) <= (len(df) - 1 - (sf or 99)) else "SELL"
        if direction:
            rej, reason = _apply_filters(df, direction, trend, st_line, config)
            if rej:
                filter_reasons[reason] += 1

    if filter_reasons:
        print("\n=== FILTER REJECTIONS (mandatory pass only) ===")
        for reason, count in filter_reasons.most_common():
            print(f"  {count:4d}  {reason}")

    clean = []
    for sym in universe:
        df = data.get(sym)
        if df is None:
            continue
        sig = evaluate_supertrend_rsi(df, config, symbol=sym)
        if sig.mandatory_pass and not sig.rejected:
            clean.append(sig)
    clean.sort(key=lambda s: s.score, reverse=True)

    print(f"\n=== ALL CLEAN SIGNALS ({len(clean)}) ===")
    for sig in clean:
        sym = sig.symbol.replace(".NS", "")
        print(f"  {sym:<14} {sig.direction:<4} score={sig.score:3d} raw={sig.components.raw_total:5.1f}")
    print(f"Above min_score {min_score}: {sum(1 for s in clean if s.score >= min_score)}")


if __name__ == "__main__":
    main()
