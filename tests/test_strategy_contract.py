"""Contract tests applied to EVERY registered strategy.

A new strategy file is picked up automatically; if it breaks any rule below
(look-ahead, non-determinism, weights outside the universe, leverage), CI fails.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from trader.backtest.engine import BacktestConfig, Backtester
from trader.data.market_data import MarketData
from trader.strategy.registry import all_strategies

from .conftest import make_market_data

STRATEGIES = sorted(all_strategies())


def _data_for(strategy):
    symbols = list(dict.fromkeys([*strategy.data_symbols(), "SPY"]))
    return make_market_data(symbols, start="2001-01-02", end="2012-12-31", seed=11)


def _perturb_after(data: MarketData, cut: pd.Timestamp, seed: int = 5) -> MarketData:
    rng = np.random.default_rng(seed)
    frames = {}
    for field in ("open", "high", "low", "close", "volume"):
        f = data.field(field).copy()
        later = f.index > cut
        f.loc[later] = f.loc[later] * rng.uniform(0.5, 1.5, size=f.loc[later].shape)
        frames[field] = f
    return MarketData(frames, rf=data.rf)


@pytest.mark.parametrize("name", STRATEGIES)
def test_contract(name):
    cls = all_strategies()[name]
    strategy = cls()
    assert strategy.universe(), "universe must not be empty"
    assert strategy.warmup() >= 0
    data, cal = _data_for(strategy)
    cfg = BacktestConfig()
    res = Backtester(strategy, data, cal, cfg).run()
    universe = set(strategy.universe())

    # Weights: inside the universe, long-only if declared, never levered.
    assert set(res.targets.columns) <= universe
    if strategy.long_only:
        assert (res.targets.to_numpy() >= -1e-12).all()
    assert (res.targets.abs().sum(axis=1) <= 1.0 + 1e-6).all()
    assert (res.daily["gross"] <= 1.0 + 1e-6).all()
    assert np.isfinite(res.returns).all()

    # Deterministic.
    again = Backtester(cls(), data, cal, cfg).run()
    pd.testing.assert_series_equal(res.returns, again.returns)

    # No look-ahead: changing data after a cut date cannot change earlier decisions.
    cut = res.returns.index[len(res.returns) // 2]
    perturbed = Backtester(cls(), _perturb_after(data, cut), cal, cfg).run()
    before = res.targets.loc[:cut]
    pd.testing.assert_frame_equal(
        before.reindex(columns=sorted(before.columns)),
        perturbed.targets.loc[:cut].reindex(columns=sorted(before.columns)).fillna(0.0),
        check_freq=False,
    )


@pytest.mark.parametrize("name", STRATEGIES)
def test_metadata(name):
    cls = all_strategies()[name]
    assert cls.title, "set a human-readable title"
    assert cls.description, "describe the strategy"
    for sym, proxy in cls.proxies.items():
        assert sym in cls().universe() or sym in cls().signal_symbols(), (
            f"proxy for unknown symbol {sym}"
        )
        assert proxy
    if cls.publication_date:
        pd.Timestamp(cls.publication_date)
