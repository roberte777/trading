"""Statistical checks against overfitting and luck.

* Probabilistic Sharpe Ratio — Bailey & López de Prado (2012), "The Sharpe Ratio
  Efficient Frontier", Journal of Risk 15(2).
* Deflated Sharpe Ratio — Bailey & López de Prado (2014), "The Deflated Sharpe
  Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality",
  Journal of Portfolio Management 40(5).
* Stationary bootstrap — Politis & Romano (1994), JASA 89(428), used for
  confidence intervals that respect volatility clustering / autocorrelation.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy import stats as sps

EULER_GAMMA = 0.5772156649015329
PERIODS = 252


def _moments(returns: pd.Series) -> tuple[float, float, float, int]:
    r = returns.dropna().to_numpy()
    n = len(r)
    sd = r.std(ddof=1)
    sr = r.mean() / sd if sd > 0 else 0.0
    skew = float(sps.skew(r, bias=False))
    kurt = float(sps.kurtosis(r, fisher=False, bias=False))  # non-excess
    return float(sr), skew, kurt, n


def probabilistic_sharpe(returns: pd.Series, sr_benchmark: float = 0.0) -> float:
    """P(true Sharpe > ``sr_benchmark``) given sample length, skew and kurtosis.

    ``sr_benchmark`` is in per-period (daily) units, as are all Sharpe ratios here.
    """
    sr, skew, kurt, n = _moments(returns)
    denom = 1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr**2
    if n < 3 or denom <= 0:
        return float("nan")
    z = (sr - sr_benchmark) * math.sqrt(n - 1) / math.sqrt(denom)
    return float(sps.norm.cdf(z))


def expected_max_sharpe(n_trials: int, var_sharpe: float) -> float:
    """Expected maximum of ``n_trials`` Sharpe estimates when the true Sharpe is zero."""
    if n_trials < 2 or var_sharpe <= 0:
        return 0.0
    a = sps.norm.ppf(1.0 - 1.0 / n_trials)
    b = sps.norm.ppf(1.0 - 1.0 / (n_trials * math.e))
    return math.sqrt(var_sharpe) * ((1.0 - EULER_GAMMA) * a + EULER_GAMMA * b)


def deflated_sharpe(
    returns: pd.Series, trial_sharpes: list[float], n_trials: int | None = None
) -> dict[str, float]:
    """DSR: PSR against the Sharpe you would expect from the best of N useless trials.

    ``trial_sharpes`` are the per-period Sharpe ratios of *every* configuration
    tried (all strategies and variants), which estimates their dispersion.
    """
    trials = np.asarray([s for s in trial_sharpes if np.isfinite(s)], dtype=float)
    n = n_trials or len(trials)
    var = float(trials.var(ddof=1)) if len(trials) > 1 else 0.0
    sr0 = expected_max_sharpe(n, var)
    return {
        "dsr": probabilistic_sharpe(returns, sr0),
        "sr0_annual": sr0 * math.sqrt(PERIODS),
        "n_trials": n,
    }


def stationary_bootstrap_indices(
    n: int, n_boot: int, mean_block: float, rng: np.random.Generator
) -> np.ndarray:
    p = 1.0 / mean_block
    idx = np.empty((n_boot, n), dtype=np.int64)
    idx[:, 0] = rng.integers(0, n, size=n_boot)
    jumps = rng.random((n_boot, n)) < p
    fresh = rng.integers(0, n, size=(n_boot, n))
    for t in range(1, n):
        idx[:, t] = np.where(jumps[:, t], fresh[:, t], (idx[:, t - 1] + 1) % n)
    return idx


def _boot_stats(r: np.ndarray, rf: np.ndarray) -> dict[str, np.ndarray]:
    ex = r - rf
    sd = ex.std(axis=1, ddof=1)
    sharpe = np.where(sd > 0, ex.mean(axis=1) / np.where(sd > 0, sd, 1.0), np.nan) * math.sqrt(
        PERIODS
    )
    growth = np.log1p(r).sum(axis=1)
    cagr = np.expm1(growth * PERIODS / r.shape[1])
    eq = np.exp(np.cumsum(np.log1p(r), axis=1))
    peak = np.maximum.accumulate(eq, axis=1)
    max_dd = (eq / peak - 1.0).min(axis=1)
    return {"sharpe": sharpe, "cagr": cagr, "max_drawdown": max_dd}


def bootstrap_ci(
    returns: pd.Series,
    rf: pd.Series | None = None,
    benchmark: pd.Series | None = None,
    n_boot: int = 1000,
    mean_block: float = 21.0,
    level: float = 0.90,
    seed: int = 7,
) -> dict[str, dict[str, float]]:
    """Stationary-bootstrap confidence intervals for Sharpe, CAGR and max drawdown.

    With a benchmark, also the paired Sharpe difference and the probability the
    strategy's Sharpe exceeds the benchmark's.
    """
    r_s = returns.dropna()
    r = r_s.to_numpy()
    rf_a = rf.reindex(r_s.index).fillna(0.0).to_numpy() if rf is not None else np.zeros_like(r)
    rng = np.random.default_rng(seed)
    idx = stationary_bootstrap_indices(len(r), n_boot, mean_block, rng)
    lo_q, hi_q = (1 - level) / 2, 1 - (1 - level) / 2
    s = _boot_stats(r[idx], rf_a[idx])
    out = {
        k: {
            "lo": float(np.nanquantile(v, lo_q)),
            "median": float(np.nanmedian(v)),
            "hi": float(np.nanquantile(v, hi_q)),
        }
        for k, v in s.items()
    }
    if benchmark is not None:
        b = benchmark.reindex(r_s.index).fillna(0.0).to_numpy()
        sb = _boot_stats(b[idx], rf_a[idx])
        diff = s["sharpe"] - sb["sharpe"]
        out["sharpe_minus_benchmark"] = {
            "lo": float(np.nanquantile(diff, lo_q)),
            "median": float(np.nanmedian(diff)),
            "hi": float(np.nanquantile(diff, hi_q)),
            "p_better": float(np.nanmean(diff > 0)),
        }
    return out
