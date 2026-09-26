"""Equal Risk Contribution (ERC) multi-asset portfolio.

Maillard, Roncalli & Teiletche (2010). At each month-end, estimate the covariance
of the eligible assets from the last year of daily returns and hold the long-only,
fully invested portfolio in which every asset contributes the same amount to
portfolio variance: ``x_i (Σx)_i`` is equal for all ``i``.

The weights come from the convex problem MRT give (their §2, eq. 7)::

    min_y  ½ yᵀΣy − (1/n) Σ ln y_i,   y > 0,   then  x = y / Σy

solved with a damped Newton method. The solution is checked for equal risk
contributions before it is used.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from trader.data.proxies import proxies_for
from trader.strategy import Context, MonthEnd, Reference, Strategy, register

UNIVERSE = ["SPY", "EFA", "EEM", "IEF", "TLT", "TIP", "GLD", "DBC", "VNQ"]

#: A symbol whose last valid close is older than this many sessions is not traded.
#: Only matters for proxy series with single missing days (e.g. GC=F on the day
#: after Thanksgiving); the missing day is forward-filled for the covariance.
MAX_STALE_SESSIONS = 5

#: Maximum relative dispersion of risk contributions accepted from the solver.
RC_TOLERANCE = 1e-6


class ERCSolverError(RuntimeError):
    pass


def risk_contributions(weights: np.ndarray, cov: np.ndarray) -> np.ndarray:
    """``x_i (Σx)_i``: each asset's contribution to portfolio variance."""
    return weights * (cov @ weights)


def erc_weights(cov: np.ndarray, max_iter: int = 100) -> np.ndarray:
    """Long-only, fully invested equal-risk-contribution weights for covariance ``cov``.

    Minimises ``f(y) = ½ yᵀSy − b Σ ln y_i`` with ``b = 1/n`` by Newton's method, then
    normalises ``x = y / Σy``. ``S`` is ``cov`` divided by its mean variance; ERC
    weights do not depend on the scale of the covariance, and the rescaling keeps the
    problem well conditioned. The objective is strictly convex (the log barrier makes
    the Hessian ``S + diag(b / y²)`` positive definite), so the minimiser is unique.

    Far from the optimum, steps are damped by an Armijo backtracking line search that
    also keeps ``y > 0``. Once the Newton decrement ``λ² = −∇fᵀΔy`` is small, the
    expected decrease in ``f`` falls below floating-point noise, so full Newton steps
    are taken (quadratic convergence) until ``λ²`` is negligible.
    """
    cov = np.asarray(cov, dtype=float)
    n = cov.shape[0]
    if cov.shape != (n, n) or n == 0:
        raise ValueError(f"covariance must be square and non-empty, got {cov.shape}")
    if n == 1:
        return np.ones(1)
    variances = np.diag(cov)
    if not np.all(np.isfinite(cov)) or np.any(variances <= 0):
        raise ValueError("covariance must be finite with positive variances")
    S = cov / variances.mean()
    b = 1.0 / n

    def objective(y: np.ndarray) -> float:
        return 0.5 * float(y @ S @ y) - b * float(np.log(y).sum())

    # Start from inverse-volatility weights, scaled so that yᵀSy = n·b = 1, which
    # holds at the optimum (sum over i of y_i (Sy)_i = sum of b).
    y = 1.0 / np.sqrt(np.diag(S))
    y /= np.sqrt(float(y @ S @ y))
    f = objective(y)
    for _ in range(max_iter):
        grad = S @ y - b / y
        hess = S + np.diag(b / y**2)
        step = np.linalg.solve(hess, -grad)
        decrement = -float(grad @ step)
        if decrement < 1e-24:
            break
        t = 1.0
        while True:
            trial = y + t * step
            if np.all(trial > 0):
                if decrement < 1e-10:
                    break
                f_trial = objective(trial)
                if f_trial <= f - 1e-4 * t * decrement:
                    break
            t *= 0.5
            if t < 1e-12:
                raise ERCSolverError("line search failed")
        y = trial
        f = objective(y)
    x = y / y.sum()
    rc = risk_contributions(x, S)
    dispersion = float(np.max(np.abs(rc / rc.mean() - 1.0)))
    if not np.all(x > 0) or dispersion > RC_TOLERANCE:
        raise ERCSolverError(f"risk contributions not equal (max relative gap {dispersion:.2e})")
    return x


