"""NYSE trading-session calendar shared by backtests and live trading.

Both modes answer "is this session a rebalance day?" from the same calendar, so a
month-end strategy trades on exactly the same sessions in a backtest and in prod.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd


def to_session(value) -> pd.Timestamp:
    """Normalize a date-like value to a tz-naive midnight Timestamp."""
    ts = pd.Timestamp(value)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("America/New_York").tz_localize(None)
    return ts.normalize()


def _run_positions(keys: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """For consecutive runs of equal keys, return (position in run, sessions left in run)."""
    n = len(keys)
    pos = np.zeros(n, dtype=np.int64)
    left = np.zeros(n, dtype=np.int64)
    if n == 0:
        return pos, left
    starts = np.r_[0, np.flatnonzero(np.diff(keys)) + 1]
    ends = np.r_[starts[1:], n]
    for s, e in zip(starts, ends, strict=True):
        run = np.arange(e - s)
        pos[s:e] = run
        left[s:e] = run[::-1]
    return pos, left


class TradingCalendar:
    """An ordered set of trading sessions (tz-naive midnight timestamps).

    The final month/week of the calendar may be truncated, so build calendars that
    extend past the last date you query (``TradingCalendar.nyse`` pads a year ahead).
    """

    def __init__(self, sessions) -> None:
        idx = pd.DatetimeIndex(sessions)
        if idx.tz is not None:
            idx = idx.tz_localize(None)
        self.sessions = idx.normalize().unique().sort_values()
        months = np.asarray(self.sessions.year * 12 + self.sessions.month)
        iso = self.sessions.isocalendar()
        weeks = np.asarray(iso["year"].astype(np.int64) * 100 + iso["week"].astype(np.int64))
        self._month_pos, self._month_left = _run_positions(months)
        self._week_pos, self._week_left = _run_positions(weeks)

    @classmethod
    def nyse(cls, start="1985-01-01", end=None) -> TradingCalendar:
        """NYSE sessions from ``start`` through ``end`` (default: one year from today)."""
        end = (
            to_session(end)
            if end is not None
            else to_session(pd.Timestamp.today()) + pd.Timedelta(days=400)
        )
        return _nyse_cached(to_session(start), end)

    def __len__(self) -> int:
        return len(self.sessions)

    def __contains__(self, value) -> bool:
        return self.is_session(value)

    @property
    def first(self) -> pd.Timestamp:
        return self.sessions[0]

    @property
    def last(self) -> pd.Timestamp:
        return self.sessions[-1]

    def index(self, value) -> int:
        ts = to_session(value)
        i = int(self.sessions.searchsorted(ts))
        if i >= len(self.sessions) or self.sessions[i] != ts:
            raise KeyError(f"{ts.date()} is not a trading session")
        return i

    def is_session(self, value) -> bool:
        ts = to_session(value)
        i = int(self.sessions.searchsorted(ts))
        return i < len(self.sessions) and self.sessions[i] == ts

    def next_session(self, value, n: int = 1) -> pd.Timestamp:
        """The n-th session strictly after ``value`` (which need not be a session)."""
        i = int(self.sessions.searchsorted(to_session(value), side="right")) + n - 1
        if i >= len(self.sessions):
            raise IndexError(f"calendar ends at {self.last.date()}")
        return self.sessions[i]

    def prev_session(self, value, n: int = 1) -> pd.Timestamp:
        """The n-th session strictly before ``value``."""
        i = int(self.sessions.searchsorted(to_session(value), side="left")) - n
        if i < 0:
            raise IndexError(f"calendar starts at {self.first.date()}")
        return self.sessions[i]

    def latest_session_on_or_before(self, value) -> pd.Timestamp:
        i = int(self.sessions.searchsorted(to_session(value), side="right")) - 1
        if i < 0:
            raise IndexError(f"calendar starts at {self.first.date()}")
        return self.sessions[i]

    def shift(self, value, n: int) -> pd.Timestamp:
        """Session ``n`` sessions after (n > 0) or before (n < 0) the session ``value``."""
        i = self.index(value) + n
        if not 0 <= i < len(self.sessions):
            raise IndexError("shift moves outside the calendar")
        return self.sessions[i]

    def sessions_between(self, start, end) -> pd.DatetimeIndex:
        s, e = to_session(start), to_session(end)
        return self.sessions[(self.sessions >= s) & (self.sessions <= e)]

    def session_of_month(self, value) -> int:
        """1-based position of the session within its calendar month."""
        return int(self._month_pos[self.index(value)]) + 1

    def sessions_left_in_month(self, value) -> int:
        """Sessions remaining in the month after this one (0 on the last session)."""
        return int(self._month_left[self.index(value)])

    def session_of_week(self, value) -> int:
        return int(self._week_pos[self.index(value)]) + 1

    def sessions_left_in_week(self, value) -> int:
        return int(self._week_left[self.index(value)])

    def is_month_end(self, value) -> bool:
        return self.sessions_left_in_month(value) == 0

    def is_week_end(self, value) -> bool:
        return self.sessions_left_in_week(value) == 0


@lru_cache(maxsize=8)
def _nyse_cached(start: pd.Timestamp, end: pd.Timestamp) -> TradingCalendar:
    import exchange_calendars as xcals

    cal = xcals.get_calendar("XNYS", start=start, end=end)
    return TradingCalendar(cal.sessions)
