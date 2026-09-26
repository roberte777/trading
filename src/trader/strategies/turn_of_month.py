"""Turn-of-the-month effect (Ariel 1987; Lakonishok & Smidt 1988; McConnell & Xu 2008).

Hold the S&P 500 over the turn of the month, i.e. trading day -1 (the last
session of the month) through trading day +3, and T-bills otherwise.

The window is a pure function of the exchange calendar, which is known in
advance, so deciding at the close of session ``t`` whether the *next* session
(the fill session) is inside the window uses no future market data.
"""

from __future__ import annotations

from dataclasses import dataclass

from trader.data.proxies import proxies_for
from trader.strategy import Context, Daily, Reference, Strategy, register

EQUITY = "SPY"
CASH = "BIL"


@register
class TurnOfTheMonth(Strategy):
    name = "turn_of_month"
    title = "Turn of the month (McConnell & Xu 2008)"
    description = (
        "Long SPY from the last trading day of each month through the third trading day "
        "of the next month (the [-1, +3] turn-of-month window), T-bills (BIL) otherwise. "
        "Decided daily from the NYSE calendar; with next-open fills SPY is held from the "
        "open of day -1 to the open of day +4."
    )
    references = (
        Reference(
            "Ariel, R.A. (1987), A Monthly Effect in Stock Returns, Journal of Financial "
            "Economics 18(1), 161-174",
            "https://doi.org/10.1016/0304-405X(87)90066-3",
        ),
        Reference(
            "Lakonishok, J. & Smidt, S. (1988), Are Seasonal Anomalies Real? A Ninety-Year "
            "Perspective, Review of Financial Studies 1(4), 403-425",
            "https://doi.org/10.1093/rfs/1.4.403",
        ),
        Reference(
            "McConnell, J.J. & Xu, W. (2008), Equity Returns at the Turn of the Month, "
            "Financial Analysts Journal 64(2), 49-64 (SSRN 917884, July 2006)",
            "https://doi.org/10.2469/faj.v64.n2.11",
        ),
        Reference(
            "Han, L., Han, Y. & Tian, S. (2025), The disappearing turn-of-month effect, "
            "Finance Research Letters 71, 106461",
            "https://doi.org/10.1016/j.frl.2024.106461",
        ),
        Reference(
            "Sullivan, R., Timmermann, A. & White, H. (2001), Dangers of data mining: The case "
            "of calendar effects in stock returns, Journal of Econometrics 105(1), 249-286",
            "https://doi.org/10.1016/S0304-4076(01)00077-X",
        ),
    )
    # McConnell & Xu's SSRN posting; the basic [-1, +3] window dates from 1987-88.
    publication_date = "2006-07-01"
    proxies = proxies_for([EQUITY, CASH])

    @dataclass(frozen=True)
    class Params:
        #: Sessions at the end of the month in the window (1 = only the last session).
        days_before: int = 1
        #: Sessions at the start of the month in the window (3 = sessions 1, 2 and 3).
        days_after: int = 3

        def __post_init__(self) -> None:
            if self.days_before < 0 or self.days_after < 0:
                raise ValueError("days_before and days_after must be >= 0")

    param_grid = {"days_before": [2], "days_after": [2, 4]}

    def universe(self) -> list[str]:
        return [EQUITY, CASH]

    def warmup(self) -> int:
        return 1

    def schedule(self):
        return Daily()

    def in_window(self, session, calendar) -> bool:
        """True if ``session`` lies in the turn-of-month window [-days_before, +days_after]."""
        p = self.params
        return (
            calendar.sessions_left_in_month(session) < p.days_before
            or calendar.session_of_month(session) <= p.days_after
        )

    def target_weights(self, ctx: Context):
        # Orders placed at this close fill on the next session, so position for it.
        fill_session = ctx.calendar.next_session(ctx.now)
        if self.in_window(fill_session, ctx.calendar) and ctx.is_tradable(EQUITY):
            return {EQUITY: 1.0}
        if ctx.is_tradable(CASH):
            return {CASH: 1.0}
        return {}
