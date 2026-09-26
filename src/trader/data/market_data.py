"""Wide daily-bar panel handed to strategies.

A ``MarketData`` holds one DataFrame per OHLCV field (rows = trading sessions,
columns = symbols). Strategies only ever see a *truncated view* ending at the
decision session, so look-ahead is structurally impossible: there is no future
row to read.
"""

from __future__ import annotations

from functools import cached_property

import numpy as np
import pandas as pd

FIELDS = ("open", "high", "low", "close", "volume")


class MarketData:
    """Split- and dividend-adjusted daily bars aligned to trading sessions.

    Prices are total-return adjusted, so ``close.pct_change()`` is the total
    return of holding the instrument (dividends reinvested).
    """

    def __init__(
        self,
        frames: dict[str, pd.DataFrame],
        *,
        rf: pd.Series | None = None,
        proxy_mask: pd.DataFrame | None = None,
        n: int | None = None,
    ) -> None:
        missing = [f for f in FIELDS if f not in frames]
        if missing:
            raise ValueError(f"missing fields: {missing}")
        close = frames["close"]
        for name, frame in frames.items():
            if not frame.index.equals(close.index) or list(frame.columns) != list(close.columns):
                raise ValueError(f"field {name!r} is not aligned with close")
        self._frames = frames
        self._rf = rf if rf is not None else pd.Series(0.0, index=close.index)
        self._proxy = (
            proxy_mask
            if proxy_mask is not None
            else pd.DataFrame(False, index=close.index, columns=close.columns)
        )
        self._n = len(close.index) if n is None else n

    # -- views -----------------------------------------------------------------
    def upto(self, i: int) -> MarketData:
        """View containing sessions ``[0, i]`` (inclusive) of the full panel."""
        if not 0 <= i < len(self._frames["close"].index):
            raise IndexError(i)
        return MarketData(self._frames, rf=self._rf, proxy_mask=self._proxy, n=i + 1)

    def upto_date(self, when) -> MarketData:
        i = int(self._frames["close"].index.searchsorted(pd.Timestamp(when), side="right")) - 1
        return self.upto(i)

    def restrict(self, symbols: list[str]) -> MarketData:
        frames = {k: v[symbols] for k, v in self._frames.items()}
        return MarketData(frames, rf=self._rf, proxy_mask=self._proxy[symbols], n=self._n)

    def _slice(self, frame: pd.DataFrame) -> pd.DataFrame:
        return frame if self._n == len(frame.index) else frame.iloc[: self._n]

    # -- fields ----------------------------------------------------------------
    @cached_property
    def open(self) -> pd.DataFrame:
        return self._slice(self._frames["open"])

    @cached_property
    def high(self) -> pd.DataFrame:
        return self._slice(self._frames["high"])

    @cached_property
    def low(self) -> pd.DataFrame:
        return self._slice(self._frames["low"])

    @cached_property
    def close(self) -> pd.DataFrame:
        return self._slice(self._frames["close"])

    @cached_property
    def volume(self) -> pd.DataFrame:
        return self._slice(self._frames["volume"])

    @cached_property
    def rf(self) -> pd.Series:
        """Daily risk-free simple return per session (T-bill accrual, causal)."""
        return self._rf.iloc[: self._n]

    @cached_property
    def proxy_mask(self) -> pd.DataFrame:
        """True where a bar was synthesized from a pre-inception proxy."""
        return self._slice(self._proxy)

    def field(self, name: str) -> pd.DataFrame:
        if name not in FIELDS:
            raise KeyError(name)
        return getattr(self, name)

    # -- metadata --------------------------------------------------------------
    @property
    def index(self) -> pd.DatetimeIndex:
        return self.close.index

    @property
    def symbols(self) -> list[str]:
        return list(self._frames["close"].columns)

    @property
    def now(self) -> pd.Timestamp:
        return self.close.index[-1]

    def __len__(self) -> int:
        return self._n

    def full_length(self) -> int:
        return len(self._frames["close"].index)

    def full(self) -> MarketData:
        return MarketData(self._frames, rf=self._rf, proxy_mask=self._proxy)

    def first_valid(self, symbol: str) -> pd.Timestamp | None:
        s = self._frames["close"][symbol]
        return s.first_valid_index()

    def to_numpy(self, name: str) -> np.ndarray:
        return self.field(name).to_numpy(dtype=float)
