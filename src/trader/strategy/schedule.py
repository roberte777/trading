"""Rebalance schedules. A schedule answers one question: does the strategy decide
at the close of this session? The same answer drives backtests and live runs."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import pandas as pd

from trader.calendar import TradingCalendar


class Schedule(ABC):
    @abstractmethod
    def is_rebalance(self, session: pd.Timestamp, calendar: TradingCalendar) -> bool:
        """True if the strategy should compute new targets at this session's close."""

    def describe(self) -> str:
        return type(self).__name__


@dataclass(frozen=True)
class Daily(Schedule):
    def is_rebalance(self, session, calendar) -> bool:
        return True

    def describe(self) -> str:
        return "every session"


@dataclass(frozen=True)
class WeekEnd(Schedule):
    """Last session of the week, or ``offset`` sessions before it."""

    offset: int = 0

    def is_rebalance(self, session, calendar) -> bool:
        return calendar.sessions_left_in_week(session) == self.offset

    def describe(self) -> str:
        return "last session of week" + (f" - {self.offset}" if self.offset else "")


@dataclass(frozen=True)
class MonthEnd(Schedule):
    """Last session of the month, or ``offset`` sessions before it."""

    offset: int = 0
    months: tuple[int, ...] | None = None  # e.g. (3, 6, 9, 12) for quarterly

    def is_rebalance(self, session, calendar) -> bool:
        if self.months is not None and session.month not in self.months:
            return False
        return calendar.sessions_left_in_month(session) == self.offset

    def describe(self) -> str:
        base = "last session of month" + (f" - {self.offset}" if self.offset else "")
        return base if self.months is None else f"{base} in months {list(self.months)}"


@dataclass(frozen=True)
class MonthStart(Schedule):
    """The ``nth`` session of the month (1 = first)."""

    nth: int = 1

    def is_rebalance(self, session, calendar) -> bool:
        return calendar.session_of_month(session) == self.nth

    def describe(self) -> str:
        return f"session {self.nth} of month"
