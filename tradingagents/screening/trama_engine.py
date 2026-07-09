"""TRAMA close-crossover signal engine.

Simple rule (per plan):
- Compute LuxAlgo TRAMA (length 100, src=close).
- Detect BUY when close crosses *above* TRAMA.
- Detect SELL when close crosses *below* TRAMA.
- Keep only crosses within the last N trading days (default 3).
- Age 1–2: latest close must still be on the signal side of TRAMA.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import pandas as pd

from tradingagents.screening.trama_indicator import trama_from_ohlc

STRATEGY_ID = "trama"
STRATEGY_NAME = "TRAMA Crossover"
STRATEGY_VERSION = "1.0"


@dataclass
class TramaSignal:
    symbol: str
    direction: str  # BUY | SELL | NONE
    cross_age: int = -1  # 0=today … max_age-1; -1 if none
    close: float = 0.0
    trama: float = 0.0
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
            "trama": self.trama,
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
    trama: pd.Series,
    max_age: int,
) -> Tuple[Optional[str], int]:
    """Return (direction, age) for the most recent close/TRAMA cross in window.

    BUY:  prior close <= prior TRAMA AND today close > today TRAMA
    SELL: prior close >= prior TRAMA AND today close < today TRAMA
    Age 0 = latest bar. Scans age 0 … max_age-1 and returns the freshest hit.
    """
    n = len(close)
    if n < 2:
        return None, -1

    # Need max_age bars plus one prior bar for the crossover check.
    limit = min(max_age, n - 1)
    for age in range(limit):
        # Index of the candidate crossover bar (age 0 = last bar)
        i = n - 1 - age
        prev = i - 1
        if prev < 0:
            break
        c0, c1 = float(close.iloc[prev]), float(close.iloc[i])
        t0, t1 = float(trama.iloc[prev]), float(trama.iloc[i])
        if not (pd.notna(c0) and pd.notna(c1) and pd.notna(t0) and pd.notna(t1)):
            continue

        if c0 <= t0 and c1 > t1:
            return "BUY", age
        if c0 >= t0 and c1 < t1:
            return "SELL", age

    return None, -1


def evaluate_trama(
    df: pd.DataFrame,
    config: Optional[dict] = None,
    symbol: str = "",
) -> TramaSignal:
    """Evaluate one ticker for a fresh TRAMA close crossover."""
    config = config or {}
    length = int(config.get("trama_length", 100))
    max_age = int(config.get("trama_cross_max_age", 3))
    min_bars = int(config.get("trama_min_bars", length + 5))
    require_hold = bool(config.get("trama_require_still_on_side", True))

    empty = TramaSignal(symbol=symbol, direction="NONE", rejected=True)

    if df is None or len(df) < min_bars:
        empty.reject_reason = f"Insufficient history (need ≥{min_bars} bars)"
        empty.remark = f"REJECT - {empty.reject_reason}"
        return empty
    if not {"High", "Low", "Close"}.issubset(df.columns):
        empty.reject_reason = "Missing High/Low/Close columns"
        empty.remark = f"REJECT - {empty.reject_reason}"
        return empty

    trama = trama_from_ohlc(df, length=length, src_col="Close")
    close = df["Close"].astype(float)

    last_close = float(close.iloc[-1])
    last_trama = float(trama.iloc[-1])
    if not (pd.notna(last_close) and pd.notna(last_trama)):
        empty.reject_reason = "TRAMA or close is NaN on latest bar"
        empty.remark = f"REJECT - {empty.reject_reason}"
        return empty

    dist_pct = 100.0 * (last_close - last_trama) / last_trama if last_trama else 0.0

    direction, age = _find_latest_crossover(close, trama, max_age=max_age)
    if direction is None:
        side = "above" if last_close > last_trama else ("below" if last_close < last_trama else "at")
        empty.close = round(last_close, 2)
        empty.trama = round(last_trama, 2)
        empty.dist_pct = round(dist_pct, 2)
        empty.reject_reason = f"No TRAMA close crossover in last {max_age} trading days"
        empty.remark = (
            f"REJECT - no TRAMA crossover in last {max_age} trading days "
            f"- close is {side} TRAMA"
        )
        return empty

    # Age 1-2: still on signal side of TRAMA (avoids stale flips that reversed).
    if require_hold and age > 0:
        if direction == "BUY" and last_close <= last_trama:
            empty.close = round(last_close, 2)
            empty.trama = round(last_trama, 2)
            empty.dist_pct = round(dist_pct, 2)
            empty.cross_age = age
            empty.reject_reason = (
                f"BUY crossover {_age_label(age)} but latest close is back at/below TRAMA"
            )
            empty.remark = f"REJECT - {empty.reject_reason}"
            return empty
        if direction == "SELL" and last_close >= last_trama:
            empty.close = round(last_close, 2)
            empty.trama = round(last_trama, 2)
            empty.dist_pct = round(dist_pct, 2)
            empty.cross_age = age
            empty.reject_reason = (
                f"SELL crossover {_age_label(age)} but latest close is back at/above TRAMA"
            )
            empty.remark = f"REJECT - {empty.reject_reason}"
            return empty

    side_word = "above" if direction == "BUY" else "below"
    verb = "crossed above" if direction == "BUY" else "crossed below"
    age_txt = _age_label(age)
    remark = f"{direction} - crossover {age_txt} - close {verb} TRAMA"
    if age > 0:
        remark += f" - close still {side_word} TRAMA"

    reasons = [
        f"TRAMA({length}) LuxAlgo formula, source=close",
        f"Close {verb} TRAMA {_age_label(age)}",
        f"Latest close {last_close:.2f} · TRAMA {last_trama:.2f} · dist {dist_pct:+.2f}%",
        f"Freshness gate: cross age {age} < {max_age} trading days",
    ]
    if require_hold and age > 0:
        reasons.append(f"Hold check: close still {side_word} TRAMA after crossover")

    return TramaSignal(
        symbol=symbol,
        direction=direction,
        cross_age=age,
        close=round(last_close, 2),
        trama=round(last_trama, 2),
        dist_pct=round(dist_pct, 2),
        remark=remark,
        rejected=False,
        reasons=reasons,
    )


def explain_trama(ticker: str, config: dict) -> TramaSignal:
    """Download one ticker and return a TRAMA signal with remarks."""
    from tradingagents.screening.prices import download_history

    symbol = ticker.upper()
    if not symbol.endswith((".NS", ".BO")):
        symbol = f"{symbol}.NS"
    period = config.get("trama_history_period", "1y")
    data = download_history([symbol], period=period)
    df = data.get(symbol)
    if df is None or df.empty:
        return TramaSignal(
            symbol=symbol,
            direction="NONE",
            rejected=True,
            reject_reason="No price history from Yahoo",
            remark="REJECT - no price history from Yahoo",
        )
    return evaluate_trama(df, config, symbol=symbol)
