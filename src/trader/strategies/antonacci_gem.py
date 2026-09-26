"""Gary Antonacci's Global Equities Momentum (GEM), the canonical dual-momentum model.

At each month-end, with R(x) the total return over the last ``lookback_months``
month-ends (13 month-end observations for 12 months, no skip month):

* Book / author's-site ordering (``abs_on="us"``, default): if R(SPY) > R(BIL),
  hold 100% of whichever of SPY or VEU has the higher R; otherwise hold 100% of
  the fallback (AGG).
* Risk Premia Harvesting ordering (``abs_on="winner"``): pick the winner of SPY
  vs VEU by R first, hold it if R(winner) > R(BIL), otherwise the fallback.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from trader.data.proxies import proxies_for
from trader.indicators import month_end, trailing_return
from trader.strategy import Context, MonthEnd, Reference, Strategy, register

US_EQUITY = "SPY"
INTL_EQUITY = "VEU"
BONDS = "AGG"
TBILLS = "BIL"
ABS_MODES = ("us", "winner")
#: Upper bound on NYSE sessions in one calendar month.
_MAX_SESSIONS_PER_MONTH = 23


@register
class GlobalEquitiesMomentum(Strategy):
    name = "antonacci_gem"
    title = "Antonacci Global Equities Momentum (dual momentum)"
    description = (
        "Monthly dual momentum across US stocks (SPY), ACWI ex-US stocks (VEU) and US "
        "aggregate bonds (AGG). If the S&P 500's 12-month total return beats T-bills, "
        "hold whichever of SPY and VEU has the higher 12-month return; otherwise hold "
        "AGG. Always 100% in a single asset."
    )
    references = (
        Reference(
            "Antonacci, G. (2014), Dual Momentum Investing: An Innovative Strategy for Higher "
            "Returns with Less Risk, McGraw-Hill, ISBN 9780071849456",
            "https://books.google.com/books?isbn=9780071849456",
        ),
        Reference(
            "Antonacci, G. (2012), Risk Premia Harvesting Through Dual Momentum, SSRN 2042750",
            "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2042750",
        ),
        Reference(
            "Antonacci, G. (2013), Absolute Momentum: A Simple Rule-Based Strategy and "
            "Universal Trend-Following Overlay, SSRN 2244633",
            "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2244633",
        ),
        Reference(
            "Antonacci, G., Global Equities Momentum (rules as stated by the author)",
            "https://www.optimalmomentum.com/global-equities-momentum/",
        ),
    )
    publication_date = "2014-11-21"
    proxies = proxies_for([US_EQUITY, INTL_EQUITY, BONDS, TBILLS])

    @dataclass(frozen=True)
    class Params:
        #: Momentum lookback in months, used for both relative and absolute momentum.
        lookback_months: int = 12
        #: Asset held when absolute momentum is negative (the book uses US aggregate bonds).
        fallback: str = BONDS
        #: "us": absolute filter on the S&P 500 (book); "winner": on the relative winner (RPH).
        abs_on: str = "us"

        def __post_init__(self) -> None:
            if self.lookback_months < 1:
                raise ValueError("lookback_months must be >= 1")
            if self.abs_on not in ABS_MODES:
                raise ValueError(f"abs_on must be one of {ABS_MODES}, got {self.abs_on!r}")

    param_grid = {"lookback_months": [6, 9], "fallback": ["BIL"], "abs_on": ["winner"]}

    def universe(self) -> list[str]:
        return list(dict.fromkeys([US_EQUITY, INTL_EQUITY, BONDS, TBILLS, self.params.fallback]))

    def warmup(self) -> int:
        # 13 month-end observations for a 12-month lookback, plus a few sessions of slack.
        return 21 * (self.params.lookback_months + 1) + 5

    def schedule(self):
        return MonthEnd()

    def momentum(self, ctx: Context) -> dict[str, float]:
        """Trailing ``lookback_months`` total return of each available symbol.

        The last month-end row is the latest close (the current month-end on a
        ``MonthEnd`` schedule). A symbol is included only if it trades today and has
        a valid close at both ends of the lookback window.
        """
        k = self.params.lookback_months
        window = ctx.history("close", _MAX_SESSIONS_PER_MONTH * (k + 2)).ffill()
        monthly = month_end(window)
        out: dict[str, float] = {}
        for sym in self.universe():
            if not ctx.is_tradable(sym):
                continue
            r = float(trailing_return(monthly[sym], k))
            if math.isfinite(r):
                out[sym] = r
        return out

    def target_weights(self, ctx: Context):
        mom = self.momentum(ctx)
        # T-bill hurdle; without T-bill history the hurdle is a zero return.
        hurdle = mom.get(TBILLS, 0.0)
        equities = [s for s in (US_EQUITY, INTL_EQUITY) if s in mom]

        risky: str | None = None
        if equities:
            # Relative momentum; ties go to the US (listed first).
            winner = max(equities, key=lambda s: mom[s])
            if self.params.abs_on == "us" and US_EQUITY in mom:
                risk_on = mom[US_EQUITY] > hurdle
            else:  # "winner" ordering, or the US series is not yet available
                risk_on = mom[winner] > hurdle
            risky = winner if risk_on else None

        if risky is not None:
            return {risky: 1.0}
        return self._fallback(ctx)

    def _fallback(self, ctx: Context) -> dict[str, float]:
        for sym in (self.params.fallback, TBILLS):
            if ctx.is_tradable(sym):
                return {sym: 1.0}
        return {}
