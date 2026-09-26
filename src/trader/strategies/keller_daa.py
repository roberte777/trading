"""Defensive Asset Allocation (DAA-G12), Keller & Keuning (2018).

Relative momentum across 12 risky asset classes, with crash protection driven
only by a two-asset "canary" universe {VWO, BND}. Each canary with non-positive
13612W momentum moves half of the portfolio into the single best of three
bond "cash" assets. The risky assets themselves are not trend-filtered.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from trader.data.proxies import proxies_for
from trader.indicators import momentum_13612w, month_end
from trader.strategy import Context, MonthEnd, Reference, Strategy, register

RISKY = ("SPY", "IWM", "QQQ", "VGK", "EWJ", "VWO", "VNQ", "GSG", "GLD", "TLT", "HYG", "LQD")
CASH = ("SHY", "IEF", "LQD")
CANARY = ("VWO", "BND")

#: 13 month-end closes (p0..p12) plus slack for the partial first month and gaps.
HISTORY_SESSIONS = 320
#: Carry a close over at most this many missing sessions (e.g. GC=F has no bar on
#: some day-after-Thanksgiving half days, which are month-ends).
FFILL_LIMIT = 5


@register
class DefensiveAssetAllocation(Strategy):
    name = "keller_daa"
    title = "Defensive Asset Allocation (DAA-G12)"
    description = (
        "Keller & Keuning's DAA-G12: each month rank 12 risky ETFs by 13612W momentum "
        "and hold the top 6 at 1/6 each. The canary pair VWO/BND sets the cash fraction: "
        "one canary with 13612W <= 0 moves 50% into the best of SHY/IEF/LQD, both move 100%."
    )
    references = (
        Reference(
            "Keller, W.J., Keuning, J.W. (2018). Breadth Momentum and the Canary Universe: "
            "Defensive Asset Allocation (DAA). SSRN Working Paper 3212862",
            "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3212862",
        ),
        Reference(
            "Keuning, J.W. (2018). Announcing Defensive Asset Allocation. TrendXplorer blog",
            "https://indexswingtrader.blogspot.com/2018/07/announcing-defensive-asset-allocation.html",
        ),
        Reference(
            "CXO Advisory (2018). Multi-class Momentum Portfolio with Canary Crash Protection",
            "https://www.cxoadvisory.com/strategic-allocation/multi-class-momentum-portfolio-with-canary-crash-protection/",
        ),
        Reference(
            "Keller, W.J., Keuning, J.W. (2023). Dual and Canary Momentum with Rising Yields/"
            "Inflation: Hybrid Asset Allocation (HAA). SSRN Working Paper 4346906",
            "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4346906",
        ),
    )
    publication_date = "2018-08-01"
    proxies = proxies_for([*RISKY, *CASH, *CANARY])

    @dataclass(frozen=True)
    class Params:
        #: T: number of risky assets held when both canaries are good.
        top_n: int = 6
        #: B: number of bad canaries that moves the portfolio fully into cash.
        breadth: int = 2

    param_grid = {"top_n": [4, 5], "breadth": [1]}

    def universe(self) -> list[str]:
        return list(dict.fromkeys([*RISKY, *CASH]))

    def signal_symbols(self) -> list[str]:
        return [s for s in CANARY if s not in self.universe()]

    def warmup(self) -> int:
        # 13 month-end closes: up to one partial month plus 12 full months.
        return 13 * 21

    def schedule(self):
        return MonthEnd()

    # -- signal ------------------------------------------------------------------------
    def momentum(self, ctx: Context) -> pd.Series:
        """13612W per symbol on month-end closes; NaN where the symbol is not eligible."""
        close = ctx.history("close", HISTORY_SESSIONS)[self.data_symbols()]
        filled = close.ffill(limit=FFILL_LIMIT)
        mom = momentum_13612w(month_end(filled))
        # Never rank a symbol without a (recent) price at this close.
        return mom.where(filled.iloc[-1].notna())

    def cash_fraction(self, bad: int) -> float:
        """CF = min(1, b/B), rounded down to a multiple of 1/T ("easy trading")."""
        top_n = self.params.top_n
        cf = min(1.0, bad / self.params.breadth)
        return math.floor(cf * top_n + 1e-9) / top_n

    def target_weights(self, ctx: Context):
        top_n = self.params.top_n
        mom = self.momentum(ctx)

        # A canary without a momentum reading counts as bad (defensive default).
        bad = sum(1 for s in CANARY if not (mom.get(s, math.nan) > 0))
        cf = self.cash_fraction(bad)
        n_risky = round((1.0 - cf) * top_n)

        risky = mom.reindex(list(RISKY)).dropna()
        # Stable sort: ties keep universe order, so decisions are deterministic.
        ranked = risky.sort_values(ascending=False, kind="mergesort")
        chosen = list(ranked.index[:n_risky])

        weights: dict[str, float] = {s: 1.0 / top_n for s in chosen}
        cash_weight = 1.0 - len(chosen) / top_n
        cash = mom.reindex(list(CASH)).dropna()
        if cash_weight > 1e-9 and not cash.empty:
            best = cash.sort_values(ascending=False, kind="mergesort").index[0]
            weights[best] = weights.get(best, 0.0) + cash_weight
        return weights
