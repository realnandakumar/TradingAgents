"""Japanese candlestick detectors for daily charts (confirm-bar required)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd

STRATEGY_ID = "candlesticks"
STRATEGY_NAME = "Candlesticks"
STRATEGY_VERSION = "1.0"

PATTERN_CATALOG: Dict[str, dict] = {
    "hammer": {"label": "Hammer", "stars": 4, "bias": "BULLISH"},
    "shooting_star": {"label": "Shooting Star", "stars": 4, "bias": "BEARISH"},
    "bullish_engulfing": {"label": "Bullish Engulfing", "stars": 5, "bias": "BULLISH"},
    "bearish_engulfing": {"label": "Bearish Engulfing", "stars": 5, "bias": "BEARISH"},
    "doji": {"label": "Doji", "stars": 3, "bias": "NEUTRAL"},
}


@dataclass
class CandleSignal:
    symbol: str
    pattern_id: str
    pattern_name: str
    bias: str
    reliability: int
    pattern_age: int
    setup_status: str
    confidence: float
    close: float
    entry_level: float
    stop_loss: float
    target_1: float
    target_2: float
    risk_reward_ratio: float
    detail: str
    pattern_window_start: str
    pattern_window_end: str
    stock_name: str = ""
    sector: str = ""
    actionability_score: float = 0.0
    distance_to_trigger_pct: float = 0.0
    levels_valid: bool = True


def _as_float(v) -> float:
    return float(v)


def _body(o: float, c: float) -> float:
    return abs(c - o)


def _range(h: float, l: float) -> float:
    return max(h - l, 1e-9)


def _is_bull(o: float, c: float) -> bool:
    return c > o


def _is_bear(o: float, c: float) -> bool:
    return c < o


def _date_str(idx) -> str:
    ts = pd.Timestamp(idx)
    return ts.strftime("%Y-%m-%d")


def _atr(df: pd.DataFrame, period: int = 14) -> float:
    if len(df) < 2:
        return _as_float(df["High"].iloc[-1] - df["Low"].iloc[-1])
    highs = df["High"].astype(float)
    lows = df["Low"].astype(float)
    closes = df["Close"].astype(float)
    prev_close = closes.shift(1)
    tr = pd.concat(
        [
            (highs - lows),
            (highs - prev_close).abs(),
            (lows - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    window = tr.tail(period)
    return float(window.mean()) if len(window) else float(tr.iloc[-1])


def _levels(
    *,
    bias: str,
    entry: float,
    stop: float,
    atr: float,
) -> tuple[float, float, float, float, bool]:
    buffer = max(atr * 0.05, abs(entry) * 0.001)
    if bias == "BULLISH":
        stop_out = min(stop, entry) - buffer
        risk = entry - stop_out
        if risk <= 0:
            return entry, stop_out, entry, entry, False
        t1 = entry + risk
        t2 = entry + 2 * risk
        return entry, stop_out, t1, t2, True
    if bias == "BEARISH":
        stop_out = max(stop, entry) + buffer
        risk = stop_out - entry
        if risk <= 0:
            return entry, stop_out, entry, entry, False
        t1 = entry - risk
        t2 = entry - 2 * risk
        return entry, stop_out, t1, t2, True
    return entry, stop, entry, entry, False


def _score(confidence: float, rr: float) -> float:
    return round(confidence * 0.7 + min(rr, 3.0) * 10, 2)


def _row(df: pd.DataFrame, i: int) -> tuple[float, float, float, float, str]:
    o = _as_float(df["Open"].iloc[i])
    h = _as_float(df["High"].iloc[i])
    l = _as_float(df["Low"].iloc[i])
    c = _as_float(df["Close"].iloc[i])
    d = _date_str(df.index[i])
    return o, h, l, c, d


def _make_signal(
    *,
    symbol: str,
    pattern_id: str,
    bias: str,
    confidence: float,
    close: float,
    entry: float,
    stop: float,
    atr: float,
    detail: str,
    window_start: str,
    window_end: str,
    age: int = 0,
) -> Optional[CandleSignal]:
    meta = PATTERN_CATALOG[pattern_id]
    entry_o, stop_o, t1, t2, ok = _levels(bias=bias, entry=entry, stop=stop, atr=atr)
    if not ok:
        return None
    rr = abs(t1 - entry_o) / abs(entry_o - stop_o) if abs(entry_o - stop_o) > 0 else 0.0
    if rr < 0.9:
        return None
    return CandleSignal(
        symbol=symbol,
        pattern_id=pattern_id,
        pattern_name=meta["label"],
        bias=bias,
        reliability=int(meta["stars"]),
        pattern_age=age,
        setup_status="CONFIRMED",
        confidence=round(confidence, 1),
        close=close,
        entry_level=round(entry_o, 4),
        stop_loss=round(stop_o, 4),
        target_1=round(t1, 4),
        target_2=round(t2, 4),
        risk_reward_ratio=round(rr, 2),
        detail=detail,
        pattern_window_start=window_start,
        pattern_window_end=window_end,
        actionability_score=_score(confidence, rr),
        distance_to_trigger_pct=0.0,
        levels_valid=True,
    )


def _detect_at(
    df: pd.DataFrame,
    pattern_i: int,
    confirm_i: int,
    symbol: str,
    enabled: set[str],
) -> List[CandleSignal]:
    """Detect patterns that complete on pattern_i and are confirmed on confirm_i."""
    if pattern_i < 1 or confirm_i <= pattern_i:
        return []
    atr = _atr(df.iloc[: confirm_i + 1])
    po, ph, pl, pc, pd_ = _row(df, pattern_i)
    _co, ch, cl, cc, cd = _row(df, confirm_i)
    prior_o, _ph, _pl, prior_c, prior_d = _row(df, pattern_i - 1)

    body = _body(po, pc)
    rng = _range(ph, pl)
    upper = ph - max(po, pc)
    lower = min(po, pc) - pl
    hits: List[CandleSignal] = []

    # Hammer: long lower wick, small upper wick, confirmed by next close above mid/high
    if "hammer" in enabled and rng > 0 and body / rng <= 0.35 and lower >= 2 * max(body, rng * 0.05) and upper <= body:
        if cc > (pl + ph) / 2 and cc > pc:
            sig = _make_signal(
                symbol=symbol,
                pattern_id="hammer",
                bias="BULLISH",
                confidence=72 if lower >= 2.5 * body else 62,
                close=cc,
                entry=cc,
                stop=pl,
                atr=atr,
                detail=f"Hammer on {pd_}; confirm close {cc:.2f} above mid",
                window_start=pd_,
                window_end=cd,
            )
            if sig:
                hits.append(sig)

    # Shooting star
    if "shooting_star" in enabled and rng > 0 and body / rng <= 0.35 and upper >= 2 * max(body, rng * 0.05) and lower <= body:
        if cc < (pl + ph) / 2 and cc < pc:
            sig = _make_signal(
                symbol=symbol,
                pattern_id="shooting_star",
                bias="BEARISH",
                confidence=72 if upper >= 2.5 * body else 62,
                close=cc,
                entry=cc,
                stop=ph,
                atr=atr,
                detail=f"Shooting star on {pd_}; confirm close {cc:.2f} below mid",
                window_start=pd_,
                window_end=cd,
            )
            if sig:
                hits.append(sig)

    # Bullish engulfing: prior bearish, pattern bullish engulfs prior body; confirm above high
    if "bullish_engulfing" in enabled and _is_bear(prior_o, prior_c) and _is_bull(po, pc):
        if pc >= prior_o and po <= prior_c and _body(po, pc) > _body(prior_o, prior_c):
            if cc > ph:
                sig = _make_signal(
                    symbol=symbol,
                    pattern_id="bullish_engulfing",
                    bias="BULLISH",
                    confidence=78,
                    close=cc,
                    entry=cc,
                    stop=min(pl, prior_c if prior_c < prior_o else prior_o),
                    atr=atr,
                    detail=f"Bullish engulfing {prior_d}/{pd_}; confirm above high",
                    window_start=prior_d,
                    window_end=cd,
                )
                if sig:
                    hits.append(sig)

    # Bearish engulfing
    if "bearish_engulfing" in enabled and _is_bull(prior_o, prior_c) and _is_bear(po, pc):
        if po >= prior_c and pc <= prior_o and _body(po, pc) > _body(prior_o, prior_c):
            if cc < pl:
                sig = _make_signal(
                    symbol=symbol,
                    pattern_id="bearish_engulfing",
                    bias="BEARISH",
                    confidence=78,
                    close=cc,
                    entry=cc,
                    stop=max(ph, prior_c if prior_c > prior_o else prior_o),
                    atr=atr,
                    detail=f"Bearish engulfing {prior_d}/{pd_}; confirm below low",
                    window_start=prior_d,
                    window_end=cd,
                )
                if sig:
                    hits.append(sig)

    # Doji + directional confirm
    if "doji" in enabled and rng > 0 and body / rng <= 0.1:
        if cc > ph:
            sig = _make_signal(
                symbol=symbol,
                pattern_id="doji",
                bias="BULLISH",
                confidence=58,
                close=cc,
                entry=cc,
                stop=pl,
                atr=atr,
                detail=f"Doji on {pd_}; bullish confirm above high",
                window_start=pd_,
                window_end=cd,
            )
            if sig:
                hits.append(sig)
        elif cc < pl:
            sig = _make_signal(
                symbol=symbol,
                pattern_id="doji",
                bias="BEARISH",
                confidence=58,
                close=cc,
                entry=cc,
                stop=ph,
                atr=atr,
                detail=f"Doji on {pd_}; bearish confirm below low",
                window_start=pd_,
                window_end=cd,
            )
            if sig:
                hits.append(sig)

    return hits


def scan_candlesticks(
    df: pd.DataFrame,
    config: Optional[dict] = None,
    symbol: str = "",
) -> List[CandleSignal]:
    """Scan for confirmed candlestick patterns on daily OHLCV.

    Requires a confirmation bar after the pattern bar (user decision).
    Only emits patterns whose confirmation is the latest bar (fresh setups).
    """
    cfg = config or {}
    if df is None or df.empty or len(df) < 4:
        return []

    work = df.copy()
    if not isinstance(work.index, pd.DatetimeIndex):
        if "Date" in work.columns:
            work = work.set_index(pd.to_datetime(work["Date"]))
        else:
            work.index = pd.to_datetime(work.index)
    work = work.sort_index()
    for col in ("Open", "High", "Low", "Close"):
        if col not in work.columns:
            return []

    enabled_raw = str(cfg.get("candle_enabled", "all")).strip().lower()
    if enabled_raw in {"", "all"}:
        enabled = set(PATTERN_CATALOG.keys())
    else:
        enabled = {p.strip() for p in enabled_raw.split(",") if p.strip() in PATTERN_CATALOG}

    min_conf = float(cfg.get("candle_min_confidence", 55))
    max_age = int(cfg.get("candle_max_age_days", 1))
    # Fresh: confirm bar is last bar; pattern bar is last-1 (age 0)
    # Optionally allow slightly older confirms within max_age
    hits: List[CandleSignal] = []
    last_i = len(work) - 1
    for age in range(0, max(0, max_age) + 1):
        confirm_i = last_i - age
        pattern_i = confirm_i - 1
        if pattern_i < 1:
            break
        for sig in _detect_at(work, pattern_i, confirm_i, symbol or "", enabled):
            sig.pattern_age = age
            if sig.confidence >= min_conf:
                hits.append(sig)

    # Prefer highest actionability per pattern_id
    best: Dict[str, CandleSignal] = {}
    for sig in hits:
        key = f"{sig.pattern_id}:{sig.bias}"
        prev = best.get(key)
        if prev is None or sig.actionability_score > prev.actionability_score:
            best[key] = sig
    return sorted(best.values(), key=lambda s: -s.actionability_score)


def explain_candlesticks(ticker: str, config: dict) -> List[CandleSignal]:
    from tradingagents.screening.prices import read_history

    period = config.get("candle_history_period", "1y")
    df = read_history(ticker, period=period, cache_dir=config.get("data_cache_dir"))
    if df is None or df.empty:
        return []
    return scan_candlesticks(df, config, symbol=ticker)


__all__ = [
    "STRATEGY_ID",
    "STRATEGY_NAME",
    "STRATEGY_VERSION",
    "PATTERN_CATALOG",
    "CandleSignal",
    "scan_candlesticks",
    "explain_candlesticks",
]
