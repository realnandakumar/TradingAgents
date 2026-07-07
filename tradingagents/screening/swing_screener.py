"""Swing trading screener for Indian (NSE) equities.

Early-entry swing filter: Supertrend (10,3) Sell→Buy within recent sessions,
RSI trend confirmation, 20/50 EMA structure, volume surge, ADX strength,
and liquidity / market-cap gates. Returns a ranked shortlist for manual review
(no automatic AI analysis).
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

import numpy as np
import pandas as pd

from tradingagents.screening.patterns import rsi
from tradingagents.screening.prices import download_history
from tradingagents.screening.swing_indicators import (
    adx,
    compute_trade_levels,
    ema,
    is_at_new_52_week_low,
    relative_volume,
    supertrend,
    supertrend_flip_to_buy_within,
    volume_spike_pct,
)
from tradingagents.screening.universe import load_universe, load_universe_metadata

logger = logging.getLogger(__name__)

# 1 crore = 10^7 INR
_CRORE = 10_000_000.0


@dataclass
class SwingPick:
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
    volume_spike_pct: float
    relative_volume: float
    risk_pct: float = 0.0
    market_cap_cr: Optional[float] = None
    avg_traded_value_cr: Optional[float] = None
    sort_rsi_band: float = field(init=False)

    def __post_init__(self):
        # Tertiary sort key: highest RSI within the 50–65 band.
        self.sort_rsi_band = min(max(self.rsi, 50.0), 65.0)


def _min_bars_required(config: dict) -> int:
    return max(
        252,
        int(config.get("swing_ema_mid", 50)),
        int(config.get("swing_volume_lookback", 20)) + 1,
    ) + 5


def _passes_technical_filters(df: pd.DataFrame, config: dict) -> Optional[dict]:
    """Return indicator snapshot when all technical rules pass, else None."""
    min_bars = _min_bars_required(config)
    if len(df) < min_bars:
        return None

    st_period = int(config.get("swing_supertrend_period", 10))
    st_mult = float(config.get("swing_supertrend_multiplier", 3.0))
    rsi_period = int(config.get("swing_rsi_period", 14))
    adx_period = int(config.get("swing_adx_period", 14))
    vol_lookback = int(config.get("swing_volume_lookback", 20))
    vol_mult = float(config.get("swing_volume_mult", 1.5))
    adx_min = float(config.get("swing_adx_min", 25.0))
    rsi_min = float(config.get("swing_rsi_min", 50.0))
    rsi_max = float(config.get("swing_rsi_max", 65.0))
    flip_sessions = int(config.get("swing_flip_lookback_sessions", 3))

    close = df["Close"]
    volume = df["Volume"]

    st_line, st_trend = supertrend(df, period=st_period, multiplier=st_mult)
    if not supertrend_flip_to_buy_within(st_trend, sessions=flip_sessions):
        return None

    rsi_series = rsi(close, rsi_period)
    latest_rsi = float(rsi_series.iloc[-1])
    if not (rsi_min <= latest_rsi <= rsi_max):
        return None

    ema20 = ema(close, 20)
    ema50 = ema(close, 50)
    latest_close = float(close.iloc[-1])
    if latest_close <= float(ema20.iloc[-1]):
        return None
    if config.get("swing_ema_mid_stack", False):
        if float(ema20.iloc[-1]) <= float(ema50.iloc[-1]):
            return None

    rel_vol = relative_volume(volume, vol_lookback)
    if rel_vol is None or rel_vol < vol_mult:
        return None

    adx_series = adx(df, period=adx_period)
    latest_adx = float(adx_series.iloc[-1])
    if not np.isfinite(latest_adx) or latest_adx <= adx_min:
        return None

    if is_at_new_52_week_low(close):
        return None

    stop = float(st_line.iloc[-1])
    risk = 100.0 * (latest_close - stop) / latest_close if latest_close > 0 else 0.0

    levels = compute_trade_levels(
        entry=latest_close,
        stop_loss=stop,
        target_1_rr=float(config.get("swing_target_1_rr", 1.5)),
        target_2_rr=float(config.get("swing_target_2_rr", 2.5)),
    )
    if levels is None:
        return None

    spike = volume_spike_pct(volume, vol_lookback) or 0.0
    avg_traded = _avg_daily_traded_value_inr(df, vol_lookback)

    return {
        **levels,
        "supertrend_status": "Buy",
        "rsi": round(latest_rsi, 2),
        "adx": round(latest_adx, 2),
        "volume_spike_pct": spike,
        "relative_volume": round(rel_vol, 4),
        "avg_traded_value_inr": avg_traded,
        "risk_pct": round(risk, 2),
    }


def _avg_daily_traded_value_inr(df: pd.DataFrame, lookback: int = 20) -> float:
    traded = df["Close"] * df["Volume"]
    window = traded.iloc[-lookback:]
    return float(window.mean())


def _fetch_market_cap(symbol: str) -> Optional[float]:
    try:
        import yfinance as yf

        ticker = yf.Ticker(symbol)
        cap = getattr(ticker, "fast_info", {}).get("market_cap")
        if cap is None:
            cap = ticker.info.get("marketCap")
        if cap is None:
            return None
        return float(cap)
    except Exception as e:  # noqa: BLE001
        logger.debug("Market cap fetch failed for %s: %s", symbol, e)
        return None


def _fetch_market_caps(symbols: List[str], workers: int = 8) -> Dict[str, float]:
    caps: Dict[str, float] = {}
    if not symbols:
        return caps
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_fetch_market_cap, sym): sym for sym in symbols}
        for fut in as_completed(futures):
            sym = futures[fut]
            try:
                val = fut.result()
                if val is not None:
                    caps[sym] = val
            except Exception:  # noqa: BLE001
                pass
    return caps


def screen_swing(
    config: dict,
    progress: Optional[Callable[[str], None]] = None,
    price_data: Optional[Dict[str, "pd.DataFrame"]] = None,
) -> List[SwingPick]:
    """Run the swing screener and return sorted picks.

    Pass ``price_data`` (a pre-downloaded ``{symbol: DataFrame}``) to reuse a
    shared batch download across screeners instead of fetching again."""
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

    period = config.get("swing_history_period", "2y")
    if price_data is None:
        _log(f"Downloading {period} history for {len(universe)} tickers...")
        price_data = download_history(universe, period=period)

    min_cap_inr = float(config.get("swing_min_market_cap_cr", 5000.0)) * _CRORE
    min_traded_inr = float(config.get("swing_min_avg_traded_value_cr", 10.0)) * _CRORE

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

    _log(f"{len(technical_hits)} tickers pass technical + traded-value filters")

    if not technical_hits:
        return []

    _log("Fetching market capitalizations...")
    caps = _fetch_market_caps([sym for sym, _ in technical_hits])

    picks: List[SwingPick] = []
    for sym, snap in technical_hits:
        cap = caps.get(sym)
        if cap is None or cap < min_cap_inr:
            continue
        meta = metadata.get(sym, {})
        picks.append(
            SwingPick(
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
                volume_spike_pct=snap["volume_spike_pct"],
                relative_volume=snap["relative_volume"],
                risk_pct=snap.get("risk_pct", 0.0),
                market_cap_cr=round(cap / _CRORE, 1),
                avg_traded_value_cr=round(snap["avg_traded_value_inr"] / _CRORE, 2),
            )
        )

    picks.sort(
        key=lambda p: (p.relative_volume, p.adx, p.sort_rsi_band),
        reverse=True,
    )
    top_n = int(config.get("swing_top_n", 10))
    total = len(picks)
    picks = picks[:top_n]
    _log(f"{total} swing candidate(s) after market-cap filter; showing top {len(picks)}")
    return picks
