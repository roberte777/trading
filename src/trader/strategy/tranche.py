"""Tranching: run a periodic strategy as N sub-portfolios on staggered rebalance days.

A monthly strategy's results depend heavily on *which* day of the month it trades
(Hoffstein, Faber & Braun, "Rebalance Timing Luck: The (Dumb) Luck of Smart Beta",
SSRN 3673910). Splitting capital into N tranches that follow the same rules but
decide ``k * spacing`` sessions apart, and holding their average, removes most of
that path dependence without changing the strategy's logic.

The wrapper is stateless: whenever any tranche is due, every tranche's weights are
recomputed from data truncated at *that tranche's* latest decision date. Backtests
and live runs therefore agree, and a restarted container needs no memory.

Use it from a config with ``execution: {tranches: 4}``.
"""

from __future__ import annotations

import pandas as pd

from trader.calendar import TradingCalendar
from trader.strategy.base import Context, Reference, Strategy
from trader.strategy.schedule import Daily, Schedule

TIMING_LUCK = Reference(
    "Hoffstein, C., Faber, N., Braun, S. (2020), Rebalance Timing Luck: The (Dumb) Luck of Smart Beta, SSRN 3673910",
    "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3673910",
)
SESSIONS_PER_MONTH = 21


class TrancheSchedule(Schedule):
    """Fires when any tranche's shifted copy of the inner schedule fires."""

    def __init__(self, inner: Schedule, offsets: tuple[int, ...]) -> None:
        self.inner = inner
        self.offsets = offsets

    def _fires(self, session: pd.Timestamp, calendar: TradingCalendar, offset: int) -> bool:
        try:
            return self.inner.is_rebalance(calendar.shift(session, offset), calendar)
        except IndexError:
            return False

    def is_rebalance(self, session, calendar) -> bool:
        return any(self._fires(session, calendar, off) for off in self.offsets)

    def last_decision(
        self, session, calendar: TradingCalendar, offset: int, max_lookback: int = 400
    ):
        """The latest session <= ``session`` on which the tranche with ``offset`` decided."""
        i = calendar.index(session)
        for j in range(min(max_lookback, i + 1)):
            d = calendar.sessions[i - j]
            if self._fires(d, calendar, offset):
                return d
        return None

    def describe(self) -> str:
        spacing = self.offsets[1] - self.offsets[0] if len(self.offsets) > 1 else 0
        return f"{self.inner.describe()}, in {len(self.offsets)} tranches {spacing} sessions apart"


class Tranched(Strategy):
    """``inner`` split into ``tranches`` equal sub-portfolios on staggered schedules."""

    def __init__(self, inner: Strategy, tranches: int = 4, spacing: int | None = None) -> None:
        if tranches < 1:
            raise ValueError("tranches must be >= 1")
        if isinstance(inner.schedule(), Daily):
            raise ValueError(f"{inner.name}: tranching applies to periodic schedules, not Daily")
        self.inner = inner
        self.tranches = tranches
        self.spacing = spacing or max(1, SESSIONS_PER_MONTH // tranches)
        self.offsets = tuple(k * self.spacing for k in range(tranches))
        self.params = inner.params
        # Identity: shadow the class-level metadata of the wrapped strategy.
        self.name = f"{inner.name}_x{tranches}"
        self.title = f"{inner.label()} ({tranches} tranches)"
        self.description = (
            f"{inner.description} Run as {tranches} equal tranches deciding "
            f"{self.spacing} sessions apart, to remove rebalance-timing luck."
        )
        self.references = (*inner.references, TIMING_LUCK)
        self.publication_date = inner.publication_date
        self.proxies = inner.proxies
        self.param_grid = inner.param_grid
        self.long_only = inner.long_only

    def universe(self) -> list[str]:
        return self.inner.universe()

    def signal_symbols(self) -> list[str]:
        return self.inner.signal_symbols()

    def warmup(self) -> int:
        return self.inner.warmup() + max(self.offsets) + 25

    def schedule(self) -> TrancheSchedule:
        return TrancheSchedule(self.inner.schedule(), self.offsets)

    def target_weights(self, ctx: Context):
        schedule = self.schedule()
        parts: list[dict[str, float]] = []
        for off in self.offsets:
            d = schedule.last_decision(ctx.now, ctx.calendar, off)
            if d is None or d < ctx.data.index[0]:
                continue
            data = ctx.data if d == ctx.now else ctx.data.upto_date(d)
            sub = Context(
                now=d,
                data=data,
                positions=ctx.positions,
                weights=ctx.weights,
                equity=ctx.equity,
                calendar=ctx.calendar,
            )
            w = self.inner.target_weights(sub)
            if w is not None:
                parts.append(dict(w))
        if not parts:
            return None
        out: dict[str, float] = {}
        for w in parts:
            for sym, v in w.items():
                out[sym] = out.get(sym, 0.0) + v / len(parts)
        return out

    def param_dict(self):
        return self.inner.param_dict()

    def with_params(self, **overrides) -> Tranched:
        return Tranched(self.inner.with_params(**overrides), self.tranches, self.spacing)

    def __repr__(self) -> str:
        return f"Tranched({self.inner!r}, tranches={self.tranches}, spacing={self.spacing})"
