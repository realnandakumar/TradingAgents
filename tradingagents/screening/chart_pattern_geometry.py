"""Pattern-specific chart geometry: window, pivots, and trendlines."""

from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

    from tradingagents.screening.chart_pattern_engine import PatternMatch

PATTERN_COLOR = "#fbbf24"


def _bar_time(df: "pd.DataFrame", idx: int) -> str:
    ts = df.index[idx]
    if hasattr(ts, "strftime"):
        return ts.strftime("%Y-%m-%d")
    return str(ts)[:10]


def _clamp_idx(df: "pd.DataFrame", idx: int) -> int:
    return max(0, min(idx, len(df) - 1))


def _line(
    line_id: str,
    label: str,
    points: List[dict],
    color: str = PATTERN_COLOR,
) -> dict:
    return {"id": line_id, "label": label, "color": color, "points": points}


def _pivot(df: "pd.DataFrame", idx: int, price: float, role: str, bullish: bool) -> dict:
    return {
        "time": _bar_time(df, idx),
        "price": round(price, 2),
        "role": role,
        "position": "belowBar" if bullish else "aboveBar",
    }


def _window_from_indices(df: "pd.DataFrame", indices: List[int], pad: int = 5) -> tuple[str, str]:
    if not indices:
        return _bar_time(df, 0), _bar_time(df, len(df) - 1)
    start = _clamp_idx(df, min(indices) - pad)
    end = len(df) - 1
    return _bar_time(df, start), _bar_time(df, end)


def _geometry_double_top(pattern_id: str, match: "PatternMatch", df: "pd.DataFrame") -> dict:
    highs = match.high_swing_idx[-2:]
    if len(highs) < 2:
        return _geometry_generic(pattern_id, match, df)

    i0, i1 = highs[0], highs[1]
    p0, p1 = float(df["High"].iloc[i0]), float(df["High"].iloc[i1])
    neck_slice = df.iloc[i0 : i1 + 1]
    neckline = float(neck_slice["Low"].min())
    mid_idx = i0 + int(neck_slice["Low"].values.argmin())
    end_t = _bar_time(df, len(df) - 1)

    pivots = [
        _pivot(df, i0, p0, "peak_1", False),
        _pivot(df, i1, p1, "peak_2", False),
    ]
    lines = [
        _line(
            f"{pattern_id}_peaks",
            "twin peaks",
            [
                {"time": _bar_time(df, i0), "value": p0},
                {"time": _bar_time(df, i1), "value": p1},
            ],
        ),
        _line(
            f"{pattern_id}_neckline",
            "neckline",
            [
                {"time": _bar_time(df, i0), "value": neckline},
                {"time": end_t, "value": neckline},
            ],
        ),
        _line(
            f"{pattern_id}_valley_link",
            "pullback",
            [
                {"time": _bar_time(df, i0), "value": p0},
                {"time": _bar_time(df, mid_idx), "value": neckline},
                {"time": _bar_time(df, i1), "value": p1},
            ],
        ),
    ]
    window_start, window_end = _window_from_indices(df, highs)
    return {"window_start": window_start, "window_end": window_end, "pivots": pivots, "lines": lines}


def _geometry_double_bottom(pattern_id: str, match: "PatternMatch", df: "pd.DataFrame") -> dict:
    lows = match.low_swing_idx[-2:]
    if len(lows) < 2:
        return _geometry_generic(pattern_id, match, df)

    i0, i1 = lows[0], lows[1]
    t0, t1 = float(df["Low"].iloc[i0]), float(df["Low"].iloc[i1])
    trough_level = (t0 + t1) / 2.0
    neck_slice = df.iloc[i0 : i1 + 1]
    neckline = float(neck_slice["High"].max())
    mid_idx = i0 + int(neck_slice["High"].values.argmax())
    end_t = _bar_time(df, len(df) - 1)

    pivots = [
        _pivot(df, i0, t0, "trough_1", True),
        _pivot(df, i1, t1, "trough_2", True),
    ]
    lines = [
        _line(
            f"{pattern_id}_troughs",
            "twin troughs",
            [
                {"time": _bar_time(df, i0), "value": t0},
                {"time": _bar_time(df, i1), "value": t1},
            ],
        ),
        _line(
            f"{pattern_id}_neckline",
            "neckline",
            [
                {"time": _bar_time(df, i0), "value": neckline},
                {"time": end_t, "value": neckline},
            ],
        ),
        _line(
            f"{pattern_id}_peak_link",
            "bounce",
            [
                {"time": _bar_time(df, i0), "value": t0},
                {"time": _bar_time(df, mid_idx), "value": neckline},
                {"time": _bar_time(df, i1), "value": t1},
            ],
        ),
    ]
    window_start, window_end = _window_from_indices(df, lows + [i0, i1])
    return {"window_start": window_start, "window_end": window_end, "pivots": pivots, "lines": lines}


