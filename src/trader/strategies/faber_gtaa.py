"""Faber GTAA-5: five equal asset-class sleeves, each timed with a 10-month SMA.

Faber (2007/2013) holds 20% in each of US large caps, foreign developed equities,
US 10-year Treasuries, commodities (GSCI) and REITs. At every month end each
sleeve is checked on its own: if the month-end total-return price is above its
10-month simple moving average the sleeve is held, otherwise its 20% sits in
90-day T-bills (BIL here) until the next month end.
"""

from __future__ import annotations

from dataclasses import dataclass

from trader.data.proxies import proxies_for
from trader.indicators import month_end
from trader.strategy import Context, MonthEnd, Reference, Strategy, register

CASH = "BIL"
#: Commodity ETFs the ``commodity`` parameter chooses between (GSG tracks the GSCI).
COMMODITY_CHOICES = ("GSG", "DBC")
#: Upper bound on NYSE sessions in one calendar month.
_MAX_SESSIONS_PER_MONTH = 23


@register
class FaberGTAA(Strategy):
    name = "faber_gtaa"
    title = "Faber GTAA-5 (10-month SMA timing)"
    description = (
        "Five asset classes (SPY, EFA, IEF, GSCI commodities, VNQ) at 20% each. At each "
        "month end a sleeve is held only if its month-end total-return price is above its "
        "10-month simple moving average; otherwise that 20% moves to T-bills (BIL)."
    )
    references = (
        Reference(
            "Faber, M.T. (2007), A Quantitative Approach to Tactical Asset Allocation, "
            "Journal of Wealth Management 9(4), 69-79, doi:10.3905/jwm.2007.674809 "
            "(SSRN 962461, posted 2007-02-11)",
            "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=962461",
        ),
        Reference(
            "Faber, M.T. (2013), A Quantitative Approach to Tactical Asset Allocation, "
            "February 2013 update",
            "https://mebfaber.com/wp-content/uploads/2016/05/SSRN-id962461.pdf",
        ),
        Reference(
            "Faber, M. (2018), A Quantitative Approach to Tactical Asset Allocation Revisited "
            "10 Years Later, Journal of Portfolio Management 44(2), 156-167",
            "https://doi.org/10.3905/jpm.2018.44.2.156",
        ),
    )
    publication_date = "2007-02-11"
    # DBC is listed even though the default universe trades GSG: see ``signal_symbols``.
    proxies = proxies_for(["SPY", "EFA", "IEF", *COMMODITY_CHOICES, "VNQ", CASH])

    @dataclass(frozen=True)
    class Params:
        sma_months: int = 10
        commodity: str = "GSG"

    param_grid = {"sma_months": [6, 8, 12], "commodity": ["DBC"]}

    def __init__(self, **params) -> None:
        super().__init__(**params)
        if self.params.sma_months < 1:
            raise ValueError("sma_months must be >= 1")
        if not self.params.commodity or self.params.commodity == CASH:
            raise ValueError(f"invalid commodity ETF {self.params.commodity!r}")

    def sleeves(self) -> list[str]:
        """The five timed sleeves, each worth 1/5 of equity."""
        return ["SPY", "EFA", "IEF", self.params.commodity, "VNQ"]

    def universe(self) -> list[str]:
        return [*self.sleeves(), CASH]

    def signal_symbols(self) -> list[str]:
        # Never traded. Loading the other commodity ETF lets the robustness suite run
        # the `commodity` variants on the data panel it loads once for the base params.
        return [c for c in COMMODITY_CHOICES if c != self.params.commodity]

    def warmup(self) -> int:
        return self.params.sma_months * _MAX_SESSIONS_PER_MONTH + 5

    def schedule(self):
        return MonthEnd()

    def target_weights(self, ctx: Context):
        n = self.params.sma_months
        sleeves = self.sleeves()
        # Enough sessions for n full month groups; each earlier month's last session
        # falls inside a contiguous window, so its row is the true month-end close.
        hist = ctx.history("close", (n + 2) * _MAX_SESSIONS_PER_MONTH)[sleeves]
        # Last close of each month; the current (latest) session stands in for this month.
        monthly = month_end(hist).iloc[-n:]
        per_sleeve = 1.0 / len(sleeves)
        weights: dict[str, float] = {}
        for sym in sleeves:
            px = monthly[sym]
            # Eligible only with n month-end closes and a price today.
            if len(px) < n or px.isna().any() or not ctx.is_tradable(sym):
                continue
            if px.iloc[-1] > px.mean():  # strict ">" as in the paper
                weights[sym] = per_sleeve
        cash = 1.0 - per_sleeve * len(weights)
        if cash > 1e-9 and ctx.is_tradable(CASH):
            weights[CASH] = cash
        return weights
