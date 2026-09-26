from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from trader.analytics.metrics import drawdown, performance_metrics, yearly_returns
from trader.analytics.stats import (
    bootstrap_ci,
    deflated_sharpe,
    expected_max_sharpe,
    probabilistic_sharpe,
)


def _series(values, start="2020-01-01"):
    return pd.Series(values, index=pd.bdate_range(start, periods=len(values)))


def test_cagr_and_drawdown_on_known_path():
    r = _series([0.0] + [0.001] * 503)
    m = performance_metrics(r)
    assert m["cagr"] == pytest.approx((1.001**503) ** (252 / 504) - 1, rel=1e-9)
    assert m["max_drawdown"] == 0.0
    dd = drawdown(_series([0.1, -0.5, 0.2]))
    assert dd.min() == pytest.approx(-0.5)


def test_sharpe_uses_excess_returns():
    rng = np.random.default_rng(1)
    r = _series(rng.normal(0.0005, 0.01, 2520))
    rf = _series([0.0002] * 2520)
    m0, m1 = performance_metrics(r), performance_metrics(r, rf)
    assert m1["sharpe"] < m0["sharpe"]
    ex = r - rf
    assert m1["sharpe"] == pytest.approx(ex.mean() / ex.std() * math.sqrt(252))


def test_beta_of_benchmark_is_one():
    rng = np.random.default_rng(2)
    b = _series(rng.normal(0.0004, 0.01, 1000))
    m = performance_metrics(b, benchmark=b)
    assert m["beta"] == pytest.approx(1.0)
    assert m["alpha"] == pytest.approx(0.0, abs=1e-12)


def test_yearly_returns():
    r = pd.Series([0.1, 0.1], index=pd.to_datetime(["2020-06-01", "2021-06-01"]))
    y = yearly_returns(r)
    assert y.loc[2020] == pytest.approx(0.1)


def test_psr_and_dsr_behave():
    rng = np.random.default_rng(3)
    good = _series(rng.normal(0.0008, 0.01, 2520))
    noise = _series(rng.normal(0.0, 0.01, 2520))
    assert probabilistic_sharpe(good) > 0.95
    assert 0.02 < probabilistic_sharpe(noise) < 0.98
    assert expected_max_sharpe(1, 0.01) == 0.0
    assert expected_max_sharpe(100, 0.0004) > expected_max_sharpe(10, 0.0004) > 0
    d = deflated_sharpe(good, [0.02, 0.05, 0.08, 0.01, 0.03] * 10)
    assert d["dsr"] < probabilistic_sharpe(good)


def test_bootstrap_ci_brackets_point_estimate():
    rng = np.random.default_rng(4)
    r = _series(rng.normal(0.0005, 0.01, 1500))
    ci = bootstrap_ci(r, n_boot=300, benchmark=r * 0.5)
    point = r.mean() / r.std() * math.sqrt(252)
    assert ci["sharpe"]["lo"] < point < ci["sharpe"]["hi"]
    assert ci["max_drawdown"]["hi"] <= 0
    assert 0 <= ci["sharpe_minus_benchmark"]["p_better"] <= 1