def _geometry_ascending_triangle(pattern_id: str, match: "PatternMatch", df: "pd.DataFrame") -> dict:
    highs = match.high_swing_idx[-3:]
    lows = match.low_swing_idx[-3:]
    if len(highs) < 2 or len(lows) < 2:
        return _geometry_generic(pattern_id, match, df)

    flat = max(float(df["High"].iloc[i]) for i in highs)
    end_t = _bar_time(df, len(df) - 1)
    pivots: List[dict] = []
    for i, role in zip(highs, ("high_1", "high_2", "high_3")[: len(highs)]):
        pivots.append(_pivot(df, i, float(df["High"].iloc[i]), role, False))
    for i, role in zip(lows, ("low_1", "low_2", "low_3")[: len(lows)]):
        pivots.append(_pivot(df, i, float(df["Low"].iloc[i]), role, True))

    resistance_line = _line(
        f"{pattern_id}_resistance",
        "flat resistance",
        [
            {"time": _bar_time(df, highs[0]), "value": flat},
            {"time": end_t, "value": flat},
        ],
    )
    support_points = [{"time": _bar_time(df, i), "value": float(df["Low"].iloc[i])} for i in lows]
    if len(support_points) >= 2:
        support_points.append({"time": end_t, "value": support_points[-1]["value"]})
    lines = [
        resistance_line,
        _line(f"{pattern_id}_rising_support", "rising support", support_points),
    ]
    window_start, window_end = _window_from_indices(df, highs + lows)
    return {"window_start": window_start, "window_end": window_end, "pivots": pivots, "lines": lines}


def _geometry_bull_flag(pattern_id: str, match: "PatternMatch", df: "pd.DataFrame") -> dict:
    flag_bars = 12
    pole_bars = 15
    end = match.end_idx if match.end_idx >= 0 else len(df) - 1
    flag_start = max(0, end - flag_bars + 1)
    pole_start = max(0, end - flag_bars - pole_bars + 1)
    flag_df = df.iloc[flag_start : end + 1]
    pole_df = df.iloc[pole_start:flag_start]

    if pole_df.empty or flag_df.empty:
        return _geometry_generic(pattern_id, match, df)

    pole_bot = float(pole_df["Low"].iloc[0])
    pole_top = float(pole_df["High"].iloc[-1])
    flag_high = float(flag_df["High"].max())
    flag_low = float(flag_df["Low"].min())
    bullish = match.pole_bullish

    pivots = [
        _pivot(df, pole_start, pole_bot if bullish else pole_top, "pole_start", bullish),
        _pivot(df, flag_start, pole_top if bullish else pole_bot, "pole_end", bullish),
    ]
    lines = [
        _line(
            f"{pattern_id}_pole",
            "pole",
            [
                {"time": _bar_time(df, pole_start), "value": pole_bot if bullish else pole_top},
                {"time": _bar_time(df, flag_start), "value": pole_top if bullish else pole_bot},
            ],
        ),
        _line(
            f"{pattern_id}_flag_top",
            "flag top",
            [
                {"time": _bar_time(df, flag_start), "value": flag_high},
                {"time": _bar_time(df, end), "value": flag_high},
            ],
        ),
        _line(
            f"{pattern_id}_flag_bottom",
            "flag bottom",
            [
                {"time": _bar_time(df, flag_start), "value": flag_low},
                {"time": _bar_time(df, end), "value": flag_low},
            ],
        ),
    ]
    window_start, _ = _window_from_indices(df, [pole_start])
    return {
        "window_start": window_start,
        "window_end": _bar_time(df, end),
        "pivots": pivots,
        "lines": lines,
    }


def _geometry_generic(pattern_id: str, match: "PatternMatch", df: "pd.DataFrame") -> dict:
    lines: List[dict] = []
    pivots: List[dict] = []
    indices: List[int] = []

    if len(match.high_swing_idx) >= 2:
        i0, i1 = match.high_swing_idx[-2], match.high_swing_idx[-1]
        indices.extend([i0, i1])
        lines.append(
            _line(
                f"{pattern_id}_high_line",
                "resistance",
                [
                    {"time": _bar_time(df, i0), "value": float(df["High"].iloc[i0])},
                    {"time": _bar_time(df, i1), "value": float(df["High"].iloc[i1])},
                ],
            )
        )
        pivots.append(_pivot(df, i1, float(df["High"].iloc[i1]), "swing_high", False))

    if len(match.low_swing_idx) >= 2:
        i0, i1 = match.low_swing_idx[-2], match.low_swing_idx[-1]
        indices.extend([i0, i1])
        lines.append(
            _line(
                f"{pattern_id}_low_line",
                "support",
                [
                    {"time": _bar_time(df, i0), "value": float(df["Low"].iloc[i0])},
                    {"time": _bar_time(df, i1), "value": float(df["Low"].iloc[i1])},
                ],
            )
        )
        pivots.append(_pivot(df, i1, float(df["Low"].iloc[i1]), "swing_low", True))

    if match.pole_height > 0 and match.end_idx >= 0:
        end = match.end_idx
        start = max(0, end - 27)
        pole_top = float(df["High"].iloc[start : end + 1].max())
        pole_bot = float(df["Low"].iloc[start : end + 1].min())
        lines.append(
            _line(
                f"{pattern_id}_pole",
                "pole",
                [
                    {"time": _bar_time(df, start), "value": pole_bot if match.pole_bullish else pole_top},
                    {"time": _bar_time(df, end), "value": pole_top if match.pole_bullish else pole_bot},
                ],
            )
        )
        indices.append(start)

    window_start, window_end = _window_from_indices(df, indices or [match.end_idx])
    return {"window_start": window_start, "window_end": window_end, "pivots": pivots, "lines": lines}


_BUILDERS = {
    "double_bottom": _geometry_double_bottom,
    "double_top": _geometry_double_top,
    "ascending_triangle": _geometry_ascending_triangle,
    "descending_triangle": _geometry_ascending_triangle,
    "bull_flag": _geometry_bull_flag,
    "bear_flag": _geometry_bull_flag,
    "pennant": _geometry_bull_flag,
}


def build_pattern_geometry(pattern_id: str, match: "PatternMatch", df: "pd.DataFrame") -> dict:
    builder = _BUILDERS.get(pattern_id, _geometry_generic)
    return builder(pattern_id, match, df)
