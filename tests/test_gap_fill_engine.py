"""Unit tests for Gap Fill engine."""

import pandas as pd
import pytest

from tradingagents.screening.gap_fill_engine import (
    STRATEGY_ID,
    _buy_fill_progress,
    _find_latest_gap,
    _gap_at_bar,
    evaluate_gap_fill,
)

pytestmark = pytest.mark.unit


def _ohlc(
    opens: list[float],
    highs: list[float],
    lows: list[float],
    closes: list[float],
) -> pd.DataFrame:
    n = len(closes)
    return pd.DataFrame({
        "Open": opens,
        "High": highs,
        "Low": lows,
        "Close": closes,
        "Volume": [1_000_000] * n,
    })


def test_strategy_id():
    assert STRATEGY_ID == "gap_fill"


def test_gap_down_detection():
    # Prior close 100, gap down open 98 with true separation (high < prior low)
    df = _ohlc(
        opens=[100.0, 98.0],
        highs=[101.0, 98.5],
        lows=[99.0, 96.0],
        closes=[100.0, 97.0],
    )
    hit = _gap_at_bar(df, 1, gap_min_pct=0.75)
    assert hit is not None
    direction, gap_pct, gap_low, gap_high, fill_target = hit
    assert direction == "DOWN"
    assert gap_pct == pytest.approx(-2.0)
    assert fill_target == pytest.approx(100.0)
    assert gap_low == pytest.approx(96.0)


def test_gap_up_detection():
    df = _ohlc(
        opens=[100.0, 102.0],
        highs=[101.0, 104.0],
        lows=[99.0, 101.5],
        closes=[100.0, 103.0],
    )
    hit = _gap_at_bar(df, 1, gap_min_pct=0.75)
    assert hit is not None
    direction, gap_pct, _, _, fill_target = hit
    assert direction == "UP"
    assert gap_pct == pytest.approx(2.0)
    assert fill_target == pytest.approx(100.0)


def test_no_gap_without_separation():
    # Overlapping range — not a true gap
    df = _ohlc(
        opens=[100.0, 98.0],
        highs=[101.0, 100.5],
        lows=[99.0, 97.0],
        closes=[100.0, 98.5],
    )
    assert _gap_at_bar(df, 1, gap_min_pct=0.75) is None


def test_find_latest_gap_age_zero():
    base_n = 28
    opens = [100.0] * base_n
    highs = [101.0] * base_n
    lows = [99.0] * base_n
    closes = [100.0] * base_n
    # Gap down today
    opens[-1] = 98.0
    highs[-1] = 98.5
    lows[-1] = 96.0
    closes[-1] = 97.5
    lows[-2] = 99.0
    df = _ohlc(opens, highs, lows, closes)
    gap_dir, age, gap_pct, _, _, fill_target, _ = _find_latest_gap(df, 0.75, 3)
    assert gap_dir == "DOWN"
    assert age == 0
    assert fill_target == pytest.approx(100.0)


def test_buy_fill_progress_mid_range():
    # gap low 90, fill target 100, close 95 → 50%
    assert _buy_fill_progress(95.0, 90.0, 100.0) == pytest.approx(50.0)


def test_evaluate_buy_gap_down_in_progress():
    base_n = 30
    opens = [100.0] * base_n
    highs = [101.0] * base_n
    lows = [99.0] * base_n
    closes = [100.0] * base_n
    # Gap down 2 days ago
    i = -3
    opens[i] = 98.0
    highs[i] = 98.5
    lows[i] = 90.0
    closes[i] = 91.0
    lows[i - 1] = 99.0
    # Partial fill now at 95 (50% of 90→100)
    closes[-1] = 95.0
    opens[-1] = 94.0
    highs[-1] = 96.0
    lows[-1] = 93.0
    df = _ohlc(opens, highs, lows, closes)
    cfg = {
        "gap_fill_min_pct": 0.75,
        "gap_fill_max_age": 3,
        "gap_fill_min_progress": 10,
        "gap_fill_max_progress": 85,
        "gap_fill_min_bars": 20,
        "gap_fill_directions": "BUY",
    }
    sig = evaluate_gap_fill(df, cfg, symbol="GAP.NS")
    assert not sig.rejected
    assert sig.direction == "BUY"
    assert sig.fill_target == pytest.approx(100.0)
    assert 10 <= sig.fill_pct <= 85


def test_evaluate_rejects_fully_filled():
    base_n = 30
    opens = [100.0] * base_n
    highs = [101.0] * base_n
    lows = [99.0] * base_n
    closes = [100.0] * base_n
    opens[-1] = 98.0
    highs[-1] = 98.5
    lows[-1] = 96.0
    closes[-1] = 101.0  # above prior close — gap filled
    lows[-2] = 99.0
    df = _ohlc(opens, highs, lows, closes)
    sig = evaluate_gap_fill(df, {"gap_fill_min_bars": 20}, symbol="FULL.NS")
    assert sig.rejected
    assert "filled" in sig.reject_reason.lower()


def test_evaluate_rejects_insufficient_history():
    df = _ohlc([100.0], [101.0], [99.0], [100.0])
    sig = evaluate_gap_fill(df, {"gap_fill_min_bars": 30}, symbol="SHORT.NS")
    assert sig.rejected
    assert "Insufficient" in sig.remark
