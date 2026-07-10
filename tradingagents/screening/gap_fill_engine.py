"""Gap Fill signal engine.

Price gaps (open away from prior close) often partially or fully fill back
toward the prior session's close. Detect fresh gaps and in-progress fills.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import pandas as pd

STRATEGY_ID = "gap_fill"
STRATEGY_NAME = "Gap Fill"
STRATEGY_VERSION = "1.0"


@dataclass
class GapFillSignal:
    symbol: str
    direction: str  # BUY | SELL | NONE
    gap_age: int = -1  # 0=today … max_age-1; -1 if none
    gap_pct: float = 0.0
    gap_low: float = 0.0
    gap_high: float = 0.0
    fill_target: float = 0.0
    fill_pct: float = 0.0
    close: float = 0.0
    score: float = 0.0
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
            "gap_age": self.gap_age,
            "gap_pct": self.gap_pct,
            "gap_low": self.gap_low,
            "gap_high": self.gap_high,
            "fill_target": self.fill_target,
            "fill_pct": self.fill_pct,
            "close": self.close,
            "score": self.score,
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


def _gap_at_bar(
    df: pd.DataFrame,
    i: int,
    gap_min_pct: float,
) -> Optional[Tuple[str, float, float, float, float]]:
    """Return (direction, gap_pct, gap_low, gap_high, fill_target) for bar i, or None."""
    if i < 1:
        return None
    prev_close = float(df["Close"].iloc[i - 1])
    prev_high = float(df["High"].iloc[i - 1])
    prev_low = float(df["Low"].iloc[i - 1])
    open_i = float(df["Open"].iloc[i])
    low_i = float(df["Low"].iloc[i])
    high_i = float(df["High"].iloc[i])

    if prev_close <= 0:
        return None

    gap_pct = 100.0 * (open_i - prev_close) / prev_close
    fill_target = prev_close

    if gap_pct >= gap_min_pct and low_i > prev_high:
        return "UP", gap_pct, low_i, high_i, fill_target
    if gap_pct <= -gap_min_pct and high_i < prev_low:
        return "DOWN", gap_pct, low_i, high_i, fill_target
    return None


def _find_latest_gap(
    df: pd.DataFrame,
    gap_min_pct: float,
    max_age: int,
) -> Tuple[Optional[str], int, float, float, float, float, float]:
    """Return freshest gap within window: direction UP/DOWN, age, gap_pct, low, high, fill_target."""
    n = len(df)
    if n < 2:
        return None, -1, 0.0, 0.0, 0.0, 0.0, 0.0

    limit = min(max_age, n - 1)
    for age in range(limit):
        i = n - 1 - age
        hit = _gap_at_bar(df, i, gap_min_pct)
        if hit is None:
            continue
        gap_dir, gap_pct, gap_low, gap_high, fill_target = hit
        return gap_dir, age, gap_pct, gap_low, gap_high, fill_target, gap_pct

    return None, -1, 0.0, 0.0, 0.0, 0.0, 0.0


def _buy_fill_progress(close_now: float, gap_low: float, fill_target: float) -> Optional[float]:
    span = fill_target - gap_low
    if span <= 0:
        return None
    return 100.0 * (close_now - gap_low) / span


def _sell_fill_progress(close_now: float, gap_high: float, fill_target: float) -> Optional[float]:
    span = gap_high - fill_target
    if span <= 0:
        return None
    return 100.0 * (gap_high - close_now) / span


def _signal_score(gap_age: int, gap_pct: float, fill_pct: float) -> float:
    return -gap_age * 10.0 + abs(gap_pct) + fill_pct * 0.1


def evaluate_gap_fill(
    df: pd.DataFrame,
    config: Optional[dict] = None,
    symbol: str = "",
) -> GapFillSignal:
    """Evaluate one ticker for an in-progress gap fill setup."""
    config = config or {}
    gap_min_pct = float(config.get("gap_fill_min_pct", 0.75))
    max_age = int(config.get("gap_fill_max_age", 3))
    min_progress = float(config.get("gap_fill_min_progress", 10))
    max_progress = float(config.get("gap_fill_max_progress", 85))
    min_bars = int(config.get("gap_fill_min_bars", 30))
    directions = str(config.get("gap_fill_directions", "BUY")).upper()
    allow_buy = "BUY" in directions
    allow_sell = "SELL" in directions

    empty = GapFillSignal(symbol=symbol, direction="NONE", rejected=True)

    if df is None or len(df) < min_bars:
        empty.reject_reason = f"Insufficient history (need ≥{min_bars} bars)"
        empty.remark = f"REJECT - {empty.reject_reason}"
        return empty
    if not {"Open", "High", "Low", "Close"}.issubset(df.columns):
        empty.reject_reason = "Missing Open/High/Low/Close columns"
        empty.remark = f"REJECT - {empty.reject_reason}"
        return empty

    close_now = float(df["Close"].iloc[-1])
    empty.close = round(close_now, 2)

    gap_dir, age, gap_pct, gap_low, gap_high, fill_target, _ = _find_latest_gap(
        df, gap_min_pct, max_age
    )
    if gap_dir is None:
        empty.reject_reason = f"No qualifying gap in last {max_age} trading days"
        empty.remark = f"REJECT - {empty.reject_reason}"
        return empty

    direction: Optional[str] = None
    fill_pct: Optional[float] = None

    if gap_dir == "DOWN" and allow_buy:
        if close_now >= fill_target:
            empty.gap_age = age
            empty.gap_pct = round(gap_pct, 2)
            empty.fill_target = round(fill_target, 2)
            empty.reject_reason = "Gap down already filled (close at/above prior close)"
            empty.remark = f"REJECT - {empty.reject_reason}"
            return empty
        fill_pct = _buy_fill_progress(close_now, gap_low, fill_target)
        direction = "BUY"
    elif gap_dir == "UP" and allow_sell:
        if close_now <= fill_target:
            empty.gap_age = age
            empty.gap_pct = round(gap_pct, 2)
            empty.fill_target = round(fill_target, 2)
            empty.reject_reason = "Gap up already filled (close at/below prior close)"
            empty.remark = f"REJECT - {empty.reject_reason}"
            return empty
        fill_pct = _sell_fill_progress(close_now, gap_high, fill_target)
        direction = "SELL"
    else:
        empty.reject_reason = f"Gap {gap_dir} not enabled in gap_fill_directions"
        empty.remark = f"REJECT - {empty.reject_reason}"
        return empty

    if fill_pct is None:
        empty.reject_reason = "Invalid fill geometry"
        empty.remark = f"REJECT - {empty.reject_reason}"
        return empty

    if fill_pct < min_progress or fill_pct > max_progress:
        empty.gap_age = age
        empty.gap_pct = round(gap_pct, 2)
        empty.gap_low = round(gap_low, 2)
        empty.gap_high = round(gap_high, 2)
        empty.fill_target = round(fill_target, 2)
        empty.fill_pct = round(fill_pct, 2)
        empty.reject_reason = (
            f"Fill progress {fill_pct:.1f}% outside {min_progress:.0f}–{max_progress:.0f}% band"
        )
        empty.remark = f"REJECT - {empty.reject_reason}"
        return empty

    score = _signal_score(age, gap_pct, fill_pct)
    age_txt = _age_label(age)
    if direction == "BUY":
        remark = (
            f"BUY - gap down {age_txt} ({gap_pct:+.2f}%) - "
            f"fill {fill_pct:.0f}% toward {fill_target:.2f}"
        )
    else:
        remark = (
            f"SELL - gap up {age_txt} ({gap_pct:+.2f}%) - "
            f"pullback {fill_pct:.0f}% toward {fill_target:.2f}"
        )

    reasons = [
        f"Gap {gap_dir} {_age_label(age)}: open vs prior close {gap_pct:+.2f}% (min {gap_min_pct}%)",
        f"True gap separation confirmed on gap day",
        f"Fill target = prior close {fill_target:.2f}",
        f"Fill progress {fill_pct:.1f}% (band {min_progress:.0f}–{max_progress:.0f}%)",
        f"Latest close {close_now:.2f}",
    ]

    return GapFillSignal(
        symbol=symbol,
        direction=direction,
        gap_age=age,
        gap_pct=round(gap_pct, 2),
        gap_low=round(gap_low, 2),
        gap_high=round(gap_high, 2),
        fill_target=round(fill_target, 2),
        fill_pct=round(fill_pct, 2),
        close=round(close_now, 2),
        score=round(score, 2),
        remark=remark,
        rejected=False,
        reasons=reasons,
    )


def explain_gap_fill(ticker: str, config: dict) -> GapFillSignal:
    """Download one ticker and return a gap fill signal with remarks."""
    from tradingagents.screening.prices import download_history

    symbol = ticker.upper()
    if not symbol.endswith((".NS", ".BO")):
        symbol = f"{symbol}.NS"
    period = config.get("gap_fill_history_period", "1y")
    data = download_history([symbol], period=period)
    df = data.get(symbol)
    if df is None or df.empty:
        return GapFillSignal(
            symbol=symbol,
            direction="NONE",
            rejected=True,
            reject_reason="No price history from Yahoo",
            remark="REJECT - no price history from Yahoo",
        )
    return evaluate_gap_fill(df, config, symbol=symbol)
