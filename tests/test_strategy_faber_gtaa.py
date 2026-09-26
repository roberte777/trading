from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from trader.backtest.engine import BacktestConfig, Backtester
from trader.calendar import TradingCalendar
from trader.data.market_data import MarketData
from trader.strategies.faber_gtaa import FaberGTAA
from trader.strategy import Context

from .conftest import make_market_data

CAL = TradingCalendar.nyse(start="2009-01-01", end="2012-12-31")
SESSIONS = CAL.sessions_between("2010-01-04", "2011-12-30")
NOW = SESSIONS[-1]  # 2011-12-30, the last session of December 2011


def _is_month_end(index: pd.DatetimeIndex) -> np.ndarray:
    ends = pd.Series(index, index=index).groupby([index.year, index.month]).transform("max")
    return (ends == index).to_numpy()


def _market(closes: dict[str, pd.Series]) -> MarketData:
    close = pd.DataFrame(closes, index=SESSIONS)
    volume = close.notna() * 1e6
    frames = {"open": close, "high": close, "low": close, "close": close, "volume": volume}
    return MarketData(frames, rf=pd.Series(0.0, index=SESSIONS))


def _decide(strategy: FaberGTAA, data: MarketData, when=NOW) -> dict[str, float]:
    i = int(data.index.get_loc(when))
    ctx = Context(
        now=when,
        data=data.upto(i),
        positions={},
        weights={},
        equity=100_000.0,
        calendar=CAL,
    )
    return dict(strategy.target_weights(ctx))


def _trend(daily: float) -> pd.Series:
    return pd.Series(100.0 * (1.0 + daily) ** np.arange(len(SESSIONS)), index=SESSIONS)


def test_rising_sleeves_held_falling_sleeves_in_bills():
    data = _market(
        {
            "SPY": _trend(0.001),
            "EFA": _trend(-0.001),
            "IEF": _trend(0.0005),
            "GSG": _trend(-0.002),
            "VNQ": _trend(0.001),
            "DBC": _trend(0.001),  # signal-only symbol; never traded by the default
            "BIL": _trend(0.0001),
        }
    )
    got = _decide(FaberGTAA(), data)
    assert got == pytest.approx({"SPY": 0.2, "IEF": 0.2, "VNQ": 0.2, "BIL": 0.4})


def test_sma_is_on_month_end_closes_including_current_month_strict():
    month_end = _is_month_end(SESSIONS)
    flat = pd.Series(100.0, index=SESSIONS)

    # SPY: Feb-2011 month end 50, Mar-Nov month ends 100, today 99. SMA10 including
    # today = 99.9 > 99 -> out. (Excluding today, Feb..Nov averages 95 < 99 -> would be in.)
    spy = flat.copy()
    spy[pd.Timestamp("2011-02-28")] = 50.0
    spy[NOW] = 99.0
    # EFA: month ends at 100, today 101, but every other session is 200. Only month-end
    # closes count, so SMA10 = 100.1 < 101 -> in (a daily SMA would say out).
    efa = pd.Series(np.where(month_end, 100.0, 200.0), index=SESSIONS)
    efa[NOW] = 101.0
    # IEF: price exactly equal to its SMA -> strict ">" fails -> out.
    data = _market(
        {
            "SPY": spy,
            "EFA": efa,
            "IEF": flat,
            "GSG": _trend(0.001),
            "VNQ": _trend(-0.001),
            "DBC": flat,
            "BIL": flat,
        }
    )
    assert spy[month_end][-10:].mean() == pytest.approx(99.9)
    got = _decide(FaberGTAA(), data)
    assert got == pytest.approx({"EFA": 0.2, "GSG": 0.2, "BIL": 0.6})


def test_symbol_without_enough_history_gets_no_weight():
    rising = _trend(0.001)
    late = rising.loc["2011-06-01":].reindex(SESSIONS)  # 7 month ends by Dec-2011
    data = _market(
        {
            "SPY": rising,
            "EFA": rising,
            "IEF": rising,
            "GSG": late,
            "VNQ": pd.Series(np.nan, index=SESSIONS),  # no data at all yet
            "DBC": rising,
            "BIL": _trend(0.0001),
        }
    )
    got = _decide(FaberGTAA(), data)
    assert got == pytest.approx({"SPY": 0.2, "EFA": 0.2, "IEF": 0.2, "BIL": 0.4})
    # With a 6-month SMA the late commodity sleeve has enough month ends to qualify.
    got6 = _decide(FaberGTAA(sma_months=6), data)
    assert got6 == pytest.approx({"SPY": 0.2, "EFA": 0.2, "IEF": 0.2, "GSG": 0.2, "BIL": 0.2})


def test_commodity_param_swaps_the_traded_etf():
    gtaa = FaberGTAA()
    assert gtaa.universe() == ["SPY", "EFA", "IEF", "GSG", "VNQ", "BIL"]
    assert gtaa.signal_symbols() == ["DBC"]
    dbc = FaberGTAA(commodity="DBC")
    assert dbc.universe() == ["SPY", "EFA", "IEF", "DBC", "VNQ", "BIL"]
    assert "DBC" in dbc.proxies and "GSG" in dbc.proxies

    data = _market(
        {
            "SPY": _trend(-0.001),
            "EFA": _trend(-0.001),
            "IEF": _trend(-0.001),
            "GSG": _trend(-0.001),
            "VNQ": _trend(-0.001),
            "DBC": _trend(0.001),
            "BIL": _trend(0.0001),
        }
    )
    assert _decide(gtaa, data) == pytest.approx({"BIL": 1.0})
    assert _decide(dbc, data) == pytest.approx({"DBC": 0.2, "BIL": 0.8})


def test_backtest_never_holds_a_sleeve_before_its_data():
    gtaa = FaberGTAA()
    data, cal = make_market_data(
        [*gtaa.data_symbols(), "SPY"],
        start="2004-01-02",
        end="2008-12-31",
        seed=3,
        first_valid={"GSG": "2006-07-21"},
    )
    res = Backtester(gtaa, data, cal, BacktestConfig(start="2005-01-03")).run()
    targets = res.targets
    # GSG needs 10 month-end closes: Jul-2006 .. Apr-2007.
    assert (targets.loc[:"2007-03-31", "GSG"] == 0).all()
    assert (targets.loc["2007-04-01":, "GSG"] > 0).any()
    assert (res.weights.loc[:"2007-04-30", "GSG"] == 0).all()
    np.testing.assert_allclose(targets.sum(axis=1), 1.0)
    assert set(np.round(targets.drop(columns="BIL").stack().unique(), 12)) <= {0.0, 0.2}
