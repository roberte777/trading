from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import pytest

from trader.backtest.engine import BacktestConfig, Backtester
from trader.execution.costs import CostModel
from trader.execution.rebalance import RebalanceRules
from trader.strategies.benchmarks import BuyAndHold
from trader.strategy import Daily, MonthEnd, Strategy

from .conftest import make_market_data


class AllIn(Strategy):
    name = "test_all_in"

    @dataclass(frozen=True)
    class Params:
        symbol: str = "SPY"

    def universe(self):
        return [self.params.symbol]

    def warmup(self):
        return 5

    def schedule(self):
        return Daily()

    def target_weights(self, ctx):
        return {self.params.symbol: 1.0}


class Recorder(Strategy):
    """Records what it was shown, to check the engine never leaks future data."""

    name = "test_recorder"

    def __init__(self, **kw):
        super().__init__(**kw)
        self.seen: list[tuple[pd.Timestamp, pd.Timestamp, int]] = []

    def universe(self):
        return ["SPY", "TLT"]

    def warmup(self):
        return 20

    def schedule(self):
        return MonthEnd()

    def target_weights(self, ctx):
        self.seen.append((ctx.now, ctx.close.index[-1], len(ctx.close)))
        return {"SPY": 0.5, "TLT": 0.5}


class Flipper(Strategy):
    """Alternates between two assets every session: maximal turnover."""

    name = "test_flipper"

    def universe(self):
        return ["SPY", "TLT"]

    def warmup(self):
        return 2

    def schedule(self):
        return Daily()

    def target_weights(self, ctx):
        return {"SPY": 1.0} if ctx.calendar.index(ctx.now) % 2 else {"TLT": 1.0}


def free(**kw) -> BacktestConfig:
    return BacktestConfig(
        costs=CostModel(
            slippage_bps=0, sec_fee_rate=0, taf_per_share=0, taf_max=0, cat_per_share=0
        ),
        **kw,
    )


def test_signal_fills_next_open_with_slippage(market):
    data, cal = market
    cfg = BacktestConfig(
        costs=CostModel(
            slippage_bps=10, sec_fee_rate=0, taf_per_share=0, taf_max=0, cat_per_share=0
        ),
        start="2006-01-03",
    )
    res = Backtester(AllIn(), data, cal, cfg).run()
    first = res.trades.iloc[0]
    assert first["date"] == pd.Timestamp("2006-01-04")  # decided at 01-03 close
    open_px = data.open.loc["2006-01-04", "SPY"]
    assert first["ref_price"] == pytest.approx(open_px)
    assert first["fill_price"] == pytest.approx(open_px * 1.001)
    assert first["signal_price"] == pytest.approx(data.close.loc["2006-01-03", "SPY"])


def test_next_close_and_delay(market):
    data, cal = market
    res = Backtester(
        AllIn(), data, cal, free(start="2006-01-03", execution="next_close", delay=2)
    ).run()
    first = res.trades.iloc[0]
    assert first["date"] == pd.Timestamp("2006-01-05")
    assert first["ref_price"] == pytest.approx(data.close.loc["2006-01-05", "SPY"])


def test_strategy_never_sees_the_future(market):
    data, cal = market
    strat = Recorder()
    Backtester(strat, data, cal, free(start="2006-01-03")).run()
    assert len(strat.seen) > 50
    for now, last_row, length in strat.seen:
        assert now == last_row
        assert length == data.index.get_loc(now) + 1


def test_buy_and_hold_accounting_without_costs(market):
    data, cal = market
    cfg = free(start="2006-01-03", rules=RebalanceRules(fractional=True))
    res = Backtester(BuyAndHold(), data, cal, cfg).run()
    assert len(res.trades) == 1
    shares = res.trades["qty"].iloc[0]
    entry = data.open.loc["2006-01-04", "SPY"]
    assert (
        shares == pytest.approx(100_000 / data.close.loc["2006-01-03", "SPY"], abs=1e-5)
        or shares * entry <= 100_000
    )
    expected = shares * data.close["SPY"].iloc[-1] + (100_000 - shares * entry)
    assert res.equity.iloc[-1] == pytest.approx(expected, rel=1e-9)
    assert res.daily["cash"].min() >= -1e-6


def test_costs_reduce_returns_monotonically(market):
    data, cal = market
    finals = []
    for mult in (0, 1, 4):
        cfg = BacktestConfig(start="2006-01-03", costs=CostModel().scaled(mult))
        finals.append(Backtester(Flipper(), data, cal, cfg).run().equity.iloc[-1])
    assert finals[0] > finals[1] > finals[2]


def test_long_only_never_levers_or_goes_negative_cash(market):
    data, cal = market
    res = Backtester(Flipper(), data, cal, BacktestConfig(start="2006-01-03")).run()
    assert (res.daily["cash"] >= -1e-6).all()
    assert (res.daily["gross"] <= 1.0 + 1e-9).all()


def test_whole_shares_by_default(market):
    data, cal = market
    res = Backtester(Flipper(), data, cal, BacktestConfig(start="2006-01-03")).run()
    assert np.allclose(res.trades["qty"], res.trades["qty"].round())


def test_monthly_schedule_trades_only_after_month_ends(market):
    data, cal = market
    res = Backtester(Recorder(), data, cal, free(start="2006-01-03", initial_rebalance=False)).run()
    for d in res.targets.index:
        assert cal.is_month_end(d)
    for d in pd.to_datetime(res.trades["date"]).unique():
        assert cal.session_of_month(d) == 1


def test_schedule_shift_moves_decisions_earlier(market):
    data, cal = market
    res = Backtester(
        Recorder(), data, cal, free(start="2006-01-03", initial_rebalance=False, schedule_shift=3)
    ).run()
    for d in res.targets.index:
        assert cal.sessions_left_in_month(d) == 3


def test_symbol_without_data_is_not_traded():
    data, cal = make_market_data(["SPY", "TLT"], first_valid={"TLT": "2008-01-02"})

    class Both(Strategy):
        name = "test_both"

        def universe(self):
            return ["SPY", "TLT"]

        def warmup(self):
            return 1

        def schedule(self):
            return MonthEnd()

        def target_weights(self, ctx):
            ok = [s for s in self.universe() if ctx.is_tradable(s)]
            return {s: 1 / len(ok) for s in ok}

    res = Backtester(Both(), data, cal, free(start="2006-01-03")).run()
    tlt_trades = res.trades[res.trades["symbol"] == "TLT"]
    assert pd.to_datetime(tlt_trades["date"]).min() >= pd.Timestamp("2008-01-02")


def test_rejects_same_bar_execution():
    with pytest.raises(ValueError):
        BacktestConfig(delay=0)
