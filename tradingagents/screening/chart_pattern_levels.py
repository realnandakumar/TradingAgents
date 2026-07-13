"""Pattern-specific entry, stop, T1/T2, and R:R for chart pattern setups."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

NEAR_BREAKOUT_STATUSES = frozenset({"APPROACHING", "AT_TRIGGER", "NEAR_TOP", "NEAR_BOTTOM"})

# Patterns where measured-move math is explicit and tested.
VALIDATED_PATTERN_IDS = frozenset({
    "double_top",
    "double_bottom",
    "ascending_triangle",
    "descending_triangle",
    "head_shoulders",
    "inverse_head_shoulders",
    "cup_and_handle",
    "rectangle",
    "bull_flag",
    "bear_flag",
    "pennant",
    "rising_wedge",
    "falling_wedge",
})


@dataclass
class PatternTradeLevels:
    entry: float
    stop: float
    target_1: float
    target_2: float
    risk_reward: float
    risk_reward_market: float
    entry_type: str
    market_entry: float
    measured_move: float
    levels_valid: bool = True

    def to_dict(self) -> dict:
        return {
            "entry_level": round(self.entry, 2),
            "stop_loss": round(self.stop, 2),
            "target_1": round(self.target_1, 2),
            "target_2": round(self.target_2, 2),
            "risk_reward_ratio": round(self.risk_reward, 2),
            "risk_reward_market": round(self.risk_reward_market, 2),
            "entry_type": self.entry_type,
            "market_entry": round(self.market_entry, 2),
            "measured_move": round(self.measured_move, 2),
            "levels_valid": self.levels_valid,
        }


def _rr(entry: float, stop: float, target: float) -> float:
    risk = abs(entry - stop)
    if risk <= 0:
        return 0.0
    return abs(target - entry) / risk


def _pack(
    entry: float,
    stop: float,
    target_1: float,
    target_2: float,
    close: float,
    measured_move: float,
) -> Optional[PatternTradeLevels]:
    if entry <= 0 or stop <= 0 or not all(map(lambda x: x > 0 and x == x, (entry, stop, target_1, target_2))):
        return None
    rr_trigger = _rr(entry, stop, target_1)
    rr_market = _rr(close, stop, target_1)
    if rr_trigger <= 0:
        return None
    return PatternTradeLevels(
        entry=entry,
        stop=stop,
        target_1=target_1,
        target_2=target_2,
        risk_reward=rr_trigger,
        risk_reward_market=rr_market,
        entry_type="trigger",
        market_entry=close,
        measured_move=measured_move,
        levels_valid=True,
    )


def compute_pattern_trade_levels(
    pattern_id: str,
    bias: str,
    setup_status: str,
    trigger: float,
    support: float,
    resistance: float,
    close: float,
    *,
    pole_height: float = 0.0,
    shoulder_stop: float = 0.0,
    handle_low: float = 0.0,
    handle_high: float = 0.0,
    wedge_height: float = 0.0,
    pole_bullish: bool = True,
) -> Optional[PatternTradeLevels]:
    if setup_status not in NEAR_BREAKOUT_STATUSES:
        return None
    if pattern_id not in VALIDATED_PATTERN_IDS:
        return None

    height = resistance - support if resistance > support else 0.0
    move = height

    if pattern_id in {"bull_flag", "bear_flag", "pennant"}:
        if pole_height <= 0:
            return None
        move = pole_height
        if pattern_id == "bull_flag" or (pattern_id == "pennant" and pole_bullish):
            entry, stop = trigger if trigger > 0 else resistance, support
            t1 = entry + pole_height
            t2 = entry + 2.0 * pole_height
        else:
            entry, stop = trigger if trigger > 0 else support, resistance
            t1 = entry - pole_height
            t2 = entry - 2.0 * pole_height
        return _pack(entry, stop, t1, t2, close, move)

    if pattern_id in {"rising_wedge", "falling_wedge"}:
        move = wedge_height if wedge_height > 0 else height
        if move <= 0:
            return None
        if pattern_id == "rising_wedge":
            entry, stop = support, resistance
            t1 = entry - move
            t2 = entry - 2.0 * move
        else:
            entry, stop = resistance, support
            t1 = entry + move
            t2 = entry + 2.0 * move
        return _pack(entry, stop, t1, t2, close, move)

    if pattern_id == "head_shoulders":
        move = height
        entry = trigger if trigger > 0 else support
        stop = shoulder_stop if shoulder_stop > 0 else resistance
        t1 = entry - move
        t2 = entry - 2.0 * move
        return _pack(entry, stop, t1, t2, close, move)

    if pattern_id == "inverse_head_shoulders":
        move = height
        entry = trigger if trigger > 0 else resistance
        stop = shoulder_stop if shoulder_stop > 0 else support
        t1 = entry + move
        t2 = entry + 2.0 * move
        return _pack(entry, stop, t1, t2, close, move)

    if pattern_id == "cup_and_handle":
        move = height
        entry = handle_high if handle_high > 0 else resistance
        stop = handle_low if handle_low > 0 else support
        t1 = entry + move
        t2 = entry + 2.0 * move
        return _pack(entry, stop, t1, t2, close, move)

    if bias == "BULLISH":
        entry = trigger if trigger > 0 else resistance
        stop = support
        t1 = entry + move
        t2 = entry + 2.0 * move
    elif bias == "BEARISH":
        entry = trigger if trigger > 0 else support
        stop = resistance
        t1 = entry - move
        t2 = entry - 2.0 * move
    elif setup_status == "NEAR_TOP":
        entry, stop = resistance, support
        t1 = resistance + move
        t2 = resistance + 2.0 * move
    elif setup_status == "NEAR_BOTTOM":
        entry, stop = support, resistance
        t1 = support - move
        t2 = support - 2.0 * move
    else:
        return None

    return _pack(entry, stop, t1, t2, close, move)


def classify_forward_outcome(
    bias: str,
    entry: float,
    stop: float,
    target_1: float,
    target_2: float,
    highs,
    lows,
    closes,
) -> str:
    """Label forward path: WIN_T1, WIN_T2, STOPPED, FALSE_BREAKOUT, EXPIRED."""
    if len(highs) == 0:
        return "EXPIRED"

    bullish = bias == "BULLISH" or (bias == "NEUTRAL" and target_1 > entry)
    stopped = False
    t1_hit = False
    t2_hit = False
    false_break = False

    for hi, lo, cl in zip(highs, lows, closes):
        if bullish:
            if lo <= stop:
                stopped = True
                break
            if hi >= target_2:
                t2_hit = True
                break
            if hi >= target_1:
                t1_hit = True
            if hi >= entry * 1.02 and lo < entry * 0.99:
                false_break = True
        else:
            if hi >= stop:
                stopped = True
                break
            if lo <= target_2:
                t2_hit = True
                break
            if lo <= target_1:
                t1_hit = True
            if lo <= entry * 0.98 and hi > entry * 1.01:
                false_break = True

    if stopped:
        return "STOPPED"
    if t2_hit:
        return "WIN_T2"
    if t1_hit:
        return "WIN_T1"
    if false_break and not t1_hit:
        return "FALSE_BREAKOUT"
    return "EXPIRED"
