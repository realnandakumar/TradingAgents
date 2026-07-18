"""NSE trading-day calendar (weekends + exchange holidays).

Holiday lists are maintained for desk session stamps and daily ops.
Extend yearly when NSE publishes the circular; keep in sync with
``dashboard/lib/nse-holidays.ts``.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional, Set, Union

import pandas as pd

# NSE holidays (closed for trading). Source: exchange circulars / common calendar.
NSE_HOLIDAYS: Set[str] = {
    # 2025
    "2025-02-26",  # Mahashivratri
    "2025-03-14",  # Holi
    "2025-03-31",  # Id-Ul-Fitr (approx / check circular)
    "2025-04-10",  # Mahavir Jayanti
    "2025-04-14",  # Dr Ambedkar Jayanti
    "2025-04-18",  # Good Friday
    "2025-05-01",  # Maharashtra Day
    "2025-08-15",  # Independence Day
    "2025-08-27",  # Ganesh Chaturthi
    "2025-10-02",  # Mahatma Gandhi Jayanti
    "2025-10-21",  # Diwali Laxmi Pujan (muhurat may differ — treat as closed for EOD)
    "2025-10-22",  # Diwali Balipratipada
    "2025-11-05",  # Guru Nanak Jayanti
    "2025-12-25",  # Christmas
    # 2026
    "2026-01-26",  # Republic Day
    "2026-03-03",  # Holi
    "2026-03-26",  # Id-Ul-Fitr (approx)
    "2026-03-31",  # Ram Navami
    "2026-04-03",  # Good Friday
    "2026-04-14",  # Dr Ambedkar Jayanti
    "2026-05-01",  # Maharashtra Day
    "2026-05-28",  # Bakri Id (approx)
    "2026-08-15",  # Independence Day
    "2026-10-02",  # Mahatma Gandhi Jayanti
    "2026-10-20",  # Diwali (Balipratipada window — verify annually)
    "2026-11-10",  # Guru Nanak Jayanti (approx)
    "2026-12-25",  # Christmas
}


def _as_date(value: Union[date, datetime, pd.Timestamp, str, None]) -> date:
    if value is None:
        return datetime.now().date()
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, pd.Timestamp):
        return value.date()
    return pd.Timestamp(value).date()


def is_nse_holiday(day: Union[date, datetime, pd.Timestamp, str, None] = None) -> bool:
    d = _as_date(day)
    return d.isoformat() in NSE_HOLIDAYS


def is_nse_trading_day(day: Union[date, datetime, pd.Timestamp, str, None] = None) -> bool:
    """True for NSE cash-market weekdays that are not exchange holidays."""
    d = _as_date(day)
    if d.weekday() >= 5:
        return False
    return d.isoformat() not in NSE_HOLIDAYS


def previous_nse_session(day: Union[date, datetime, pd.Timestamp, str, None] = None) -> date:
    """Most recent NSE session on or before *day* (exclusive if *day* is not a session)."""
    d = _as_date(day)
    while not is_nse_trading_day(d):
        d = d.fromordinal(d.toordinal() - 1)
    return d


__all__ = [
    "NSE_HOLIDAYS",
    "is_nse_holiday",
    "is_nse_trading_day",
    "previous_nse_session",
]
