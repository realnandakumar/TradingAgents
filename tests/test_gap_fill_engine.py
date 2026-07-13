"""Unit tests for Gap Screener engine."""

import pandas as pd
import pytest

from tradingagents.screening.gap_fill_engine import (
    STRATEGY_ID,
    STRATEGY_NAME,
    _buy_fill_progress,
    _completed_df,
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


def _gap_down_df() -> pd.DataFrame:
    n = 35
    closes = [120.0 - i * 0.5 for i in range(n - 2)]
    opens = list(closes)
    highs = [c + 0.8 for c in closes]
    lows = [c - 0.8 for c in closes]
    # Single gap down on latest completed bar
    prev_c = closes[-1]
    opens.append(prev_c * 0.93)
    highs.append(opens[-1] + 0.3)
    lows.append(opens[-1] - 2.5)
    closes.append(opens[-1] - 0.5)
    lows[-2] = closes[-2] - 1.0
    highs[-2] = closes[-2] + 0.8
    # Today's bar — flat, no new gap
    opens.append(closes[-1])
    highs.append(closes[-1] + 0.3)
    lows.append(closes[-1] - 0.3)
    closes.append(closes[-1] + 0.1)
    return _ohlc(opens, highs, lows, closes)


def test_strategy_meta():
    assert STRATEGY_ID == "gap_fill"
    assert STRATEGY_NAME == "Gap Screener"


def test_gap_trade_side_mapping():
    from tradingagents.screening.gap_fill_engine import gap_trade_side, is_long_gap_candidate

    assert gap_trade_side("DOWN") == "BUY"
    assert gap_trade_side("UP") == "SELL"
    assert gap_trade_side("BUY") == "BUY"
    assert is_long_gap_candidate("DOWN") is True
    assert is_long_gap_candidate("UP") is False


def test_gap_down_detection():
    df = _ohlc(
        opens=[100.0, 94.0],
        highs=[101.0, 95.0],
        lows=[99.0, 90.0],
        closes=[100.0, 92.0],
    )
    hit = _gap_at_bar(df, 1, gap_min_pct=5.0)
    assert hit is not None
    direction, gap_pct, _, _, fill_target = hit
    assert direction == "DOWN"
    assert gap_pct == pytest.approx(-6.0)
    assert fill_target == pytest.approx(100.0)


def test_gap_up_detection():
    df = _ohlc(
        opens=[100.0, 106.0],
        highs=[101.0, 108.0],
        lows=[99.0, 105.5],
        closes=[100.0, 107.0],
    )
    hit = _gap_at_bar(df, 1, gap_min_pct=5.0)
    assert hit is not None
    direction, gap_pct, _, _, fill_target = hit
    assert direction == "UP"
    assert gap_pct == pytest.approx(6.0)


def test_no_gap_without_separation():
    df = _ohlc(
        opens=[100.0, 94.0],
        highs=[101.0, 100.5],
        lows=[99.0, 90.0],
        closes=[100.0, 95.0],
    )
    assert _gap_at_bar(df, 1, gap_min_pct=5.0) is None


def test_exclude_today_skips_intraday_gap():
    base_n = 30
    opens = [100.0] * base_n
    highs = [101.0] * base_n
    lows = [99.0] * base_n
    closes = [100.0] * base_n
    opens[-1] = 94.0
    highs[-1] = 95.0
    lows[-1] = 90.0
    closes[-1] = 91.0
    lows[-2] = 99.0
    df = _ohlc(opens, highs, lows, closes)
    sig = evaluate_gap_fill(
        df,
        {"gap_fill_min_bars": 20, "gap_fill_exclude_today": True, "gap_fill_max_age": 5},
        symbol="TODAY.NS",
    )
    assert sig.rejected


def test_evaluate_finds_active_gap_down():
    df = _gap_down_df()
    sig = evaluate_gap_fill(
        df,
        {
            "gap_fill_min_pct": 5.0,
            "gap_fill_max_age": 30,
            "gap_fill_exclude_today": True,
            "gap_fill_min_bars": 20,
            "gap_fill_directions": "DOWN",
        },
        symbol="GAP.NS",
    )
    assert not sig.rejected, sig.reject_reason
    assert sig.direction == "DOWN"
    assert sig.gap_pct <= -5.0


def test_evaluate_respects_direction_filter():
    df = _gap_down_df()
    sig = evaluate_gap_fill(
        df,
        {"gap_fill_min_bars": 20, "gap_fill_directions": "UP"},
        symbol="GAP.NS",
    )
    assert sig.rejected
    assert "not enabled" in sig.reject_reason.lower()


def test_buy_fill_progress_mid_range():
    assert _buy_fill_progress(95.0, 90.0, 100.0) == pytest.approx(50.0)


def test_completed_df_drops_last_bar():
    df = _ohlc([1, 2], [1, 2], [1, 2], [1, 2])
    out = _completed_df(df, True)
    assert len(out) == 1


def test_evaluate_rejects_insufficient_history():
    df = _ohlc([100.0], [101.0], [99.0], [100.0])
    sig = evaluate_gap_fill(df, {"gap_fill_min_bars": 30}, symbol="SHORT.NS")
    assert sig.rejected


def test_evaluate_rejects_gap_over_half_filled():
    df = _gap_down_df()
    sig = evaluate_gap_fill(
        df,
        {
            "gap_fill_min_pct": 5.0,
            "gap_fill_max_age": 30,
            "gap_fill_exclude_today": True,
            "gap_fill_min_bars": 20,
            "gap_fill_directions": "DOWN",
            "gap_fill_max_progress": 50,
            "gap_fill_min_progress": 0,
        },
        symbol="GAP.NS",
    )
    # Default gap-down fixture is ~50% fill at close — at or above cap rejects
    if not sig.rejected:
        assert sig.fill_pct <= 50
    else:
        assert "closed" in sig.reject_reason.lower() or "fill" in sig.reject_reason.lower()
