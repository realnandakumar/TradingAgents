"""Walk-forward accuracy audit for Chart Patterns screener."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional

import pandas as pd

from tradingagents.screening.chart_pattern_engine import scan_chart_patterns
from tradingagents.screening.chart_pattern_levels import (
    classify_forward_outcome,
    compute_pattern_trade_levels,
)


@dataclass
class ChartPatternAuditTrade:
    symbol: str
    pattern_id: str
    as_of_date: str
    setup_status: str
    confidence: float
    actionability_score: float
    entry: float
    stop: float
    target_1: float
    target_2: float
    risk_reward: float
    close: float
    entry_fill: float
    fill_mode: str
    outcome: str
    return_pct: float


@dataclass
class ChartPatternAuditSummary:
    symbols_tested: int = 0
    signals: int = 0
    t1_hit_rate: float = 0.0
    t2_hit_rate: float = 0.0
    stop_hit_rate: float = 0.0
    false_breakout_rate: float = 0.0
    avg_return_pct: float = 0.0
    by_pattern: Dict[str, dict] = field(default_factory=dict)
    by_confidence_bucket: Dict[str, dict] = field(default_factory=dict)
    fill_mode: str = "close"
    version: str = "1.0"
    trades: List[ChartPatternAuditTrade] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "symbols_tested": self.symbols_tested,
            "signals": self.signals,
            "fill_mode": getattr(self, "fill_mode", "close"),
            "t1_hit_rate_pct": round(self.t1_hit_rate * 100, 1),
            "t2_hit_rate_pct": round(self.t2_hit_rate * 100, 1),
            "stop_hit_rate_pct": round(self.stop_hit_rate * 100, 1),
            "false_breakout_rate_pct": round(self.false_breakout_rate * 100, 1),
            "avg_return_pct": round(self.avg_return_pct, 2),
            "by_pattern": self.by_pattern,
            "by_confidence_bucket": self.by_confidence_bucket,
        }


def _bucket(confidence: float) -> str:
    if confidence >= 75:
        return "75-100"
    if confidence >= 65:
        return "65-74"
    return "55-64"


def audit_symbol(
    df: pd.DataFrame,
    config: dict,
    symbol: str = "",
    step: int = 5,
    horizon: int = 20,
    fill_mode: Literal["close", "next_open"] = "close",
) -> List[ChartPatternAuditTrade]:
    min_bars = int(config.get("chart_pattern_min_bars", 60))
    trades: List[ChartPatternAuditTrade] = []
    if df is None or len(df) < min_bars + horizon + 10:
        return trades

    extra = 1 if fill_mode == "next_open" else 0
    end = len(df) - horizon - extra
    for t in range(min_bars, end, step):
        hist = df.iloc[: t + 1]
        as_of_ts = hist.index[-1]
        audit_config = {**config, "chart_pattern_exclude_today": False}
        hits = scan_chart_patterns(hist, audit_config, symbol=symbol)
        if not hits:
            continue

        fwd = df.iloc[t + 1 : t + 1 + horizon]
        if len(fwd) < horizon:
            continue

        for hit in hits:
            if not hit.levels_valid:
                levels = compute_pattern_trade_levels(
                    hit.pattern_id,
                    hit.bias,
                    hit.setup_status,
                    hit.trigger_level,
                    hit.support_level,
                    hit.resistance_level,
                    hit.close,
                )
                if levels is None:
                    continue
                entry, stop, t1, t2, rr = (
                    levels.entry,
                    levels.stop,
                    levels.target_1,
                    levels.target_2,
                    levels.risk_reward,
                )
            else:
                entry, stop, t1, t2, rr = (
                    hit.entry_level,
                    hit.stop_loss,
                    hit.target_1,
                    hit.target_2,
                    hit.risk_reward_ratio,
                )

            outcome = classify_forward_outcome(
                hit.bias,
                entry,
                stop,
                t1,
                t2,
                fwd["High"].tolist(),
                fwd["Low"].tolist(),
                fwd["Close"].tolist(),
            )
            if fill_mode == "next_open":
                entry_fill = float(fwd["Open"].iloc[0])
            else:
                entry_fill = hit.close
            exit_px = float(fwd["Close"].iloc[-1])
            ret = (exit_px - entry_fill) / entry_fill * 100.0
            if hit.bias == "BEARISH":
                ret = -ret

            trades.append(
                ChartPatternAuditTrade(
                    symbol=symbol,
                    pattern_id=hit.pattern_id,
                    as_of_date=str(as_of_ts)[:10],
                    setup_status=hit.setup_status,
                    confidence=hit.confidence,
                    actionability_score=hit.actionability_score,
                    entry=entry,
                    stop=stop,
                    target_1=t1,
                    target_2=t2,
                    risk_reward=rr,
                    close=hit.close,
                    entry_fill=entry_fill,
                    fill_mode=fill_mode,
                    outcome=outcome,
                    return_pct=ret,
                )
            )
    return trades


def audit_universe(
    config: dict,
    price_data: Dict[str, pd.DataFrame],
    step: int = 5,
    horizon: int = 20,
    fill_mode: Literal["close", "next_open"] = "close",
) -> ChartPatternAuditSummary:
    all_trades: List[ChartPatternAuditTrade] = []
    for symbol, df in price_data.items():
        if df is None or df.empty:
            continue
        all_trades.extend(
            audit_symbol(
                df,
                config,
                symbol=symbol,
                step=step,
                horizon=horizon,
                fill_mode=fill_mode,
            )
        )

    summary = ChartPatternAuditSummary(
        symbols_tested=len(price_data),
        signals=len(all_trades),
        trades=all_trades,
        fill_mode=fill_mode,
    )
    if not all_trades:
        return summary

    n = len(all_trades)
    summary.t1_hit_rate = sum(1 for t in all_trades if t.outcome == "WIN_T1") / n
    summary.t2_hit_rate = sum(1 for t in all_trades if t.outcome == "WIN_T2") / n
    summary.stop_hit_rate = sum(1 for t in all_trades if t.outcome == "STOPPED") / n
    summary.false_breakout_rate = sum(1 for t in all_trades if t.outcome == "FALSE_BREAKOUT") / n
    summary.avg_return_pct = sum(t.return_pct for t in all_trades) / n

    by_pattern: Dict[str, List[ChartPatternAuditTrade]] = {}
    by_bucket: Dict[str, List[ChartPatternAuditTrade]] = {}
    for trade in all_trades:
        by_pattern.setdefault(trade.pattern_id, []).append(trade)
        by_bucket.setdefault(_bucket(trade.confidence), []).append(trade)

    for pid, rows in by_pattern.items():
        m = len(rows)
        summary.by_pattern[pid] = {
            "signals": m,
            "t1_hit_rate_pct": round(sum(1 for r in rows if r.outcome == "WIN_T1") / m * 100, 1),
            "stop_hit_rate_pct": round(sum(1 for r in rows if r.outcome == "STOPPED") / m * 100, 1),
            "avg_return_pct": round(sum(r.return_pct for r in rows) / m, 2),
        }

    for bucket, rows in by_bucket.items():
        m = len(rows)
        summary.by_confidence_bucket[bucket] = {
            "signals": m,
            "t1_hit_rate_pct": round(sum(1 for r in rows if r.outcome == "WIN_T1") / m * 100, 1),
            "avg_return_pct": round(sum(r.return_pct for r in rows) / m, 2),
        }

    return summary
