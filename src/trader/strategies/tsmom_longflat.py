"""Time-series momentum, long/flat multi-asset ETF adaptation.

Moskowitz, Ooi & Pedersen (2012) go long or short each futures market on the sign
of its past 12-month excess return, sized to equal ex-ante volatility. This is the
unlevered, long-only version ("Variant A" of the research dossier): the short leg
becomes cash (BIL), and the per-asset 40%/sigma sizing becomes an inverse-volatility
risk budget over every eligible asset, so gross exposure never exceeds 1.

At each month-end ``t``:

1. Eligible set: risky assets with a price today, at least ``lookback + 1``
   month-end closes and at least 120 daily returns.
2. ``excess_i = R_i(lookback) - R_BIL(lookback)`` on month-end total-return closes
   (no skip month).
3. ``s_i = 1`` if ``excess_i > 0`` else 0. ``signal="blend"`` averages the 1-, 3-
   and 12-month indicators (Hurst, Ooi & Pedersen 2017).
4. ``sigma_i``: EWMA std of daily returns, ``ewm(com=vol_com)``, through ``t``.
5. ``b_i = (1/sigma_i) / sum_j (1/sigma_j)`` over ALL eligible assets.
6. ``w_i = s_i * b_i``; BIL gets ``1 - sum_i w_i``.

``trend_filter=False`` sets ``s_i = 1`` (plain inverse-vol portfolio), the control
run that separates the trend signal from the risk-budgeted drift of the assets.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from trader.data.proxies import proxies_for
from trader.indicators import ewma_vol, month_end
from trader.strategy import Context, MonthEnd, Reference, Strategy, register

RISKY = (
    "SPY",
    "IWM",
    "EFA",
    "EEM",
    "EWJ",
    "VGK",
    "IEF",
    "TLT",
    "LQD",
    "TIP",
    "VNQ",
    "DBC",
    "GLD",
)
CASH = "BIL"
SIGNALS = ("12", "blend")
BLEND_HORIZONS = (1, 3, 12)
#: Daily returns an asset needs before its volatility estimate is trusted.
MIN_RETURN_SESSIONS = 120
#: Bridge short holiday gaps in proxy series (GC=F before GLD has a few) so an asset
#: does not drop out of the portfolio for a month because of one missing close.
MAX_STALE_SESSIONS = 5


@register
class TimeSeriesMomentum(Strategy):
    name = "tsmom_longflat"
    title = "Time-series momentum (long/flat, inverse-vol)"
    description = (
        "Moskowitz-Ooi-Pedersen time-series momentum on 13 multi-asset ETFs, long/flat and "
        "unlevered: each month-end, every asset with a positive 12-month return in excess of "
        "T-bills is held at its inverse-volatility risk budget (EWMA vol, com=60, budget taken "
        "over all eligible assets); the budgets of assets with a negative excess return go to BIL."
    )
    references = (
        Reference(
            "Moskowitz, T.J., Ooi, Y.H. & Pedersen, L.H. (2012), Time series momentum, "
            "Journal of Financial Economics 104(2), 228-250",
            "https://doi.org/10.1016/j.jfineco.2011.11.003",
        ),
        Reference(
            "Hurst, B., Ooi, Y.H. & Pedersen, L.H. (2017), A Century of Evidence on "
            "Trend-Following Investing, Journal of Portfolio Management 44(1), 15-29",
            "https://doi.org/10.3905/jpm.2017.44.1.015",
        ),
        Reference(
            "Huang, D., Li, J., Wang, L. & Zhou, G. (2020), Time series momentum: Is it there?, "
            "Journal of Financial Economics 135(3), 774-794",
            "https://doi.org/10.1016/j.jfineco.2019.08.004",
        ),
    )
    publication_date = "2011-12-11"
    proxies = proxies_for([*RISKY, CASH])

    @dataclass(frozen=True)
    class Params:
        #: Lookback of the sign signal in months (used when ``signal == "12"``).
        lookback_months: int = 12
        #: Center of mass, in sessions, of the EWMA volatility estimate.
        vol_com: int = 60
        #: "12": single-horizon MOP signal over ``lookback_months``;
        #: "blend": equal-weight 1/3/12-month signal of Hurst, Ooi & Pedersen.
        signal: str = "12"
        #: False = control run with every eligible asset held (s_i = 1).
        trend_filter: bool = True

    param_grid = {
        "lookback_months": [3, 6, 9],
        "vol_com": [20, 120],
        "signal": ["blend"],
        "trend_filter": [False],
    }

    def __init__(self, **params) -> None:
        super().__init__(**params)
        if self.params.signal not in SIGNALS:
            raise ValueError(f"signal must be one of {SIGNALS}, got {self.params.signal!r}")
        if self.params.lookback_months < 1 or self.params.vol_com < 1:
            raise ValueError("lookback_months and vol_com must be >= 1")

    def universe(self) -> list[str]:
        return [*RISKY, CASH]

    def horizons(self) -> tuple[int, ...]:
        """Lookbacks (months) whose excess-return signs make up the signal."""
        return BLEND_HORIZONS if self.params.signal == "blend" else (self.params.lookback_months,)

    def warmup(self) -> int:
        return max(22 * (max(self.horizons()) + 1), MIN_RETURN_SESSIONS + 1)

    def schedule(self):
        return MonthEnd()

    def target_weights(self, ctx: Context):
        p = self.params
        horizons = self.horizons()
        need_months = max(horizons) + 1
        # Enough sessions for the longest lookback and for the EWMA to forget its start
        # ((com/(com+1))^(20*com) < 1e-8), without recomputing over the whole history.
        n = max(23 * (need_months + 1), 20 * p.vol_com, 2 * MIN_RETURN_SESSIONS)
        close = ctx.history("close", n).ffill(limit=MAX_STALE_SESSIONS)
        monthly = month_end(close)

        today = close.iloc[-1]
        n_months = monthly.notna().sum()
        n_rets = close.pct_change().notna().sum()
        candidates = [
            s
            for s in RISKY
            if np.isfinite(today[s])
            and n_months[s] >= need_months
            and n_rets[s] >= MIN_RETURN_SESSIONS
        ]
        cash_ok = bool(np.isfinite(today[CASH]))
        if not candidates:
            return {CASH: 1.0} if cash_ok else {}

        # Fraction of horizons on which the asset beat T-bills.
        votes = pd.Series(0.0, index=candidates)
        for h in horizons:
            base = monthly.iloc[-1 - h]
            r = monthly.iloc[-1][candidates] / base[candidates] - 1.0
            votes += (r - self._cash_return(ctx, monthly, h) > 0).astype(float)
            votes[r.isna()] = np.nan
        signal = votes / len(horizons) if p.trend_filter else votes * 0.0 + 1.0

        vol = ewma_vol(close[candidates], com=p.vol_com)
        ok = signal.notna() & np.isfinite(vol) & (vol > 0)
        eligible = [s for s in candidates if ok[s]]
        if not eligible:
            return {CASH: 1.0} if cash_ok else {}

        inv = 1.0 / vol[eligible]
        budget = inv / inv.sum()
        weights = {s: float(signal[s] * budget[s]) for s in eligible if signal[s] > 0}
        if cash_ok:
            weights[CASH] = max(0.0, 1.0 - sum(weights.values()))
        return weights

    @staticmethod
    def _cash_return(ctx: Context, monthly: pd.DataFrame, h: int) -> float:
        """T-bill return over the last ``h`` months: BIL, else the harness T-bill rate."""
        r = monthly[CASH].iloc[-1] / monthly[CASH].iloc[-1 - h] - 1.0
        if np.isfinite(r):
            return float(r)
        rf = ctx.data.rf
        return float((1.0 + rf[rf.index > monthly.index[-1 - h]]).prod() - 1.0)
