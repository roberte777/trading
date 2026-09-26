from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from scipy.optimize import minimize

from trader.backtest.engine import BacktestConfig, Backtester
from trader.calendar import TradingCalendar
from trader.data.market_data import MarketData
from trader.strategies.risk_parity_erc import (
    UNIVERSE,
    EqualRiskContribution,
    erc_weights,
    risk_contributions,
)
from trader.strategy import Context

from .conftest import make_market_data

CAL = TradingCalendar.nyse(start="2000-01-01", end="2014-12-31")


def _market(close: pd.DataFrame) -> MarketData:
    frames = {f: close.copy() for f in ("open", "high", "low", "close")}
    frames["volume"] = pd.DataFrame(1e6, index=close.index, columns=close.columns)
    return MarketData(frames, rf=pd.Series(0.0, index=close.index))


def _ctx(close: pd.DataFrame) -> Context:
    data = _market(close)
    return Context(
        now=close.index[-1], data=data, positions={}, weights={}, equity=1.0, calendar=CAL
    )


def _random_walks(sessions, vols, seed=0, corr=None) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    k = len(vols)
    corr = np.eye(k) if corr is None else corr
    z = rng.multivariate_normal(np.zeros(k), corr, size=len(sessions))
    rets = z * np.asarray(vols) / np.sqrt(252)
    return pd.DataFrame(100 * np.exp(np.cumsum(rets, axis=0)), index=sessions)


def _scipy_erc(cov: np.ndarray) -> np.ndarray:
    """Reference solution: MRT's log-barrier problem with L-BFGS-B, as in the spec."""
    n = len(cov)
    s = cov / np.diag(cov).mean()

    def f(y):
        return 0.5 * y @ s @ y - np.log(y).sum() / n

    def g(y):
        return s @ y - 1.0 / (n * y)

    y0 = 1.0 / np.sqrt(np.diag(s))
    res = minimize(
        f, y0, jac=g, method="L-BFGS-B", bounds=[(1e-10, None)] * n, options={"ftol": 1e-15}
    )
    return res.x / res.x.sum()


# -- solver -------------------------------------------------------------------------


def test_erc_equal_risk_contributions_random_covariance():
    rng = np.random.default_rng(3)
    for n in (2, 5, 9):
        a = rng.normal(size=(n, n))
        corr = a @ a.T + 0.1 * np.eye(n)
        d = 1.0 / np.sqrt(np.diag(corr))
        corr = corr * np.outer(d, d)
        vols = rng.uniform(0.03, 0.35, n)
        cov = corr * np.outer(vols, vols) / 252  # daily scale
        x = erc_weights(cov)
        rc = risk_contributions(x, cov)
        assert x.sum() == pytest.approx(1.0, abs=1e-12)
        assert (x > 0).all()
        assert np.max(np.abs(rc / rc.mean() - 1.0)) < 1e-4
        np.testing.assert_allclose(x, _scipy_erc(cov), atol=1e-4)


def test_erc_constant_correlation_is_inverse_vol():
    # MRT: with equal correlations the ERC portfolio is the inverse-volatility portfolio.
    vols = np.array([0.10, 0.20, 0.30, 0.40])
    corr = np.full((4, 4), 0.5) + 0.5 * np.eye(4)
    x = erc_weights(corr * np.outer(vols, vols))
    np.testing.assert_allclose(x, [0.48, 0.24, 0.16, 0.12], atol=1e-10)


def test_erc_four_asset_block_correlation():
    # Correlated pair (0.8) plus a negatively correlated pair (-0.5): the correlated pair
    # is cut back and the hedged pair is scaled up relative to inverse-vol.
    vols = np.array([0.10, 0.20, 0.30, 0.40])
    corr = np.array(
        [[1.0, 0.8, 0.0, 0.0], [0.8, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, -0.5], [0.0, 0.0, -0.5, 1.0]]
    )
    x = erc_weights(corr * np.outer(vols, vols))
    np.testing.assert_allclose(x, [0.3836, 0.1918, 0.2426, 0.1820], atol=1e-4)


# -- strategy -----------------------------------------------------------------------