@register
class EqualRiskContribution(Strategy):
    name = "risk_parity_erc"
    title = "Equal risk contribution (MRT 2010)"
    description = (
        "Long-only, fully invested equal-risk-contribution portfolio over nine asset-class "
        "ETFs (US, developed and emerging equity; intermediate, long and inflation-linked "
        "Treasuries; gold; commodities; US REITs). Each month-end, the covariance of the "
        "last 252 daily returns is estimated and weights are set so every asset "
        "contributes equally to portfolio variance. Assets join once they have 252 daily "
        "returns. Unlevered, no cash leg."
    )
    references = (
        Reference(
            "Maillard, S., Roncalli, T., Teiletche, J. (2010), The Properties of Equally "
            "Weighted Risk Contribution Portfolios, Journal of Portfolio Management 36(4), 60-70",
            "https://doi.org/10.3905/jpm.2010.36.4.060",
        ),
        Reference(
            "Maillard, Roncalli & Teiletche, working paper (first version June 2008)",
            "http://www.thierry-roncalli.com/download/erc.pdf",
        ),
        Reference(
            "Asness, C., Frazzini, A., Pedersen, L. H. (2012), Leverage Aversion and Risk "
            "Parity, Financial Analysts Journal 68(1), 47-59",
            "https://doi.org/10.2469/faj.v68.n1.1",
        ),
        Reference(
            "Griveau-Billion, T., Richard, J.-C., Roncalli, T. (2013), A Fast Algorithm for "
            "Computing High-dimensional Risk Parity Portfolios",
            "https://arxiv.org/abs/1311.4057",
        ),
        Reference(
            "Chaves, D., Hsu, J., Li, F., Shakernia, O. (2011), Risk Parity Portfolio vs. "
            "Other Asset Allocation Heuristic Portfolios, Journal of Investing 20(1), 108-118",
            "https://doi.org/10.3905/joi.2011.20.1.108",
        ),
        Reference(
            "Anderson, R., Bianchi, S., Goldberg, L. (2012), Will My Risk Parity Strategy "
            "Outperform?, Financial Analysts Journal 68(6), 75-93",
            "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2101898",
        ),
    )
    publication_date = "2008-06-01"
    proxies = proxies_for(UNIVERSE)

    @dataclass(frozen=True)
    class Params:
        #: Covariance window in sessions (MRT §4.2: rolling one-year window).
        cov_days: int = 252
        #: ``daily`` (MRT) or ``weekly`` (non-overlapping 5-session returns).
        return_freq: str = "daily"

    param_grid = {"cov_days": [126, 504], "return_freq": ["weekly"]}

    def __init__(self, **params) -> None:
        super().__init__(**params)
        if self.params.return_freq not in ("daily", "weekly"):
            raise ValueError(
                f"return_freq must be 'daily' or 'weekly', got {self.params.return_freq!r}"
            )
        if self.params.cov_days < 10:
            raise ValueError("cov_days must be at least 10")

    def universe(self) -> list[str]:
        return list(UNIVERSE)

    def warmup(self) -> int:
        return self.params.cov_days + MAX_STALE_SESSIONS + 1

    def schedule(self):
        return MonthEnd()

    def returns_window(self, ctx: Context):
        """Returns used for the covariance, restricted to eligible symbols.

        A symbol is eligible when it has a close in each of the last ``cov_days + 1``
        sessions (after forward-filling single missing days) and a real close within
        the last ``MAX_STALE_SESSIONS`` sessions.
        """
        n = self.params.cov_days
        raw = ctx.history("close", n + 1 + MAX_STALE_SESSIONS)[self.universe()]
        if len(raw) < n + 1:
            return None
        prices = raw.ffill().iloc[-(n + 1) :]
        recent = raw.iloc[-MAX_STALE_SESSIONS:].notna().any()
        eligible = [s for s in prices.columns if prices[s].notna().all() and recent[s]]
        if not eligible:
            return None
        prices = prices[eligible]
        if self.params.return_freq == "weekly":
            # Non-overlapping 5-session returns ending at the current close.
            prices = prices.iloc[::-1].iloc[::5].iloc[::-1]
        rets = prices.pct_change().iloc[1:]
        # A constant series has no risk to equalise; it cannot enter the solver.
        rets = rets.loc[:, rets.std(ddof=1) > 0]
        return rets if rets.shape[1] else None

    def target_weights(self, ctx: Context):
        rets = self.returns_window(ctx)
        if rets is None:
            return {}
        if rets.shape[1] == 1:
            return {rets.columns[0]: 1.0}
        cov = np.cov(rets.to_numpy(), rowvar=False, ddof=1)
        x = erc_weights(cov)
        return {s: float(w) for s, w in zip(rets.columns, x, strict=True)}
