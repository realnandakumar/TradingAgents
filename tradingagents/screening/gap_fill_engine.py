"""Gap screener engine — detect active true gaps on daily charts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import pandas as pd

from tradingagents.screening.patterns import rsi

STRATEGY_ID = "gap_fill"
STRATEGY_NAME = "Gap Screener"
STRATEGY_VERSION = "2.0"


@dataclass
class GapFillSignal:
    symbol: str
    direction: str  # DOWN | UP | NONE
    gap_age: int = -1
    gap_pct: float = 0.0
    gap_low: float = 0.0
    gap_high: float = 0.0
    fill_target: float = 0.0
    fill_pct: float = 0.0
    close: float = 0.0
    rsi: float = 0.0
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
            "rsi": self.rsi,
            "score": self.score,
            "remark": self.remark,
            "rejected": self.rejected,
            "reject_reason": self.reject_reason,
            "stock_name": self.stock_name,
            "sector": self.sector,
            "reasons": self.reasons,
        }


def _completed_df(df: pd.DataFrame, exclude_today: bool) -> pd.DataFrame:
    if exclude_today and len(df) > 1:
        return df.iloc[:-1].copy()
    return df


def _age_label(age: int, *, exclude_today: bool = False) -> str:
    if age == 0:
        return "latest session" if exclude_today else "today"
    if age == 1:
        return "1 day ago"
    return f"{age} days ago"


def _gap_at_bar(
    df: pd.DataFrame,
    i: int,
    gap_min_pct: float,
) -> Optional[Tuple[str, float, float, float, float]]:
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


def _signal_score(gap_age: int, gap_pct: float) -> float:
    return -gap_age * 10.0 + abs(gap_pct)


def _latest_rsi(close: pd.Series, period: int) -> Optional[float]:
    series = rsi(close, period)
    if series.empty:
        return None
    val = float(series.iloc[-1])
    if pd.isna(val):
        return None
    return val


def _direction_allowed(gap_dir: str, directions: str) -> bool:
    allowed = {d.strip().upper() for d in directions.split(",") if d.strip()}
    if gap_dir == "DOWN":
        return "DOWN" in allowed or "BUY" in allowed
    return "UP" in allowed or "SELL" in allowed


def gap_trade_side(direction: str) -> Optional[str]:
    """Map gap direction (DOWN/UP) to paper trade side (BUY/SELL)."""
    d = (direction or "").upper()
    if d in ("DOWN", "BUY"):
        return "BUY"
    if d in ("UP", "SELL"):
        return "SELL"
    return None


def is_long_gap_candidate(direction: str) -> bool:
    return gap_trade_side(direction) == "BUY"


def pick_passes_long_entry(signal: GapFillSignal, config: Optional[dict] = None) -> tuple[bool, str]:
    """Re-check screener entry rules before opening a long paper position."""
    config = config or {}
    if signal.rejected or signal.direction in ("NONE", ""):
        return False, signal.reject_reason or "screener rejected"
    if not is_long_gap_candidate(signal.direction):
        return False, f"{signal.direction} is not a long (BUY) gap setup"
    directions = str(config.get("gap_fill_directions", "UP,DOWN"))
    if not _direction_allowed(signal.direction, directions):
        return False, f"gap direction {signal.direction} disabled in config"
    gap_min_pct = float(config.get("gap_fill_min_pct", 5.0))
    max_age = int(config.get("gap_fill_max_age", 30))
    min_progress = float(config.get("gap_fill_min_progress", 10))
    max_progress = float(config.get("gap_fill_max_progress", 50))
    if abs(signal.gap_pct) < gap_min_pct:
        return False, f"gap {signal.gap_pct:+.2f}% below min {gap_min_pct}%"
    if signal.gap_age < 0 or signal.gap_age > max_age:
        return False, f"gap age {signal.gap_age} outside 0–{max_age} days"
    if signal.fill_pct < min_progress:
        return False, (
            f"fill {signal.fill_pct:.0f}% below min {min_progress:.0f}% (too early)"
        )
    if signal.fill_pct > max_progress:
        return False, (
            f"fill {signal.fill_pct:.0f}% above max {max_progress:.0f}% (too late)"
        )
    if signal.direction == "DOWN" and signal.close >= signal.fill_target:
        return False, "gap down already filled to prior close"
    return True, ""


def evaluate_gap_fill(
    df: pd.DataFrame,
    config: Optional[dict] = None,
    symbol: str = "",
) -> GapFillSignal:
    """Return the freshest active true gap for one ticker (screener only)."""
    config = config or {}
    gap_min_pct = float(config.get("gap_fill_min_pct", 5.0))
    max_age = int(config.get("gap_fill_max_age", 30))
    exclude_today = bool(config.get("gap_fill_exclude_today", True))
    rsi_period = int(config.get("gap_fill_rsi_period", 14))
    min_bars = int(config.get("gap_fill_min_bars", 30))
    directions = str(config.get("gap_fill_directions", "UP,DOWN"))

    empty = GapFillSignal(symbol=symbol, direction="NONE", rejected=True)

    if df is None or len(df) < min_bars:
        empty.reject_reason = f"Insufficient history (need >={min_bars} bars)"
        empty.remark = f"REJECT - {empty.reject_reason}"
        return empty
    if not {"Open", "High", "Low", "Close"}.issubset(df.columns):
        empty.reject_reason = "Missing Open/High/Low/Close columns"
        empty.remark = f"REJECT - {empty.reject_reason}"
        return empty

    work = _completed_df(df, exclude_today)
    if len(work) < min_bars:
        empty.reject_reason = f"Insufficient completed history (need >={min_bars} bars)"
        empty.remark = f"REJECT - {empty.reject_reason}"
        return empty

    price_now = float(df["Close"].iloc[-1])
    gap_dir, age, gap_pct, gap_low, gap_high, fill_target, _ = _find_latest_gap(
        work, gap_min_pct, max_age
    )
    if gap_dir is None:
        empty.reject_reason = f"No qualifying gap in last {max_age} trading days"
        empty.remark = f"REJECT - {empty.reject_reason}"
        return empty

    if not _direction_allowed(gap_dir, directions):
        empty.reject_reason = f"Gap {gap_dir} not enabled in gap_fill_directions"
        empty.remark = f"REJECT - {empty.reject_reason}"
        return empty

    direction = gap_dir
    if gap_dir == "DOWN":
        fill_pct = _buy_fill_progress(price_now, gap_low, fill_target)
    else:
        fill_pct = _sell_fill_progress(price_now, gap_high, fill_target)

    if fill_pct is None:
        empty.reject_reason = "Invalid fill geometry"
        empty.remark = f"REJECT - {empty.reject_reason}"
        return empty

    min_progress = float(config.get("gap_fill_min_progress", 10))
    max_progress = float(config.get("gap_fill_max_progress", 50))
    if fill_pct < min_progress:
        empty.reject_reason = (
            f"Gap only {fill_pct:.0f}% toward fill (min {min_progress:.0f}% for setup)"
        )
        empty.remark = f"REJECT - {empty.reject_reason}"
        return empty
    if fill_pct > max_progress:
        empty.reject_reason = (
            f"Gap already {fill_pct:.0f}% closed (max {max_progress:.0f}% — too late to enter)"
        )
        empty.remark = f"REJECT - {empty.reject_reason}"
        return empty

    rsi_now = _latest_rsi(work["Close"], rsi_period)
    age_txt = _age_label(age, exclude_today=exclude_today)
    fill_txt = "filled" if (
        (gap_dir == "DOWN" and price_now >= fill_target)
        or (gap_dir == "UP" and price_now <= fill_target)
    ) else f"{fill_pct:.0f}% toward {fill_target:.2f}"

    remark = f"GAP {gap_dir} {age_txt} ({gap_pct:+.2f}%) - {fill_txt}"

    reasons = [
        f"Active gap {gap_dir} {_age_label(age, exclude_today=exclude_today)}: "
        f"open vs prior close {gap_pct:+.2f}% (min {gap_min_pct}%)",
        "True gap separation confirmed on gap day",
        f"Fill target = prior close {fill_target:.2f}",
        f"Fill progress {fill_pct:.1f}% at price {price_now:.2f}",
    ]
    if rsi_now is not None:
        reasons.append(f"RSI({rsi_period}) = {rsi_now:.1f} (info only)")
    if exclude_today:
        reasons.append("Gap detected on completed sessions; today's bar excluded")

    return GapFillSignal(
        symbol=symbol,
        direction=direction,
        gap_age=age,
        gap_pct=round(gap_pct, 2),
        gap_low=round(gap_low, 2),
        gap_high=round(gap_high, 2),
        fill_target=round(fill_target, 2),
        fill_pct=round(fill_pct, 2),
        close=round(price_now, 2),
        rsi=round(rsi_now or 0.0, 2),
        score=round(_signal_score(age, gap_pct), 2),
        remark=remark,
        rejected=False,
        reasons=reasons,
    )


def explain_gap_fill(ticker: str, config: dict) -> GapFillSignal:
    """Download one ticker and return gap screener details."""
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
