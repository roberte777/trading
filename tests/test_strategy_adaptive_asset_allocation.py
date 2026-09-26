"""Hand-built checks for Adaptive Asset Allocation.

Daily returns are ``mu + a * h`` where ``h`` is one of three period-4 sign patterns
that are zero-mean and mutually orthogonal over any 4-session window. Over the
8-session correlation window the sample correlations are therefore exactly zero,
the covariance is diagonal with variance proportional to ``a**2``, and the
long-only minimum-variance weights are proportional to ``1 / a**2``.
"""

from __future__ import annotations

import itertools

import numpy as np
import pandas as pd
import pytest

from trader.calendar import TradingCalendar
from trader.data.market_data import FIELDS, MarketData
from trader.strategies.adaptive_asset_allocation import (
    UNIVERSE,
    AdaptiveAssetAllocation,
    min_variance_weights,
)
from trader.strategy import Context

PATTERNS = [
    np.array([1.0, 1.0, -1.0, -1.0]),
    np.array([1.0, -1.0, 1.0, -1.0]),
    np.array([1.0, -1.0, -1.0, 1.0]),
]
SMALL = {"momentum_days": 8, "corr_days": 8, "vol_days": 8, "top_n": 3}
N = 40


def _context(specs: dict[str, tuple[float, float, int]], first: dict[str, int] | None = None):
    """Build a context at the last session.

    ``specs[sym] = (mu, a, pattern)``; symbols not in ``specs`` have no data at all.
    ``first[sym] = k`` blanks out the first ``k`` sessions of ``sym``.
    """
    cal = TradingCalendar.nyse(start="2010-01-01", end="2011-12-31")
    sessions = cal.sessions_between("2010-01-04", "2011-12-31")[:N]
    close = pd.DataFrame(np.nan, index=sessions, columns=UNIVERSE)
    t = np.arange(N)
    for sym, (mu, a, k) in specs.items():
        r = mu + a * PATTERNS[k][t % 4]
        r[0] = 0.0
        close[sym] = 100.0 * np.cumprod(1.0 + r)
    for sym, k in (first or {}).items():
        close.iloc[:k, close.columns.get_loc(sym)] = np.nan
    frames = {f: close.copy() for f in FIELDS}
    frames["volume"] = close.notna().astype(float) * 1e6
    data = MarketData(frames)
    return Context(
        now=sessions[-1],
        data=data.upto(N - 1),
        positions={},
        weights={},
        equity=100_000.0,
        calendar=cal,
    )


def _losers() -> dict[str, tuple[float, float, int]]:
    return {s: (-0.003, 0.004, 0) for s in ("SPY", "EZU", "EWJ", "EEM", "VNQ")}


def test_top_momentum_assets_get_min_variance_weights():
    # Three rising assets with vols in ratio 1 : 2 : 4 -> weights 16 : 4 : 1.
    specs = {
        **_losers(),
        "IEF": (0.004, 0.005, 0),
        "TLT": (0.004, 0.010, 1),
        "DBC": (0.004, 0.020, 2),
    }
    w = AdaptiveAssetAllocation(**SMALL).target_weights(_context(specs))
    assert set(w) == {"IEF", "TLT", "DBC"}
    assert w["IEF"] == pytest.approx(16 / 21, abs=1e-5)
    assert w["TLT"] == pytest.approx(4 / 21, abs=1e-5)
    assert w["DBC"] == pytest.approx(1 / 21, abs=1e-5)
    assert sum(w.values()) == pytest.approx(1.0)


def test_positions_below_min_weight_are_dropped_and_renormalized():
    # Vol ratio 1 : 2 : 10 -> raw weights 100 : 25 : 1; DBC's 0.8% is under 2%.
    specs = {
        **_losers(),
        "IEF": (0.004, 0.005, 0),
        "TLT": (0.004, 0.010, 1),
        "DBC": (0.004, 0.050, 2),
    }
    w = AdaptiveAssetAllocation(**SMALL).target_weights(_context(specs))
    assert set(w) == {"IEF", "TLT"}
    assert w["IEF"] == pytest.approx(0.8, abs=1e-5)
    assert w["TLT"] == pytest.approx(0.2, abs=1e-5)


def test_assets_without_enough_history_get_no_weight():
    # GLD and RWX have the best momentum but only 6 sessions of data (10 needed);
    # EWJ has no data at all. Only IEF and TLT are eligible, so top 3 holds two.
    specs = {
        "SPY": (-0.003, 0.004, 0),
        "IEF": (0.004, 0.005, 0),
        "TLT": (0.004, 0.010, 1),
        "GLD": (0.05, 0.005, 2),
        "RWX": (0.05, 0.005, 1),
    }
    first = {"SPY": N - 3, "GLD": N - 6, "RWX": N - 6}
    w = AdaptiveAssetAllocation(**SMALL).target_weights(_context(specs, first))
    assert set(w) == {"IEF", "TLT"}
    assert w["IEF"] == pytest.approx(0.8, abs=1e-5)
    assert w["TLT"] == pytest.approx(0.2, abs=1e-5)


def test_no_eligible_assets_means_no_positions():
    w = AdaptiveAssetAllocation(**SMALL).target_weights(
        _context({"IEF": (0.004, 0.005, 0)}, {"IEF": N - 3})
    )
    assert w == {}


def _exact_long_only_min_variance(cov: np.ndarray) -> np.ndarray:
    """Oracle: best feasible unconstrained min-var over every support set (KKT)."""
    n = cov.shape[0]
    best, best_var = None, np.inf
    for k in range(1, n + 1):
        for support in itertools.combinations(range(n), k):
            idx = list(support)
            x = np.linalg.solve(cov[np.ix_(idx, idx)], np.ones(k))
            x = x / x.sum()
            if (x < -1e-12).any():
                continue
            w = np.zeros(n)
            w[idx] = x
            var = w @ cov @ w
            if var < best_var:
                best, best_var = w, var
    return best


@pytest.mark.parametrize("seed", range(5))
def test_min_variance_solver_matches_exact_solution(seed):
    rng = np.random.default_rng(seed)
    # Realistic daily-return scale: vols 0.3%-2%, random correlations.
    vol = rng.uniform(0.003, 0.02, 5)
    a = rng.normal(size=(5, 5))
    c = a @ a.T + 0.5 * np.eye(5)
    d = np.sqrt(np.diag(c))
    corr = c / np.outer(d, d)
    cov = np.outer(vol, vol) * corr
    w = min_variance_weights(cov)
    exact = _exact_long_only_min_variance(cov)
    assert w.sum() == pytest.approx(1.0)
    assert (w >= 0).all()
    assert w @ cov @ w == pytest.approx(exact @ cov @ exact, rel=1e-6)
    np.testing.assert_allclose(w, exact, atol=1e-4)


def test_min_variance_corner_solution():
    # Highly correlated pair: unconstrained min-var would short the riskier asset.
    vol = np.array([0.01, 0.02])
    corr = np.array([[1.0, 0.9], [0.9, 1.0]])
    w = min_variance_weights(np.outer(vol, vol) * corr)
    np.testing.assert_allclose(w, [1.0, 0.0], atol=1e-6)
