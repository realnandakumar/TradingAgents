"""Nadaraya-Watson Envelope contrarian crossover signal engine.

Signals (LuxAlgo triangles, contrarian):
- BUY: close crosses below lower envelope (oversold, expect bounce)
- SELL: close crosses above upper envelope (overbought, expect pullback)

Cross detection:
- BUY: prev close >= prev lower AND curr close < curr lower
- SELL: prev close <= prev upper AND curr close > curr upper

Freshness: cross within last N days; age 1–2 must still be on signal side.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import pandas as pd

from tradingagents.screening.nw_envelope_indicator import nw_envelope_from_ohlc

STRATEGY_ID = "nw_envelope"
STRATEGY_NAME = "Nadaraya-Watson Envelope [LuxAlgo]"
STRATEGY_VERSION = "1.0"


@dataclass
class NwEnvelopeSignal:
    symbol: str
    direction: str  # BUY | SELL | NONE
    cross_age: int = -1
    close: float = 0.0
    middle: float = 0.0
    upper: float = 0.0
    lower: float = 0.0
    dist_pct: float = 0.0
    remark: str = ""
    rejected: bool = False
    reject_reason: str = ""
    stock_name: str = ""
    sector: str = ""
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "strategy_id": STRATEGY_ID,
            "strategy_name": STRATEGY_NAME,
            "version": STRATEGY_VERSION,
            "symbol": self.symbol,
            "direction": self.direction,
            "cross_age": self.cross_age,
            "close": self.close,
            "middle": self.middle,
            "upper": self.upper,
            "lower": self.lower,
            "dist_pct": self.dist_pct,
            "remark": self.remark,
            "rejected": self.rejected,
            "reject_reason": self.reject_reason,
            "stock_name": self.stock_name,
            "sector": self.sector,
            "reasons": self.reasons,
        }


def _age_label(age: int) -> str:
    if age == 0:
        return "today"
    if age == 1:
        return "1 day ago"
    return f"{age} days ago"


def _find_latest_crossover(
    close: pd.Series,
    upper: pd.Series,
    lower: pd.Series,
    max_age: int,
) -> Tuple[Optional[str], int]:
    """Return (direction, age) for the most recent envelope cross in window."""
    n = len(close)
    if n < 2:
        return None, -1

    limit = min(max_age, n - 1)
    for age in range(limit):
        i = n - 1 - age
        prev = i - 1
        if prev < 0:
            break
        c0, c1 = float(close.iloc[prev]), float(close.iloc[i])
        u0, u1 = float(upper.iloc[prev]), float(upper.iloc[i])
        l0, l1 = float(lower.iloc[prev]), float(lower.iloc[i])
        if not all(pd.notna(x) for x in (c0, c1, u0, u1, l0, l1)):
            continue

        if c0 >= l0 and c1 < l1:
            return "BUY", age
        if c0 <= u0 and c1 > u1:
            return "SELL", age

    return None, -1


def _band_dist_pct(direction: str, close: float, upper: float, lower: float) -> float:
    if direction == "BUY" and lower:
        return 100.0 * (close - lower) / lower
    if direction == "SELL" and upper:
        return 100.0 * (close - upper) / upper
    if lower:
        return 100.0 * (close - lower) / lower
    return 0.0


def evaluate_nw_envelope(
    df: pd.DataFrame,
    config: Optional[dict] = None,
    symbol: str = "",
) -> NwEnvelopeSignal:
    """Evaluate one ticker for a fresh NWE contrarian crossover."""
    config = config or {}
    bandwidth = float(config.get("nwe_bandwidth", 8.0))
    mult = float(config.get("nwe_mult", 3.0))
    lookback = int(config.get("nwe_lookback", 500))
    max_age = int(config.get("nwe_cross_max_age", 3))
    min_bars = int(config.get("nwe_min_bars", 60))
    require_hold = bool(config.get("nwe_require_still_on_side", True))

    empty = NwEnvelopeSignal(symbol=symbol, direction="NONE", rejected=True)

    if df is None or len(df) < min_bars:
        empty.reject_reason = f"Insufficient history (need ≥{min_bars} bars)"
        empty.remark = f"REJECT - {empty.reject_reason}"
        return empty
    if "Close" not in df.columns:
        empty.reject_reason = "Missing Close column"
        empty.remark = f"REJECT - {empty.reject_reason}"
        return empty

    bands = nw_envelope_from_ohlc(
        df, bandwidth=bandwidth, mult=mult, lookback=lookback, src_col="Close"
    )
    close = df["Close"].astype(float)
    upper = bands["nwe_upper"]
    lower = bands["nwe_lower"]
    middle = bands["nwe_middle"]

    last_close = float(close.iloc[-1])
    last_upper = float(upper.iloc[-1])
    last_lower = float(lower.iloc[-1])
    last_middle = float(middle.iloc[-1])
    if not all(pd.notna(x) for x in (last_close, last_upper, last_lower, last_middle)):
        empty.reject_reason = "NWE bands or close is NaN on latest bar"
        empty.remark = f"REJECT - {empty.reject_reason}"
        return empty

    direction, age = _find_latest_crossover(close, upper, lower, max_age=max_age)
    if direction is None:
        if last_close < last_lower:
            side = "below lower"
        elif last_close > last_upper:
            side = "above upper"
        else:
            side = "inside envelope"
        empty.close = round(last_close, 2)
        empty.middle = round(last_middle, 2)
        empty.upper = round(last_upper, 2)
        empty.lower = round(last_lower, 2)
        empty.dist_pct = round(_band_dist_pct("BUY", last_close, last_upper, last_lower), 2)
        empty.reject_reason = f"No NWE crossover in last {max_age} trading days"
        empty.remark = (
            f"REJECT - no NWE crossover in last {max_age} trading days "
            f"- close is {side}"
        )
        return empty

    dist_pct = _band_dist_pct(direction, last_close, last_upper, last_lower)

    if require_hold and age > 0:
        if direction == "BUY" and last_close >= last_lower:
            empty.close = round(last_close, 2)
            empty.middle = round(last_middle, 2)
            empty.upper = round(last_upper, 2)
            empty.lower = round(last_lower, 2)
            empty.dist_pct = round(dist_pct, 2)
            empty.cross_age = age
            empty.reject_reason = (
                f"BUY crossover {_age_label(age)} but latest close is back at/above lower band"
            )
            empty.remark = f"REJECT - {empty.reject_reason}"
            return empty
        if direction == "SELL" and last_close <= last_upper:
            empty.close = round(last_close, 2)
            empty.middle = round(last_middle, 2)
            empty.upper = round(last_upper, 2)
            empty.lower = round(last_lower, 2)
            empty.dist_pct = round(dist_pct, 2)
            empty.cross_age = age
            empty.reject_reason = (
                f"SELL crossover {_age_label(age)} but latest close is back at/below upper band"
            )
            empty.remark = f"REJECT - {empty.reject_reason}"
            return empty

    if direction == "BUY":
        verb = "crossed below lower band"
        side_word = "below lower"
    else:
        verb = "crossed above upper band"
        side_word = "above upper"

    age_txt = _age_label(age)
    remark = f"{direction} - crossover {age_txt} - close {verb}"
    if age > 0:
        remark += f" - close still {side_word}"

    reasons = [
        f"NWE(bw={bandwidth}, mult={mult}, lb={min(lookback, len(df))}) LuxAlgo endpoint, source=close",
        f"Close {verb} {_age_label(age)}",
        (
            f"Latest close {last_close:.2f} · mid {last_middle:.2f} · "
            f"upper {last_upper:.2f} · lower {last_lower:.2f} · dist {dist_pct:+.2f}%"
        ),
        f"Freshness gate: cross age {age} < {max_age} trading days",
    ]
    if require_hold and age > 0:
        reasons.append(f"Hold check: close still {side_word} after crossover")

    return NwEnvelopeSignal(
        symbol=symbol,
        direction=direction,
        cross_age=age,
        close=round(last_close, 2),
        middle=round(last_middle, 2),
        upper=round(last_upper, 2),
        lower=round(last_lower, 2),
        dist_pct=round(dist_pct, 2),
        remark=remark,
        rejected=False,
        reasons=reasons,
    )


def explain_nw_envelope(ticker: str, config: dict) -> NwEnvelopeSignal:
    """Download one ticker and return an NWE signal with remarks."""
    from tradingagents.screening.prices import download_history

    symbol = ticker.upper()
    if not symbol.endswith((".NS", ".BO")):
        symbol = f"{symbol}.NS"
    period = config.get("nwe_history_period", "2y")
    data = download_history([symbol], period=period)
    df = data.get(symbol)
    if df is None or df.empty:
        return NwEnvelopeSignal(
            symbol=symbol,
            direction="NONE",
            rejected=True,
            reject_reason="No price history from Yahoo",
            remark="REJECT - no price history from Yahoo",
        )
    return evaluate_nw_envelope(df, config, symbol=symbol)
