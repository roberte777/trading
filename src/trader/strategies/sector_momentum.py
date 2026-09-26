"""Sector momentum rotation (Moskowitz & Grinblatt 1999) on the Select Sector SPDRs.

At each month-end, rank the sector ETFs on their total return from month-end
``t - skip - lookback`` to month-end ``t - skip`` and hold the top ``top_n``
equal-weighted for one month. Optionally (Faber 2010) move everything to T-bills
when SPY closes the month at or below its 10-month SMA.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from trader.data.proxies import proxies_for
from trader.indicators import month_end, trailing_return
from trader.strategy import Context, MonthEnd, Reference, Strategy, register

#: Select Sector SPDRs. The nine originals list 1998-12-22, XLRE 2015-10-08, XLC 2018-06-19.
SECTORS = ("XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY", "XLRE", "XLC")
CASH = "BIL"
MARKET = "SPY"
#: Faber (2010) timing rule: 10-month simple moving average of month-end closes.
TREND_MONTHS = 10
#: Upper bound on sessions per calendar month (used to size the history window).
_MAX_SESSIONS_PER_MONTH = 23


@register
class SectorMomentum(Strategy):
    name = "sector_momentum"
    title = "Sector momentum rotation (Moskowitz-Grinblatt)"
    description = (
        "Each month-end, rank the Select Sector SPDRs on trailing 6-month total return "
        "(no skip month) and hold the top 3 equal-weighted for one month. Sectors join the "
        "ranking once they have enough month-end history (XLRE 2016, XLC 2018). Optional "
        "Faber (2010) hedge: 100% BIL when SPY is at or below its 10-month SMA."
    )
    references = (
        Reference(
            "Moskowitz, T.J., Grinblatt, M. (1999), Do Industries Explain Momentum?, "
            "Journal of Finance 54(4), 1249-1290",
            "https://doi.org/10.1111/0022-1082.00146",
        ),
        Reference(
            "Jegadeesh, N., Titman, S. (1993), Returns to Buying Winners and Selling Losers: "
            "Implications for Stock Market Efficiency, Journal of Finance 48(1), 65-91",
            "https://doi.org/10.1111/j.1540-6261.1993.tb04702.x",
        ),
        Reference(
            "Faber, M. (2010), Relative Strength Strategies for Investing, SSRN 1585517",
            "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1585517",
        ),
    )
    publication_date = "1999-08-01"
    proxies = proxies_for([*SECTORS, CASH, MARKET])

    @dataclass(frozen=True)
    class Params:
        lookback_months: int = 6
        skip_months: int = 0
        top_n: int = 3
        trend_filter: bool = False

    param_grid = {
        "lookback_months": [3, 9, 12],
        "skip_months": [1],
        "top_n": [2, 4],
        "trend_filter": [True],
    }

    def universe(self) -> list[str]:
        return [*SECTORS, CASH]

    def signal_symbols(self) -> list[str]:
        return [MARKET]

    def warmup(self) -> int:
        p = self.params
        return _MAX_SESSIONS_PER_MONTH * (p.lookback_months + p.skip_months + 1)

    def schedule(self):
        return MonthEnd()

    def _window(self) -> int:
        """Sessions that always contain the month-end closes the rules need."""
        p = self.params
        months = max(p.lookback_months + p.skip_months, TREND_MONTHS) + 2
        return _MAX_SESSIONS_PER_MONTH * months

    def target_weights(self, ctx: Context):
        p = self.params
        # Month-end closes; on the MonthEnd schedule the last row is the current month-end.
        monthly = month_end(ctx.history("close", self._window()))

        if p.trend_filter and _risk_off(monthly[MARKET]):
            return _cash(ctx, 1.0)

        need = p.lookback_months + p.skip_months + 1
        scores: dict[str, float] = {}
        for sym in SECTORS:
            if not ctx.is_tradable(sym):
                continue
            col = monthly[sym]
            if int(col.notna().sum()) < need:
                continue
            ret = float(trailing_return(col, p.lookback_months, p.skip_months))
            if np.isfinite(ret):
                scores[sym] = ret

        # Highest return first; ties broken alphabetically so the result is deterministic.
        ranked = sorted(scores, key=lambda s: (-scores[s], s))
        winners = ranked[: p.top_n]
        slot = 1.0 / p.top_n
        weights = {sym: slot for sym in winners}
        # Slots with no eligible sector (only before enough sectors have history) sit in BIL.
        weights.update(_cash(ctx, 1.0 - slot * len(winners)))
        return weights


def _risk_off(spy_monthly) -> bool:
    """Faber's rule: month-end close at or below the 10-month SMA of month-end closes."""
    tail = spy_monthly.iloc[-TREND_MONTHS:]
    if len(tail) < TREND_MONTHS or tail.isna().any():
        return False  # not enough history to judge the trend: do not hedge
    return bool(tail.iloc[-1] <= tail.mean())


def _cash(ctx: Context, weight: float) -> dict[str, float]:
    if weight <= 1e-12 or not ctx.is_tradable(CASH):
        return {}
    return {CASH: weight}
