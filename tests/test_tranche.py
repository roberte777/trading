from __future__ import annotations

import pandas as pd
import pytest

from trader.backtest.engine import BacktestConfig, Backtester
from trader.config import ExecutionConfig, RunConfig
from trader.strategy import Daily, MonthEnd, Strategy, Tranched

from .conftest import make_market_data
from .test_strategy_contract import _perturb_after


class OddEven(Strategy):
    """All-in A in odd months, B in even months (by decision date)."""

    name = "test_odd_even"
    title = "odd/even"
    description = "test"

    def universe(self):
        return ["SPY", "TLT"]

    def warmup(self):
        return 5

    def schedule(self):
        return MonthEnd()

    def target_weights(self, ctx):
        return {"SPY": 1.0} if ctx.now.month % 2 else {"TLT": 1.0}


@pytest.fixture(scope="module")
def market():
    return make_market_data(["SPY", "TLT"], start="2004-01-02", end="2008-12-31")


def test_single_tranche_matches_inner(market):
    data, cal = market
    # (On an unscheduled initial rebalance the wrapper uses each tranche's last
    # scheduled decision, so compare scheduled decisions only.)
    cfg = BacktestConfig(start="2005-01-03", initial_rebalance=False)
    a = Backtester(OddEven(), data, cal, cfg).run()
    b = Backtester(Tranched(OddEven(), 1), data, cal, cfg).run()
    pd.testing.assert_series_equal(a.returns, b.returns)


def test_tranches_average_staggered_decisions(market):
    data, cal = market
    t = Tranched(OddEven(), tranches=2, spacing=10)
    assert t.name == "test_odd_even_x2"
    # Mid-month: tranche 0 last decided at the previous month-end, tranche 1 ten
    # sessions before this month's end.
    res = Backtester(
        t, data, cal, BacktestConfig(start="2005-01-03", initial_rebalance=False)
    ).run()
    mixed = res.targets[(res.targets > 0).sum(axis=1) == 2]
    assert not mixed.empty
    assert set(mixed.stack().round(6).unique()) <= {0.5}
    for d in res.targets.index:
        left = cal.sessions_left_in_month(d)
        assert left in (0, 10)


def test_tranched_has_no_lookahead(market):
    data, cal = market
    cfg = BacktestConfig(start="2005-01-03")
    base = Backtester(Tranched(OddEven(), 4), data, cal, cfg).run()
    cut = base.returns.index[len(base.returns) // 2]
    pert = Backtester(Tranched(OddEven(), 4), _perturb_after(data, cut), cal, cfg).run()
    pd.testing.assert_frame_equal(base.targets.loc[:cut], pert.targets.loc[:cut], check_freq=False)


def test_rejects_daily_and_builds_from_config():
    class D(OddEven):
        name = "test_daily"

        def schedule(self):
            return Daily()

    with pytest.raises(ValueError):
        Tranched(D(), 2)
    run = RunConfig(strategy="sixty_forty", execution=ExecutionConfig(tranches=4))
    s = run.build_strategy()
    assert isinstance(s, Tranched) and s.name == "sixty_forty_x4" and s.offsets == (0, 5, 10, 15)
    assert s.with_params().name == "sixty_forty_x4"
