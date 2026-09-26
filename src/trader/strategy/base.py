"""The strategy contract.

A strategy is a *stateless* function from market history (plus current holdings)
to target portfolio weights. It never places orders, never sees the future, and
never knows whether it is running in a backtest or in production. That is what
lets the exact same class run in the backtester and in an Alpaca container.

Minimal example::

    @register
    class TrendSPY(Strategy):
        name = "trend_spy"
        title = "SPY above 200-day SMA"

        @dataclass(frozen=True)
        class Params:
            lookback: int = 200

        def universe(self):
            return ["SPY", "BIL"]

        def warmup(self):
            return self.params.lookback + 5

        def schedule(self):
            return MonthEnd()

        def target_weights(self, ctx):
            px = ctx.close["SPY"]
            risk_on = px.iloc[-1] > px.iloc[-self.params.lookback:].mean()
            return {"SPY": 1.0} if risk_on else {"BIL": 1.0}
"""

from __future__ import annotations

import dataclasses
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, ClassVar

import numpy as np
import pandas as pd

from trader.calendar import TradingCalendar
from trader.data.market_data import MarketData
from trader.strategy.schedule import MonthEnd, Schedule


@dataclass(frozen=True)
class Reference:
    """A source the strategy is taken from."""

    citation: str
    url: str = ""


@dataclass(frozen=True)
class NoParams:
    pass


@dataclass
class Context:
    """Everything a strategy may look at when deciding, as of the close of ``now``."""

    now: pd.Timestamp
    data: MarketData
    positions: Mapping[str, float]
    weights: Mapping[str, float]
    equity: float
    calendar: TradingCalendar
    extras: dict[str, Any] = field(default_factory=dict)

    @property
    def close(self) -> pd.DataFrame:
        return self.data.close

    @property
    def open(self) -> pd.DataFrame:
        return self.data.open

    @property
    def high(self) -> pd.DataFrame:
        return self.data.high

    @property
    def low(self) -> pd.DataFrame:
        return self.data.low

    @property
    def volume(self) -> pd.DataFrame:
        return self.data.volume

    def history(self, field: str = "close", n: int | None = None) -> pd.DataFrame:
        """The last ``n`` sessions of a field (all history if ``n`` is None)."""
        frame = self.data.field(field)
        return frame if n is None else frame.iloc[-n:]

    def price(self, symbol: str) -> float:
        return float(self.data.close[symbol].iloc[-1])

    def is_tradable(self, symbol: str, min_history: int = 1) -> bool:
        """True if the symbol has a price today and at least ``min_history`` sessions of data."""
        col = self.data.close[symbol]
        if not np.isfinite(col.iloc[-1]):
            return False
        return (
            int(col.iloc[-min_history:].notna().sum()) >= min_history if min_history > 1 else True
        )

    def holding(self, symbol: str) -> bool:
        return abs(self.positions.get(symbol, 0.0)) > 1e-12

    def month_end_closes(self, symbols: list[str] | None = None) -> pd.DataFrame:
        """Close on the last session of each calendar month (current month = latest close)."""
        close = self.data.close if symbols is None else self.data.close[symbols]
        return close.groupby([close.index.year, close.index.month]).tail(1)


class Strategy(ABC):
    """Base class for all strategies. Subclass, set the class attributes, register."""

    #: Registry key; also used in config files, result folders and container names.
    name: ClassVar[str] = ""
    #: Human-readable name for reports.
    title: ClassVar[str] = ""
    description: ClassVar[str] = ""
    references: ClassVar[tuple[Reference, ...]] = ()
    #: First public date of the source. Results after it are out-of-sample.
    publication_date: ClassVar[str | None] = None
    #: Parameter dataclass. Defaults must be the values from the source.
    Params: ClassVar[type] = NoParams
    #: Alternative values per parameter, for one-at-a-time sensitivity runs.
    param_grid: ClassVar[dict[str, list[Any]]] = {}
    #: Instruments to extend backwards with older proxies (see trader.data.loader).
    proxies: ClassVar[dict[str, str]] = {}
    long_only: ClassVar[bool] = True

    def __init__(self, **params: Any) -> None:
        known = (
            {f.name for f in dataclasses.fields(self.Params)}
            if dataclasses.is_dataclass(self.Params)
            else set()
        )
        unknown = set(params) - known
        if unknown:
            raise TypeError(
                f"{self.name}: unknown params {sorted(unknown)}; expected {sorted(known)}"
            )
        self.params = self.Params(**params)

    # -- what the harness calls ---------------------------------------------------
    @abstractmethod
    def universe(self) -> list[str]:
        """Every symbol the strategy may hold."""

    def signal_symbols(self) -> list[str]:
        """Extra symbols needed only as signals (never traded)."""
        return []

    def warmup(self) -> int:
        """Sessions of history needed before the first decision."""
        return 260

    def schedule(self) -> Schedule:
        return MonthEnd()

    @abstractmethod
    def target_weights(self, ctx: Context) -> Mapping[str, float] | None:
        """Target weight per symbol as a fraction of equity.

        Omitted symbols are sold. Weights must be >= 0 for long-only strategies and
        sum to <= 1 unless the run allows leverage. Return ``None`` to leave the
        portfolio unchanged.
        """

    # -- helpers --------------------------------------------------------------------
    def data_symbols(self) -> list[str]:
        return list(dict.fromkeys([*self.universe(), *self.signal_symbols()]))

    def param_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self.params) if dataclasses.is_dataclass(self.params) else {}

    def with_params(self, **overrides: Any) -> Strategy:
        return type(self)(**{**self.param_dict(), **overrides})

    def label(self) -> str:
        return self.title or self.name

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.param_dict()})"
