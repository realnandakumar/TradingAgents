"""Walk-forward accuracy audit for Pattern Forecast."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pandas as pd

from tradingagents.screening.pattern_forecast_engine import evaluate_pattern_forecast
from tradingagents.screening.pattern_forecast_sim import simulate_forward_exit


@dataclass
class AuditTrade:
    symbol: str
    as_of_date: str
    direction: str
    probability: float
    composite_score: float
    entry: float
    projected_close: float
    projected_max: float
    stop_loss: float
    actual_close: float
    actual_max: float
    actual_min: float
    direction_hit: bool
    max_touch_hit: bool
    stop_hit: bool
    return_pct: float
    exit_reason: str = ""


@dataclass
class AuditSummary:
    symbols_tested: int = 0
    signals: int = 0
    up_signals: int = 0
    direction_accuracy: float = 0.0
    max_touch_rate: float = 0.0
    stop_hit_rate: float = 0.0
    avg_return_pct: float = 0.0
    win_rate: float = 0.0
    by_probability_bucket: Dict[str, dict] = field(default_factory=dict)
    version: str = "1.1"
    trades: List[AuditTrade] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "symbols_tested": self.symbols_tested,
            "signals": self.signals,
            "up_signals": self.up_signals,
            "direction_accuracy_pct": round(self.direction_accuracy * 100, 1),
            "max_touch_rate_pct": round(self.max_touch_rate * 100, 1),
            "stop_hit_rate_pct": round(self.stop_hit_rate * 100, 1),
            "avg_return_pct": round(self.avg_return_pct, 2),
            "win_rate_pct": round(self.win_rate * 100, 1),
            "by_probability_bucket": self.by_probability_bucket,
        }


def _bucket(probability: float) -> str:
    if probability >= 80:
        return "80-100"
    if probability >= 70:
        return "70-79"
    if probability >= 60:
        return "60-69"
    return "55-59"


def _benchmark_through(
    benchmark_df: Optional[pd.DataFrame],
    as_of: pd.Timestamp,
) -> Optional[pd.DataFrame]:
    if benchmark_df is None or benchmark_df.empty:
        return None
    try:
        return benchmark_df[benchmark_df.index <= as_of]
    except Exception:  # noqa: BLE001
        return benchmark_df


def audit_symbol(
    df: pd.DataFrame,
    config: dict,
    symbol: str = "",
    step: int = 5,
    up_only: bool = True,
    benchmark_df: Optional[pd.DataFrame] = None,
) -> List[AuditTrade]:
    horizon = int(config.get("pattern_forecast_horizon", 5))
    min_bars = int(config.get("pattern_forecast_min_bars", 126))
    stop_on_close = bool(config.get("pattern_forecast_stop_on_close_only", False))
    breakeven_pct = float(config.get("pattern_forecast_breakeven_trigger_pct", 0.0))
    trades: List[AuditTrade] = []

    if df is None or len(df) < min_bars + horizon + 10:
        return trades

    end = len(df) - horizon
    for t in range(min_bars, end, step):
        hist = df.iloc[: t + 1]
        as_of_ts = hist.index[-1]
        bench_hist = _benchmark_through(benchmark_df, as_of_ts)
        sig = evaluate_pattern_forecast(hist, config, symbol=symbol, benchmark_df=bench_hist)
        if sig.rejected or sig.direction == "NONE":
            continue
        if up_only and sig.direction != "UP":
            continue

        fwd = df.iloc[t + 1 : t + 1 + horizon]
        if len(fwd) < horizon:
            continue

        entry = float(sig.close)
        actual_close = float(fwd["Close"].iloc[-1])
        actual_max = float(fwd["High"].max())
        actual_min = float(fwd["Low"].min())
        actual_dir = "UP" if actual_close > entry else "DOWN"

        stop = float(sig.stop_loss)
        target = float(sig.projected_max_high_5d)
        sim = simulate_forward_exit(
            entry,
            stop,
            target,
            fwd,
            stop_on_close_only=stop_on_close,
            breakeven_trigger_pct=breakeven_pct,
        )
        ret_pct = 100.0 * (sim.exit_price - entry) / entry

        as_of = ""
        try:
            as_of = as_of_ts.strftime("%Y-%m-%d")
        except Exception:  # noqa: BLE001
            pass

        trades.append(
            AuditTrade(
                symbol=symbol,
                as_of_date=as_of,
                direction=sig.direction,
                probability=sig.probability,
                composite_score=sig.composite_score,
                entry=entry,
                projected_close=sig.projected_close_5d,
                projected_max=target,
                stop_loss=stop,
                actual_close=actual_close,
                actual_max=actual_max,
                actual_min=actual_min,
                direction_hit=actual_dir == sig.direction,
                max_touch_hit=sim.target_hit,
                stop_hit=sim.stop_hit,
                return_pct=round(ret_pct, 2),
                exit_reason=sim.exit_reason,
            )
        )
    return trades


def summarize_audit(
    trades: List[AuditTrade],
    symbols_tested: int = 0,
    version: str = "1.1",
) -> AuditSummary:
    if not trades:
        return AuditSummary(symbols_tested=symbols_tested, version=version)

    direction_hits = sum(1 for t in trades if t.direction_hit)
    max_hits = sum(1 for t in trades if t.max_touch_hit)
    stops = sum(1 for t in trades if t.stop_hit)
    wins = sum(1 for t in trades if t.return_pct > 0)
    avg_ret = sum(t.return_pct for t in trades) / len(trades)

    buckets: Dict[str, dict] = {}
    for t in trades:
        b = _bucket(t.probability)
        buckets.setdefault(b, {"n": 0, "dir_hit": 0, "max_hit": 0, "wins": 0})
        buckets[b]["n"] += 1
        buckets[b]["dir_hit"] += int(t.direction_hit)
        buckets[b]["max_hit"] += int(t.max_touch_hit)
        buckets[b]["wins"] += int(t.return_pct > 0)

    for b, stats in buckets.items():
        n = stats["n"]
        stats["direction_accuracy_pct"] = round(100 * stats["dir_hit"] / n, 1)
        stats["max_touch_rate_pct"] = round(100 * stats["max_hit"] / n, 1)
        stats["win_rate_pct"] = round(100 * stats["wins"] / n, 1)

    return AuditSummary(
        symbols_tested=symbols_tested,
        signals=len(trades),
        up_signals=sum(1 for t in trades if t.direction == "UP"),
        direction_accuracy=direction_hits / len(trades),
        max_touch_rate=max_hits / len(trades),
        stop_hit_rate=stops / len(trades),
        avg_return_pct=avg_ret,
        win_rate=wins / len(trades),
        by_probability_bucket=buckets,
        version=version,
        trades=trades,
    )


def audit_universe(
    config: dict,
    price_data: Dict[str, pd.DataFrame],
    step: int = 5,
    up_only: bool = True,
    benchmark_df: Optional[pd.DataFrame] = None,
    version: str = "1.1",
) -> AuditSummary:
    benchmark = config.get("paper_benchmark", "^NSEI")
    if benchmark_df is None:
        benchmark_df = price_data.get(benchmark)

    all_trades: List[AuditTrade] = []
    for sym, df in price_data.items():
        if sym == benchmark or df is None or df.empty:
            continue
        all_trades.extend(
            audit_symbol(
                df, config, symbol=sym, step=step, up_only=up_only, benchmark_df=benchmark_df
            )
        )
    tested = len(price_data) - (1 if benchmark in price_data else 0)
    return summarize_audit(all_trades, symbols_tested=tested, version=version)
