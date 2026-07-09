"""Momentum continuation screener for Indian (NSE) equities."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

import numpy as np
import pandas as pd

from tradingagents.screening.momentum_indicators import (
    adx_rising,
    macd,
    pct_above_ema,
    supertrend_buy_age,
    volume_short_above_long,
)
from tradingagents.screening.patterns import rsi
from tradingagents.screening.prices import download_history
from tradingagents.screening.swing_indicators import (
    adx,
    compute_trade_levels,
    ema,
    is_at_new_52_week_low,
    supertrend,
    supertrend_flip_to_buy_within,
)
from tradingagents.screening.swing_screener import (
    _CRORE,
    _avg_daily_traded_value_inr,
    _fetch_market_caps,
)
from tradingagents.screening.universe import load_universe, load_universe_metadata

logger = logging.getLogger(__name__)


@dataclass
class MomentumPick:
    symbol: str
    stock_name: str
    sector: str
    entry_price: float
    stop_loss: float
    target_1: float
    target_2: float
    stop_loss_pct: float
    target_1_pct: float
    target_2_pct: float
    risk_reward_ratio: float
    risk_reward_ratio_2: float
    supertrend_status: str
    rsi: float
    adx: float
    macd: float
    macd_signal: float
    volume_ratio_5_20: float
    extension_pct: float
    adx_rising: bool
    risk_pct: float = 0.0
    market_cap_cr: Optional[float] = None
    avg_traded_value_cr: Optional[float] = None
    sort_rsi_mid: float = field(init=False)

    def __post_init__(self):
        self.sort_rsi_mid = -abs(self.rsi - 60.0)


def _min_bars_required(config: dict) -> int:
    return max(
        252,
        int(config.get("momentum_ema_slow", 200)),
        int(config.get("momentum_volume_long", 20)),
        int(config.get("momentum_hh_lookback", 20)),
    ) + 10


def _passes_technical_filters(df: pd.DataFrame, config: dict) -> Optional[dict]:
    min_bars = _min_bars_required(config)
    if len(df) < min_bars:
        return None

    st_period = int(config.get("momentum_supertrend_period", 10))
    st_mult = float(config.get("momentum_supertrend_multiplier", 3.0))
    ema_fast = int(config.get("momentum_ema_fast", 50))
    ema_slow = int(config.get("momentum_ema_slow", 200))
    rsi_period = int(config.get("momentum_rsi_period", 14))
    adx_period = int(config.get("momentum_adx_period", 14))
    rsi_min = float(config.get("momentum_rsi_min", 50.0))
    rsi_max = float(config.get("momentum_rsi_max", 65.0))
    adx_min = float(config.get("momentum_adx_min", 20.0))
    vol_short = int(config.get("momentum_volume_short", 5))
    vol_long = int(config.get("momentum_volume_long", 20))
    vol_min_ratio = float(config.get("momentum_volume_min_ratio", 1.0))
    max_ext = float(config.get("momentum_max_extension_pct", 15.0))
    macd_fast = int(config.get("momentum_macd_fast", 12))
    macd_slow = int(config.get("momentum_macd_slow", 26))
    macd_sig = int(config.get("momentum_macd_signal", 9))
    adx_rise_sessions = int(config.get("momentum_adx_rising_sessions", 3))
    st_min_buy = int(config.get("momentum_st_min_buy_sessions", 4))
    swing_flip_sessions = int(config.get("swing_flip_lookback_sessions", 3))
    exclude_swing_overlap = config.get("momentum_exclude_swing_overlap", True)

    close = df["Close"]
    volume = df["Volume"]
    latest_close = float(close.iloc[-1])

    ema50 = ema(close, ema_fast)
    ema200 = ema(close, ema_slow)
    if latest_close <= float(ema50.iloc[-1]) or float(ema50.iloc[-1]) <= float(ema200.iloc[-1]):
        return None

    extension = pct_above_ema(latest_close, float(ema50.iloc[-1]))
    if extension > max_ext:
        return None

    st_line, st_trend = supertrend(df, period=st_period, multiplier=st_mult)
    if int(st_trend.iloc[-1]) != 1:
        return None

    # Anti-overlap with swing (early ST flip): momentum = established trend only.
    if exclude_swing_overlap:
        if supertrend_flip_to_buy_within(st_trend, sessions=swing_flip_sessions):
            return None
        if supertrend_buy_age(st_trend) < st_min_buy:
            return None

    rsi_series = rsi(close, rsi_period)
    latest_rsi = float(rsi_series.iloc[-1])
    if not (rsi_min <= latest_rsi <= rsi_max):
        return None

    adx_series = adx(df, period=adx_period)
    latest_adx = float(adx_series.iloc[-1])
    if not np.isfinite(latest_adx) or latest_adx <= adx_min:
        return None

    macd_line, macd_signal, _ = macd(close, macd_fast, macd_slow, macd_sig)
    latest_macd = float(macd_line.iloc[-1])
    latest_signal = float(macd_signal.iloc[-1])
    if not (np.isfinite(latest_macd) and np.isfinite(latest_signal)):
        return None
    if latest_macd <= latest_signal:
        return None

    vol_ratio = volume_short_above_long(volume, vol_short, vol_long, min_ratio=vol_min_ratio)
    if vol_ratio is None:
        return None

    if is_at_new_52_week_low(close):
        return None

    stop = float(st_line.iloc[-1])
    if stop <= 0 or stop >= latest_close:
        return None

    levels = compute_trade_levels(
        entry=latest_close,
        stop_loss=stop,
        target_1_rr=float(config.get("momentum_target_1_rr", 1.5)),
        target_2_rr=float(config.get("momentum_target_2_rr", 2.5)),
    )
    if levels is None:
        return None

    risk = 100.0 * (latest_close - stop) / latest_close if latest_close > 0 else 0.0
    avg_traded = _avg_daily_traded_value_inr(df, vol_long)
    rising = adx_rising(adx_series, sessions=adx_rise_sessions)

    return {
        **levels,
        "supertrend_status": "Buy",
        "rsi": round(latest_rsi, 2),
        "adx": round(latest_adx, 2),
        "macd": round(latest_macd, 4),
        "macd_signal": round(latest_signal, 4),
        "volume_ratio_5_20": round(vol_ratio, 4),
        "extension_pct": round(extension, 2),
        "adx_rising": rising,
        "avg_traded_value_inr": avg_traded,
        "risk_pct": round(risk, 2),
    }


def screen_momentum(
    config: dict,
    progress: Optional[Callable[[str], None]] = None,
    price_data: Optional[Dict[str, "pd.DataFrame"]] = None,
) -> List[MomentumPick]:
    def _log(msg: str):
        logger.info(msg)
        if progress:
            progress(msg)

    universe = load_universe(
        csv_path=config.get("screen_universe_csv"),
        cache_dir=config.get("data_cache_dir"),
    )
    metadata = load_universe_metadata(
        csv_path=config.get("screen_universe_csv"),
        cache_dir=config.get("data_cache_dir"),
    )

    period = config.get("momentum_history_period", "2y")
    if price_data is None:
        _log(f"Downloading {period} history for {len(universe)} tickers...")
        price_data = download_history(universe, period=period)

    min_cap_inr = float(config.get("momentum_min_market_cap_cr", 5000.0)) * _CRORE
    min_traded_inr = float(config.get("momentum_min_avg_traded_value_cr", 10.0)) * _CRORE

    technical_hits: List[tuple[str, dict]] = []
    for sym in universe:
        df = price_data.get(sym)
        if df is None:
            continue
        snap = _passes_technical_filters(df, config)
        if snap is None:
            continue
        if snap["avg_traded_value_inr"] < min_traded_inr:
            continue
        technical_hits.append((sym, snap))

    _log(f"{len(technical_hits)} tickers pass momentum technical + traded-value filters")

    if not technical_hits:
        return []

    _log("Fetching market capitalizations...")
    caps = _fetch_market_caps([sym for sym, _ in technical_hits])

    picks: List[MomentumPick] = []
    for sym, snap in technical_hits:
        cap = caps.get(sym)
        if cap is None or cap < min_cap_inr:
            continue
        meta = metadata.get(sym, {})
        picks.append(
            MomentumPick(
                symbol=sym,
                stock_name=meta.get("name") or sym.replace(".NS", ""),
                sector=meta.get("sector") or "—",
                entry_price=snap["entry"],
                stop_loss=snap["stop_loss"],
                target_1=snap["target_1"],
                target_2=snap["target_2"],
                stop_loss_pct=snap["stop_loss_pct"],
                target_1_pct=snap["target_1_pct"],
                target_2_pct=snap["target_2_pct"],
                risk_reward_ratio=snap["risk_reward_ratio"],
                risk_reward_ratio_2=snap["risk_reward_ratio_2"],
                supertrend_status=snap["supertrend_status"],
                rsi=snap["rsi"],
                adx=snap["adx"],
                macd=snap["macd"],
                macd_signal=snap["macd_signal"],
                volume_ratio_5_20=snap["volume_ratio_5_20"],
                extension_pct=snap["extension_pct"],
                adx_rising=snap["adx_rising"],
                risk_pct=snap.get("risk_pct", 0.0),
                market_cap_cr=round(cap / _CRORE, 1),
                avg_traded_value_cr=round(snap["avg_traded_value_inr"] / _CRORE, 2),
            )
        )

    picks.sort(
        key=lambda p: (
            int(p.adx_rising),
            p.adx,
            p.volume_ratio_5_20,
            p.sort_rsi_mid,
        ),
        reverse=True,
    )
    top_n = int(config.get("momentum_top_n", 10))
    total = len(picks)
    picks = picks[:top_n]
    _log(f"{total} momentum candidate(s) after market-cap filter; showing top {len(picks)}")
    return picks
