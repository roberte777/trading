from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from trader.calendar import TradingCalendar
from trader.data.market_data import MarketData


def make_market_data(
    symbols: list[str],
    start: str = "2004-01-01",
    end: str = "2012-12-31",
    seed: int = 0,
    drift: float = 0.07,
    vol: float = 0.18,
    rf_annual: float = 0.02,
    first_valid: dict[str, str] | None = None,
) -> tuple[MarketData, TradingCalendar]:
    """Random-walk OHLCV panel on real NYSE sessions."""
    cal = TradingCalendar.nyse(start="2000-01-01", end="2014-12-31")
    sessions = cal.sessions_between(start, end)
    rng = np.random.default_rng(seed)
    n = len(sessions)
    frames: dict[str, dict[str, np.ndarray]] = {
        f: {} for f in ("open", "high", "low", "close", "volume")
    }
    for k, sym in enumerate(symbols):
        mu = drift / 252 + 0.0001 * k
        sig = vol / np.sqrt(252) * (1 + 0.2 * k)
        rets = rng.normal(mu, sig, n)
        close = 100 * np.exp(np.cumsum(rets))
        gap = rng.normal(0, sig / 2, n)
        open_ = np.r_[close[0], close[:-1]] * np.exp(gap)
        high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, sig / 3, n)))
        low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, sig / 3, n)))
        frames["open"][sym], frames["high"][sym], frames["low"][sym] = open_, high, low
        frames["close"][sym] = close
        frames["volume"][sym] = rng.integers(1_000_000, 5_000_000, n).astype(float)
    dfs = {f: pd.DataFrame(v, index=sessions) for f, v in frames.items()}
    for sym, first in (first_valid or {}).items():
        for f in dfs:
            dfs[f].loc[: pd.Timestamp(first) - pd.Timedelta(days=1), sym] = np.nan
    rf = pd.Series(rf_annual / 252, index=sessions)
    return MarketData(dfs, rf=rf), cal


@pytest.fixture
def market():
    return make_market_data(["SPY", "TLT", "GLD", "EFA", "BIL"])
