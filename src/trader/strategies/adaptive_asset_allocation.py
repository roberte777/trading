"""Adaptive Asset Allocation (Butler, Philbrick, Gordillo & Varadi, 2012).

Each month-end, rank ten asset-class ETFs by their 6-month (126-session) total
return, keep the top five, and weight them with a long-only minimum-variance
portfolio. The covariance matrix follows the specification AllocateSmartly agreed
with the authors: 126-day correlations scaled by 20-day volatilities. The
portfolio is always fully invested; there is no cash or absolute-momentum filter.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from trader.data.proxies import proxies_for
from trader.strategy import Context, MonthEnd, Reference, Strategy, register

log = logging.getLogger(__name__)

#: The ten asset classes, in the order the authors list them.
UNIVERSE = [
    "SPY",  # US stocks
    "EZU",  # European stocks
    "EWJ",  # Japanese stocks
    "EEM",  # emerging-market stocks
    "VNQ",  # US REITs
    "RWX",  # international REITs
    "IEF",  # intermediate Treasuries
    "TLT",  # long Treasuries
    "DBC",  # commodities
    "GLD",  # gold
]

#: Extra sessions read before the window so a vendor gap on its first day can be
#: forward-filled instead of making the asset look too young.
_GAP_PAD = 5


def inverse_variance_weights(cov: np.ndarray) -> np.ndarray:
    """Weights proportional to 1 / variance (the solver fallback)."""
    var = np.maximum(np.diag(cov), 1e-18)
    inv = 1.0 / var
    return inv / inv.sum()


def min_variance_weights(cov: np.ndarray) -> np.ndarray:
    """Long-only, fully invested minimum-variance weights.

    Minimizes ``w' cov w`` subject to ``sum(w) = 1`` and ``0 <= w <= 1`` with SLSQP,
    starting from equal weights. The covariance is divided by its mean variance
    first: this leaves the minimizer unchanged but keeps the objective near 1, so
    SLSQP's absolute tolerance is meaningful for daily-return variances (~1e-4).
    Falls back to inverse-variance weights if the solver fails.
    """
    n = cov.shape[0]
    if n == 1:
        return np.ones(1)
    scale = float(np.mean(np.diag(cov)))
    if not np.isfinite(scale) or scale <= 0:
        return inverse_variance_weights(cov)
    s = cov / scale
    res = minimize(
        lambda w: float(w @ s @ w),
        np.full(n, 1.0 / n),
        jac=lambda w: 2.0 * (s @ w),
        method="SLSQP",
        bounds=[(0.0, 1.0)] * n,
        constraints=({"type": "eq", "fun": lambda w: float(w.sum() - 1.0)},),
        options={"ftol": 1e-12, "maxiter": 1000},
    )
    w = np.asarray(res.x, dtype=float)
    if not res.success or not np.isfinite(w).all():
        log.debug("min-variance solver failed (%s); using inverse-variance weights", res.message)
        return inverse_variance_weights(cov)
    w = np.clip(w, 0.0, None)
    return w / w.sum()


@register
class AdaptiveAssetAllocation(Strategy):
    name = "adaptive_asset_allocation"
    title = "Adaptive Asset Allocation (top 5, min-variance)"
    description = (
        "Butler, Philbrick, Gordillo & Varadi's AAA: each month-end, hold the 5 of 10 "
        "asset-class ETFs with the best 126-day total return, weighted by a long-only "
        "minimum-variance portfolio whose covariance combines 126-day correlations with "
        "20-day volatilities. Always fully invested; positions under 2% are dropped."
    )
    references = (
        Reference(
            "Butler, A., Philbrick, M., Gordillo, R. & Varadi, D. (2012), Adaptive Asset "
            "Allocation: A Primer, SSRN 2328254 (dated 2012-05-31; GestaltU, May 2012)",
            "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2328254",
        ),
        Reference(
            "Butler, A., Philbrick, M. & Gordillo, R. (2015), Adaptive Asset Allocation: "
            "A Primer (revised whitepaper), ReSolve Asset Management",
            "https://www.investresolve.com/inc/uploads/pdf/Adaptive-Asset-Allocation-Whitepaper.pdf",
        ),
        Reference(
            "AllocateSmartly, Adam Butler / GestaltU: Adaptive Asset Allocation "
            "(rules agreed with the authors)",
            "https://allocatesmartly.com/adam-butler-gestaltu-adaptive-asset-allocation/",
        ),
    )
    publication_date = "2012-05-01"
    proxies = proxies_for(UNIVERSE)

    @dataclass(frozen=True)
    class Params:
        momentum_days: int = 126
        top_n: int = 5
        vol_days: int = 20
        corr_days: int = 126
        min_weight: float = 0.02

    param_grid = {
        "momentum_days": [63, 252],
        "top_n": [3, 4],
        "corr_days": [63, 252],
    }

    def universe(self) -> list[str]:
        return list(UNIVERSE)

    def _closes_needed(self) -> int:
        """Closes an asset needs: ``corr_days + 1`` returns and ``momentum_days + 1`` closes."""
        p = self.params
        return max(p.momentum_days + 1, max(p.corr_days, p.vol_days) + 2)

    def warmup(self) -> int:
        return self._closes_needed()

    def schedule(self):
        return MonthEnd()

    def target_weights(self, ctx: Context):
        p = self.params
        need = self._closes_needed()
        raw = ctx.history("close", need + _GAP_PAD)[UNIVERSE]
        if len(raw) < need:
            return {}
        # Forward-fill interior vendor gaps (e.g. GC=F holidays); leading NaNs before
        # an asset's first bar stay NaN and make it ineligible.
        window = raw.ffill().iloc[-need:]
        today = raw.iloc[-1]
        eligible = [s for s in UNIVERSE if np.isfinite(today[s]) and window[s].notna().all()]
        if not eligible:
            return {}

        px = window[eligible]
        momentum = px.iloc[-1] / px.iloc[-1 - p.momentum_days] - 1.0
        # Stable sort: ties keep universe order, so the ranking is deterministic.
        ranked = momentum.sort_values(ascending=False, kind="mergesort")
        chosen = list(ranked.index[: p.top_n])

        rets = px[chosen].pct_change(fill_method=None).iloc[1:]
        weights = self._weights(rets, p)
        return {s: float(w) for s, w in zip(chosen, weights, strict=True) if w > 0}

    @staticmethod
    def _weights(rets: pd.DataFrame, p) -> np.ndarray:
        n = rets.shape[1]
        if n == 1:
            return np.ones(1)
        corr = rets.iloc[-p.corr_days :].corr().to_numpy()
        corr = np.nan_to_num(corr, nan=0.0)
        np.fill_diagonal(corr, 1.0)
        vol = rets.iloc[-p.vol_days :].std(ddof=1).to_numpy()
        vol = np.nan_to_num(vol, nan=0.0)
        cov = np.outer(vol, vol) * corr
        w = min_variance_weights(cov)
        # Drop tiny positions and hand their weight to the rest.
        keep = w >= p.min_weight
        if keep.any():
            w = np.where(keep, w, 0.0)
        return w / w.sum()
