"""Simulate 5-day forward exit for walk-forward audit."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

import pandas as pd


@dataclass
class ForwardExit:
    exit_price: float
    stop_hit: bool
    target_hit: bool
    exit_reason: str


def simulate_forward_exit(
    entry: float,
    stop: float,
    target: float,
    fwd_df: pd.DataFrame,
    stop_on_close_only: bool = True,
    breakeven_trigger_pct: float = 2.0,
) -> ForwardExit:
    """Day-by-day exit: breakeven ratchet, close-only stop, intraday target."""
    effective_stop = stop
    trigger = 1.0 + breakeven_trigger_pct / 100.0

    for _, bar in fwd_df.iterrows():
        high = float(bar["High"])
        low = float(bar["Low"])
        close = float(bar["Close"])

        if breakeven_trigger_pct > 0 and high >= entry * trigger:
            effective_stop = max(effective_stop, entry)

        if stop_on_close_only:
            stopped = close <= effective_stop
        else:
            stopped = low <= effective_stop

        if stopped:
            return ForwardExit(
                exit_price=round(effective_stop, 2),
                stop_hit=True,
                target_hit=False,
                exit_reason="stop_loss",
            )

        if target > 0 and high >= target:
            return ForwardExit(
                exit_price=round(target, 2),
                stop_hit=False,
                target_hit=True,
                exit_reason="target_max_high",
            )

    last_close = float(fwd_df["Close"].iloc[-1])
    return ForwardExit(
        exit_price=round(last_close, 2),
        stop_hit=False,
        target_hit=False,
        exit_reason="time_exit",
    )