def test_two_assets_get_inverse_vol_weights_and_missing_symbols_get_none():
    # Only SPY and TLT have a full year of data; for two assets ERC is exactly
    # inverse-vol whatever the correlation. GLD has 100 sessions (not eligible); the
    # other six have no data at all.
    sessions = CAL.sessions_between("2004-01-02", "2005-12-30")
    close = pd.DataFrame(np.nan, index=sessions, columns=UNIVERSE)
    walks = _random_walks(sessions, [0.18, 0.12, 0.2], seed=1)
    close["SPY"], close["TLT"] = walks[0].to_numpy(), walks[1].to_numpy()
    close.loc[sessions[-100:], "GLD"] = walks[2].to_numpy()[-100:]

    w = EqualRiskContribution().target_weights(_ctx(close))

    rets = close[["SPY", "TLT"]].iloc[-253:].pct_change().iloc[1:]
    inv = 1.0 / rets.std(ddof=1)
    expected = inv / inv.sum()
    assert set(w) == {"SPY", "TLT"}
    assert w["SPY"] == pytest.approx(expected["SPY"], abs=1e-9)
    assert w["TLT"] == pytest.approx(expected["TLT"], abs=1e-9)
    assert w["TLT"] > w["SPY"]  # the lower-vol asset gets more capital
    assert sum(w.values()) == pytest.approx(1.0)


def test_asset_enters_after_cov_days_of_returns():
    sessions = CAL.sessions_between("2004-01-02", "2006-12-29")
    close = _random_walks(sessions, [0.15] * len(UNIVERSE), seed=2)
    close.columns = UNIVERSE
    first_dbc = 400
    close.iloc[:first_dbc, UNIVERSE.index("DBC")] = np.nan
    strat = EqualRiskContribution()
    # 251 returns of DBC: not yet eligible. 252 returns: eligible.
    before = strat.target_weights(_ctx(close.iloc[: first_dbc + 252]))
    after = strat.target_weights(_ctx(close.iloc[: first_dbc + 253]))
    assert "DBC" not in before and len(before) == 8
    assert "DBC" in after and len(after) == 9


def test_nine_asset_weights_have_equal_risk_contributions():
    sessions = CAL.sessions_between("2004-01-02", "2005-12-30")
    k = len(UNIVERSE)
    rng = np.random.default_rng(4)
    a = rng.normal(size=(k, k))
    corr = a @ a.T + np.eye(k)
    d = 1.0 / np.sqrt(np.diag(corr))
    close = _random_walks(sessions, rng.uniform(0.04, 0.3, k), seed=5, corr=corr * np.outer(d, d))
    close.columns = UNIVERSE

    w = EqualRiskContribution().target_weights(_ctx(close))

    x = np.array([w[s] for s in UNIVERSE])
    cov = close.iloc[-253:].pct_change().iloc[1:].cov().to_numpy()
    rc = risk_contributions(x, cov)
    assert np.max(np.abs(rc / rc.mean() - 1.0)) < 1e-4
    assert x.sum() == pytest.approx(1.0)


def test_weekly_returns_are_non_overlapping_five_session_returns():
    sessions = CAL.sessions_between("2004-01-02", "2005-12-30")
    close = pd.DataFrame(np.nan, index=sessions, columns=UNIVERSE)
    walks = _random_walks(sessions, [0.2, 0.1], seed=6)
    close["SPY"], close["IEF"] = walks[0].to_numpy(), walks[1].to_numpy()

    w = EqualRiskContribution(return_freq="weekly").target_weights(_ctx(close))

    px = close[["SPY", "IEF"]].iloc[-253:]
    weekly = px.iloc[[-1 - 5 * k for k in range(51)][::-1]].pct_change().iloc[1:]
    assert len(weekly) == 50
    inv = 1.0 / weekly.std(ddof=1)
    assert w["SPY"] == pytest.approx(inv["SPY"] / inv.sum(), abs=1e-9)


def test_backtest_never_holds_symbol_before_it_is_eligible():
    first = {"EEM": "2005-06-01", "GLD": "2006-03-15", "DBC": "2007-02-01"}
    data, cal = make_market_data(UNIVERSE, start="2003-01-02", end="2009-12-31", first_valid=first)
    strat = EqualRiskContribution()
    res = Backtester(strat, data, cal, BacktestConfig(start="2004-02-02")).run()
    for sym, day in first.items():
        pos = data.close.index.searchsorted(pd.Timestamp(day))
        eligible_from = data.close.index[pos + strat.params.cov_days]
        held = res.targets.get(sym, pd.Series(0.0, index=res.targets.index))
        assert (held.loc[: eligible_from - pd.Timedelta(days=1)] == 0).all(), sym
        assert (held.loc[eligible_from:] > 0).all(), sym
    np.testing.assert_allclose(res.targets.sum(axis=1), 1.0, atol=1e-9)
