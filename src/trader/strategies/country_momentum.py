"""Country equity momentum: the long-only top tercile ("P3") of Asness, Moskowitz &
Pedersen (2013), "Value and Momentum Everywhere", on US-listed country ETFs."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from trader.data.proxies import proxies_for
from trader.indicators import month_end, trailing_return
from trader.strategy import Context, MonthEnd, Reference, Strategy, register

#: AMP's 18 developed equity markets as US-listed, USD-unhedged ETFs (Portugal has
#: no listed ETF with usable history). EDEN and ENOR start in January 2012.
COUNTRIES: tuple[str, ...] = (
    "SPY",  # United States
    "EWA",  # Australia
    "EWO",  # Austria
    "EWK",  # Belgium
    "EWC",  # Canada
    "EDEN",  # Denmark (2012-01)
    "EWQ",  # France
    "EWG",  # Germany
    "EWH",  # Hong Kong
    "EWI",  # Italy
    "EWJ",  # Japan
    "EWN",  # Netherlands
    "ENOR",  # Norway (2012-01)
    "EWP",  # Spain
    "EWD",  # Sweden
    "EWL",  # Switzerland
    "EWU",  # United Kingdom
)
CASH = "BIL"
#: Most NYSE sessions in any calendar month; sizes the history window.
_MAX_SESSIONS_PER_MONTH = 23


@register
class CountryMomentum(Strategy):
    name = "country_momentum"
    title = "Country equity momentum (AMP 2013, top tercile)"
    description = (
        "Each month-end, rank AMP's developed equity markets (SPY plus iShares MSCI "
        "country ETFs) on MOM2-12, the 12-month total return skipping the most recent "
        "month, and hold the top third equal-weighted (AMP's P3 portfolio). Optional "
        "absolute filter sends a selected country's slot to T-bills (BIL) when its "
        "momentum does not beat BIL's over the same window."
    )
    references = (
        Reference(
            "Asness, C.S., Moskowitz, T.J., Pedersen, L.H. (2013), Value and Momentum "
            "Everywhere, Journal of Finance 68(3), 929-985, doi:10.1111/jofi.12021",
            "https://pages.stern.nyu.edu/~lpederse/papers/ValMomEverywhere.pdf",
        ),
        Reference(
            "Daniel, K., Moskowitz, T.J. (2016), Momentum Crashes, Journal of Financial "
            "Economics 122(2), 221-247",
            "https://doi.org/10.1016/j.jfineco.2015.12.002",
        ),
    )
    # First SSRN posting (abstract 1363476).
    publication_date = "2009-03-20"
    proxies = proxies_for([*COUNTRIES, CASH])

    @dataclass(frozen=True)
    class Params:
        lookback_months: int = 12
        skip_months: int = 1
        top_fraction: float = 0.3333333333
        abs_filter: bool = False

    param_grid = {
        "skip_months": [0],
        "lookback_months": [6],
        "top_fraction": [0.2, 0.5],
        "abs_filter": [True],
    }

    def universe(self) -> list[str]:
        return [*COUNTRIES, CASH]

    def _months_needed(self) -> int:
        return self.params.lookback_months + self.params.skip_months + 1

    def warmup(self) -> int:
        return self._months_needed() * 22

    def schedule(self):
        return MonthEnd()

    def target_weights(self, ctx: Context):
        p = self.params
        need = self._months_needed()
        # Enough sessions to always contain ``need`` distinct calendar months.
        window = ctx.history("close", need * _MAX_SESSIONS_PER_MONTH)[[*COUNTRIES, CASH]]
        monthly = month_end(window)  # last row = the current (decision) close
        if len(monthly) < need:
            return {CASH: 1.0} if ctx.is_tradable(CASH) else {}
        recent = monthly.iloc[-need:]
        mom = trailing_return(monthly, p.lookback_months, p.skip_months)

        eligible = [
            s
            for s in COUNTRIES
            if bool(recent[s].notna().all()) and np.isfinite(mom[s]) and ctx.is_tradable(s)
        ]
        if not eligible:
            return {CASH: 1.0} if ctx.is_tradable(CASH) else {}

        # Highest momentum first; ties broken by symbol so decisions are deterministic.
        ranked = sorted(eligible, key=lambda s: (-float(mom[s]), s))
        n_hold = max(1, math.floor(len(eligible) * p.top_fraction + 0.5))
        chosen = ranked[:n_hold]
        slot = 1.0 / n_hold

        cash_ok = ctx.is_tradable(CASH)
        hurdle = float(mom[CASH]) if cash_ok and np.isfinite(mom[CASH]) else 0.0
        weights: dict[str, float] = {}
        for s in chosen:
            if p.abs_filter and not float(mom[s]) > hurdle:
                if cash_ok:
                    weights[CASH] = weights.get(CASH, 0.0) + slot
                continue
            weights[s] = slot
        return weights
