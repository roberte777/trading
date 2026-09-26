"""Volatility-managed S&P 500 (Moreira & Muir 2017), unlevered and calibrated in real time.

At each month-end the SPY weight is ``min(cap, c_t / RV_t)``, where ``RV_t`` is the
realized variance of the month just ended (sum of squared demeaned daily excess
returns) and ``c_t`` scales the rule so that the *uncapped* managed series would have
had the same unconditional volatility as buy-and-hold over all months before ``t``.
The rest of the portfolio sits in T-bills (BIL).

This is the "No Leverage" row of Moreira & Muir's Tables 4-5. The paper picks ``c``
over the full sample (in-sample); here it is re-estimated every month from an
expanding window of strictly earlier months, as Cederburg et al. (2020) do for their
real-time test.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from trader.data.proxies import proxies_for
from trader.strategy import Context, MonthEnd, Reference, Strategy, register

RISKY = "SPY"
CASH = "BIL"
#: Sessions in a nominal month. Used as the realized-variance window when a decision
#: does not fall on a month-end (the first session of a backtest, timing-luck shifts).
SESSIONS_PER_MONTH = 21

CALIBRATIONS = ("expanding", "mean_rv")
SCALINGS = ("variance", "vol")


def _month_key(index: pd.DatetimeIndex) -> np.ndarray:
    return np.asarray(index.year * 12 + index.month - 1, dtype=np.int64)


def daily_excess_returns(close: pd.Series, rf: pd.Series) -> pd.Series:
    """Daily total return minus the T-bill return, from the first valid close onwards.

    The first element (the first close, which has no return) is NaN. Missing closes
    after it are forward-filled (a zero return that day; the next return spans both
    sessions), so a vendor gap cannot drop a month.
    """
    first = close.first_valid_index()
    if first is None:
        return pd.Series(dtype=float)
    px = close.loc[first:].ffill()
    return px.pct_change() - rf.reindex(px.index).fillna(0.0)


def monthly_stats(excess: pd.Series, rf: pd.Series) -> pd.DataFrame:
    """Per complete calendar month: realized variance ``rv`` and excess return ``ret``.

    ``rv`` is Moreira & Muir's estimator: the sum over the month's sessions of squared
    daily excess returns minus their monthly mean (not annualized, not averaged).
    ``ret`` is the compounded monthly return minus the compounded T-bill return.
    Indexed by ``year * 12 + month - 1``. A month with any missing daily return (the
    month of the first close) is dropped.
    """
    if excess.empty:
        return pd.DataFrame(columns=["rv", "ret"], dtype=float)
    key = _month_key(excess.index)
    rf_d = rf.reindex(excess.index).fillna(0.0)
    g = excess.groupby(key)
    n = g.count()
    complete = n == g.size()
    rv = g.var(ddof=0) * n
    growth = np.expm1(np.log1p(excess + rf_d).groupby(key).sum())
    bills = np.expm1(np.log1p(rf_d).groupby(key).sum())
    out = pd.DataFrame({"rv": rv, "ret": growth - bills})
    return out[complete]


@register
class VolatilityManagedSPY(Strategy):
    name = "vol_managed_spy"
    title = "Volatility-managed SPY (Moreira-Muir, unlevered)"
    description = (
        "Moreira & Muir's volatility-managed market portfolio without leverage. At each "
        "month-end, hold SPY at weight min(1, c/RV), where RV is the month's realized "
        "variance of daily SPY excess returns and c is recalibrated each month on all "
        "earlier months so the uncapped rule has buy-and-hold's volatility; the rest "
        "goes to T-bills (BIL)."
    )
    references = (
        Reference(
            "Moreira, A. & Muir, T. (2017), Volatility-Managed Portfolios, Journal of "
            "Finance 72(4), 1611-1644; NBER Working Paper 22208 (2016)",
            "https://doi.org/10.1111/jofi.12513",
        ),
        Reference(
            "Cederburg, S., O'Doherty, M. S., Wang, F. & Yan, X. (2020), On the "
            "performance of volatility-managed portfolios, Journal of Financial "
            "Economics 138(1), 95-117",
            "https://doi.org/10.1016/j.jfineco.2020.04.015",
        ),
        Reference(
            "Bongaerts, D., Kang, X. & van Dijk, M. (2020), Conditional Volatility "
            "Targeting, Financial Analysts Journal 76(4), 54-71",
            "https://doi.org/10.1080/0015198X.2020.1790853",
        ),
    )
    publication_date = "2015-09-12"
    proxies = proxies_for([RISKY, CASH])

    @dataclass(frozen=True)
    class Params:
        #: Maximum SPY weight. 1.0 is the paper's "No Leverage" row.
        cap: float = 1.0
        #: "expanding": c matches buy-and-hold volatility on all earlier months (MM).
        #: "mean_rv": c is the long-run mean of monthly RV (Bongaerts et al. style).
        calibration: str = "expanding"
        #: "variance": scale by 1/RV (MM headline). "vol": scale by 1/sqrt(RV).
        scaling: str = "variance"
        #: Calibration months required before the rule is used; 100% SPY until then.
        min_calibration_months: int = 120

        def __post_init__(self) -> None:
            if self.calibration not in CALIBRATIONS:
                raise ValueError(f"calibration must be one of {CALIBRATIONS}")
            if self.scaling not in SCALINGS:
                raise ValueError(f"scaling must be one of {SCALINGS}")
            if not 0.0 < self.cap <= 1.0:
                raise ValueError("cap must be in (0, 1]: this is the unlevered version")
            if self.min_calibration_months < 2:
                raise ValueError("min_calibration_months must be at least 2")

    param_grid = {"calibration": ["mean_rv"], "scaling": ["vol"]}

    def universe(self) -> list[str]:
        return [RISKY, CASH]

    def warmup(self) -> int:
        # Enough sessions for the calibration window plus the month being scaled.
        return SESSIONS_PER_MONTH * (self.params.min_calibration_months + 2)

    def schedule(self):
        return MonthEnd()

    # -- signal ------------------------------------------------------------------------
    def spy_weight(self, ctx: Context) -> float:
        """Target SPY weight at the close of ``ctx.now`` (before availability checks)."""
        p = self.params
        rf = ctx.data.rf
        excess = daily_excess_returns(ctx.close[RISKY], rf)
        months = monthly_stats(excess, rf)
        now_key = int(_month_key(pd.DatetimeIndex([ctx.now]))[0])

        # Realized variance of "month t": the calendar month ending today, or, when
        # today is not a month-end, the trailing nominal month of sessions.
        if _is_month_end(ctx) and now_key in months.index:
            rv_now = float(months.at[now_key, "rv"])
        else:
            window = excess.iloc[-SESSIONS_PER_MONTH:]
            if len(window) < SESSIONS_PER_MONTH or window.isna().any():
                return 1.0
            rv_now = float(((window - window.mean()) ** 2).sum())

        # Calibration uses only months strictly before the current calendar month.
        past = months[months.index < now_key]
        x = past["rv"] if p.scaling == "variance" else np.sqrt(past["rv"])
        if p.calibration == "expanding":
            nxt = past["ret"].reindex(x.index + 1).to_numpy()
            ok = np.isfinite(nxt) & (x.to_numpy() > 0)
            if int(ok.sum()) < p.min_calibration_months:
                return 1.0
            f_next, x_lag = nxt[ok], x.to_numpy()[ok]
            scaled_sd = float(np.std(f_next / x_lag, ddof=1))
            if not scaled_sd > 0:
                return 1.0
            c = float(np.std(f_next, ddof=1)) / scaled_sd
        else:  # mean_rv
            if len(x) < p.min_calibration_months:
                return 1.0
            c = float(x.mean())

        x_now = rv_now if p.scaling == "variance" else np.sqrt(rv_now)
        if not np.isfinite(x_now):
            return 1.0
        if x_now <= 0:
            return p.cap
        return float(min(p.cap, max(0.0, c / x_now)))

    def target_weights(self, ctx: Context):
        spy_ok = ctx.is_tradable(RISKY)
        bil_ok = ctx.is_tradable(CASH)
        w = min(self.params.cap, self.spy_weight(ctx)) if spy_ok else 0.0
        out: dict[str, float] = {}
        if w > 0:
            out[RISKY] = w
        if bil_ok and 1.0 - w > 1e-9:
            out[CASH] = 1.0 - w
        return out


def _is_month_end(ctx: Context) -> bool:
    try:
        return ctx.calendar.is_month_end(ctx.now)
    except KeyError:  # a calendar that does not know today; trust the schedule
        return True
