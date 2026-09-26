from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from trader.calendar import TradingCalendar
from trader.data.market_data import MarketData
from trader.strategies.antonacci_gem import GlobalEquitiesMomentum
from trader.strategy import Context

CAL = TradingCalendar.nyse(start="2000-01-01", end="2014-12-31")
SESSIONS = CAL.sessions_between("2008-01-02", "2010-12-31")
DECISION = pd.Timestamp("2010-06-30")  # a month-end session


def _panel(annual: dict[str, float], first_valid: dict[str, str] | None = None) -> MarketData:
    """Smooth exponential price paths growing at a known annual rate per symbol."""
    t = np.arange(len(SESSIONS)) / 252.0
    close = pd.DataFrame(
        {s: 100.0 * np.exp(np.log1p(g) * t) for s, g in annual.items()}, index=SESSIONS
    )
    for sym, first in (first_valid or {}).items():
        close.loc[close.index < pd.Timestamp(first), sym] = np.nan
    frames = {f: close.copy() for f in ("open", "high", "low", "close")}
    frames["volume"] = close.notna().astype(float) * 1e6
    return MarketData(frames)


def _decide(strategy, data: MarketData, when: pd.Timestamp = DECISION):
    i = int(data.index.get_loc(when))
    ctx = Context(now=when, data=data.upto(i), positions={}, weights={}, equity=1.0, calendar=CAL)
    return strategy.target_weights(ctx)


BASE = {"SPY": 0.10, "VEU": 0.05, "AGG": 0.04, "BIL": 0.02}


def test_relative_momentum_picks_stronger_equity_when_us_beats_tbills():
    gem = GlobalEquitiesMomentum()
    assert _decide(gem, _panel(BASE)) == {"SPY": 1.0}
    assert _decide(gem, _panel({**BASE, "VEU": 0.15})) == {"VEU": 1.0}


def test_absolute_momentum_on_us_sends_book_version_to_bonds():
    # US stocks lag T-bills; ex-US stocks beat them. The book checks the S&P 500 only.
    data = _panel({**BASE, "SPY": 0.01, "VEU": 0.08})
    assert _decide(GlobalEquitiesMomentum(), data) == {"AGG": 1.0}
    assert _decide(GlobalEquitiesMomentum(fallback="BIL"), data) == {"BIL": 1.0}
    # The RPH ordering checks the relative winner (VEU) against T-bills instead.
    assert _decide(GlobalEquitiesMomentum(abs_on="winner"), data) == {"VEU": 1.0}


def test_winner_ordering_falls_back_when_winner_lags_tbills():
    data = _panel({**BASE, "SPY": -0.05, "VEU": 0.01, "BIL": 0.03})
    assert _decide(GlobalEquitiesMomentum(abs_on="winner"), data) == {"AGG": 1.0}
    assert _decide(GlobalEquitiesMomentum(), data) == {"AGG": 1.0}


def test_momentum_is_twelve_month_end_to_month_end_return():
    data = _panel(BASE)
    gem = GlobalEquitiesMomentum()
    i = int(data.index.get_loc(DECISION))
    ctx = Context(
        now=DECISION, data=data.upto(i), positions={}, weights={}, equity=1.0, calendar=CAL
    )
    mom = gem.momentum(ctx)
    start = data.close.loc[pd.Timestamp("2009-06-30")]
    end = data.close.loc[DECISION]
    for sym in BASE:
        assert mom[sym] == pytest.approx(end[sym] / start[sym] - 1.0)


def test_symbol_without_enough_history_is_ignored():
    # VEU would win easily, but it only has ~8 months of data at the decision date.
    data = _panel({**BASE, "VEU": 0.30}, first_valid={"VEU": "2009-11-02"})
    gem = GlobalEquitiesMomentum()
    assert "VEU" not in gem.momentum(
        Context(
            now=DECISION,
            data=data.upto(int(data.index.get_loc(DECISION))),
            positions={},
            weights={},
            equity=1.0,
            calendar=CAL,
        )
    )
    assert _decide(gem, data) == {"SPY": 1.0}
    # Once it has 12 months of history it becomes eligible.
    assert _decide(gem, data, pd.Timestamp("2010-11-30")) == {"VEU": 1.0}


def test_symbol_with_no_data_yet_never_gets_weight():
    # Fallback AGG does not exist yet: hold T-bills rather than an unpriced asset.
    data = _panel({**BASE, "SPY": -0.10, "VEU": -0.10}, first_valid={"AGG": "2010-09-01"})
    assert _decide(GlobalEquitiesMomentum(), data) == {"BIL": 1.0}


def test_invalid_params_rejected():
    with pytest.raises(ValueError):
        GlobalEquitiesMomentum(abs_on="both")
    with pytest.raises(ValueError):
        GlobalEquitiesMomentum(lookback_months=0)
