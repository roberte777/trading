"""Risk parity with a 10-month trend filter (Clare, Seaton, Smith & Thomas 2016).

At each month-end every eligible risky asset gets an inverse-volatility weight
(Asness, Frazzini & Pedersen 2012). Any asset whose month-end close is at or below
its 10-month SMA of month-end closes (Faber 2007) has its weight moved to T-bills.
The strategy is fully invested and unlevered.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from trader.data.proxies import proxies_for
from trader.indicators import month_end
from trader.strategy import Context, MonthEnd, Reference, Strategy, register

RISKY = ("SPY", "EFA", "EEM", "IEF", "DBC", "VNQ")
CASH = "BIL"
#: Upper bound on NYSE sessions in a calendar month, used to size the history window.
_SESSIONS_PER_MONTH = 23


@register
class RiskParityTrend(Strategy):
    name = "risk_parity_trend"
    title = "Risk parity + 10-month trend filter (Clare et al. 2016)"
    description = (
        "Inverse-volatility (risk parity) weights over six global asset-class ETFs "
        "(SPY, EFA, EEM, IEF, DBC, VNQ) from the standard deviation of the last 12 "
        "monthly returns. An asset whose month-end close is at or below its 10-month "
        "SMA has its weight moved to T-bills (BIL). Rebalanced monthly, unlevered."
    )
    references = (
        Reference(
            "Clare, A., Seaton, J., Smith, P.N., Thomas, S. (2016), The trend is our friend: "
            "Risk parity, momentum and trend following in global asset allocation, Journal of "
            "Behavioral and Experimental Finance 9, 63-80 (SSRN 2126478, first posted 2012)",
            "https://doi.org/10.1016/j.jbef.2016.01.002",
        ),
        Reference(
            "Asness, C., Frazzini, A., Pedersen, L.H. (2012), Leverage Aversion and Risk Parity, "
            "Financial Analysts Journal 68(1), 47-59",
            "https://doi.org/10.2469/faj.v68.n1.1",
        ),
        Reference(
            "Faber, M. (2007), A Quantitative Approach to Tactical Asset Allocation, "
            "Journal of Wealth Management 9(4), 69-79",
            "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=962461",
        ),
    )
    publication_date = "2016-01-15"
    proxies = proxies_for([*RISKY, CASH])

    @dataclass(frozen=True)
    class Params:
        sma_months: int = 10
        vol_months: int = 12

    param_grid = {"sma_months": [6, 8, 12], "vol_months": [6, 36]}

    def universe(self) -> list[str]:
        return [*RISKY, CASH]

    def _months_needed(self) -> int:
        """Month-end closes an asset needs before it is eligible."""
        return max(self.params.vol_months, self.params.sma_months) + 1

    def warmup(self) -> int:
        return self._months_needed() * 22

    def schedule(self):
        return MonthEnd()

    def target_weights(self, ctx: Context):
        p = self.params
        need = self._months_needed()
        # Enough sessions to contain the last ``need`` month-end rows (the current,
        # possibly partial, month counts as the latest month-end).
        window = ctx.history("close", (need + 2) * _SESSIONS_PER_MONTH)[list(RISKY)]
        monthly = month_end(window.ffill()).iloc[-need:]

        inv_vol: dict[str, float] = {}
        in_trend: dict[str, bool] = {}
        for sym in RISKY:
            if not ctx.is_tradable(sym):
                continue
            px = monthly[sym]
            if len(px) < need or not np.isfinite(px.to_numpy()).all():
                continue
            sigma = float(px.pct_change().iloc[-p.vol_months :].std(ddof=1))
            if not np.isfinite(sigma) or sigma <= 0:
                continue
            inv_vol[sym] = 1.0 / sigma
            in_trend[sym] = float(px.iloc[-1]) > float(px.iloc[-p.sma_months :].mean())

        total = sum(inv_vol.values())
        weights = {s: v / total for s, v in inv_vol.items() if in_trend[s]} if total > 0 else {}
        cash = 1.0 - sum(weights.values())
        if cash > 1e-12 and ctx.is_tradable(CASH):
            weights[CASH] = cash
        return weights
