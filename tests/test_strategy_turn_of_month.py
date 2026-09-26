from __future__ import annotations

import pandas as pd
import pytest

from trader.backtest.engine import BacktestConfig, Backtester
from trader.execution.rebalance import RebalanceRules
from trader.strategies.turn_of_month import TurnOfTheMonth
from trader.strategy import Context

from .conftest import make_market_data


def _decide(strategy, data, cal, when: str):
    i = int(data.index.get_loc(pd.Timestamp(when)))
    ctx = Context(
        now=data.index[i],
        data=data.upto(i),
        positions={},
        weights={},
        equity=1.0,
        calendar=cal,
    )
    return strategy.target_weights(ctx)


@pytest.fixture(scope="module")
def market():
    return make_market_data(["SPY", "BIL"], start="2009-06-01", end="2013-06-28", seed=3)


# January 2010 ends on Fri 29 Jan; 1-3 Feb are sessions 1-3 of February, 4 Feb is session 4.
@pytest.mark.parametrize(
    ("decision", "expected"),
    [
        ("2010-01-27", {"BIL": 1.0}),  # fills 28 Jan (day -2): outside
        ("2010-01-28", {"SPY": 1.0}),  # fills 29 Jan (day -1, last session)
        ("2010-01-29", {"SPY": 1.0}),  # fills 1 Feb (day +1)
        ("2010-02-01", {"SPY": 1.0}),  # fills 2 Feb (day +2)
        ("2010-02-02", {"SPY": 1.0}),  # fills 3 Feb (day +3)
        ("2010-02-03", {"BIL": 1.0}),  # fills 4 Feb (day +4): exit
        ("2010-02-16", {"BIL": 1.0}),  # mid-month
    ],
)
def test_long_spy_only_for_sessions_minus1_to_plus3(market, decision, expected):
    data, cal = market
    assert _decide(TurnOfTheMonth(), data, cal, decision) == expected


# Good Friday 29 Mar 2013 closes the NYSE, so Thu 28 Mar is trading day -1.
@pytest.mark.parametrize(
    ("decision", "expected"),
    [
        ("2013-03-26", {"BIL": 1.0}),  # fills 27 Mar (day -2)
        ("2013-03-27", {"SPY": 1.0}),  # fills 28 Mar (day -1)
        ("2013-03-28", {"SPY": 1.0}),  # fills 1 Apr (day +1)
        ("2013-04-02", {"SPY": 1.0}),  # fills 3 Apr (day +3)
        ("2013-04-03", {"BIL": 1.0}),  # fills 4 Apr (day +4)
    ],
)
def test_window_follows_exchange_calendar_over_month_end_holiday(market, decision, expected):
    data, cal = market
    assert _decide(TurnOfTheMonth(), data, cal, decision) == expected


def test_param_variants_widen_and_narrow_the_window(market):
    data, cal = market
    wide_before = TurnOfTheMonth(days_before=2)
    assert _decide(wide_before, data, cal, "2010-01-27") == {"SPY": 1.0}  # day -2 now inside
    assert _decide(wide_before, data, cal, "2010-01-26") == {"BIL": 1.0}  # day -3 still outside
    short_after = TurnOfTheMonth(days_after=2)
    assert _decide(short_after, data, cal, "2010-02-01") == {"SPY": 1.0}  # day +2 inside
    assert _decide(short_after, data, cal, "2010-02-02") == {"BIL": 1.0}  # day +3 now outside
    with pytest.raises(ValueError):
        TurnOfTheMonth(days_after=-1)


def test_symbol_without_data_gets_no_weight():
    data, cal = make_market_data(
        ["SPY", "BIL"],
        start="2009-06-01",
        end="2010-12-31",
        first_valid={"SPY": "2010-03-01"},
    )
    # In the window, but SPY has no price yet: hold T-bills instead.
    assert _decide(TurnOfTheMonth(), data, cal, "2010-01-28") == {"BIL": 1.0}
    # Once SPY exists it is bought for the window.
    assert _decide(TurnOfTheMonth(), data, cal, "2010-03-30") == {"SPY": 1.0}

    data, cal = make_market_data(
        ["SPY", "BIL"],
        start="2009-06-01",
        end="2010-12-31",
        first_valid={"SPY": "2010-03-01", "BIL": "2010-03-01"},
    )
    assert _decide(TurnOfTheMonth(), data, cal, "2010-01-28") == {}
    assert _decide(TurnOfTheMonth(), data, cal, "2010-02-16") == {}


def test_backtest_holds_spy_exactly_on_window_sessions(market):
    """End to end: with next-open fills, SPY is held at the close of days -1, +1, +2, +3."""
    data, cal = market
    cfg = BacktestConfig(
        start="2010-01-04", end="2012-12-31", rules=RebalanceRules(rebalance_band=0.02)
    )
    res = Backtester(TurnOfTheMonth(), data, cal, cfg).run()
    held = res.weights["SPY"].iloc[1:] > 0.5  # first session is the initial fill day
    expected = pd.Series(
        [cal.sessions_left_in_month(d) == 0 or cal.session_of_month(d) <= 3 for d in held.index],
        index=held.index,
    )
    pd.testing.assert_series_equal(held, expected, check_names=False)
    # Fully invested every day after the first fill: in SPY or in BIL, never both.
    both = res.weights[["SPY", "BIL"]].iloc[1:]
    assert ((both > 0.5).sum(axis=1) == 1).all()
    # One round trip in SPY per month.
    spy_buys = res.trades[(res.trades["symbol"] == "SPY") & (res.trades["qty"] > 0)]
    assert len(spy_buys) == pytest.approx(36, abs=1)
