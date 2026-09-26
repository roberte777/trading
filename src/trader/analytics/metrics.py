"""Performance, risk and trading metrics for daily return series."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats as sps

PERIODS = 252

#: Stress windows reported for every strategy (peak-to-trough of the S&P 500 where applicable).
CRISES: dict[str, tuple[str, str]] = {
    "Dot-com bust (2000-03 → 2002-10)": ("2000-03-24", "2002-10-09"),
    "GFC (2007-10 → 2009-03)": ("2007-10-09", "2009-03-09"),
    "Euro/US downgrade (2011-04 → 2011-10)": ("2011-04-29", "2011-10-03"),
    "Q4 2018 selloff": ("2018-09-20", "2018-12-24"),
    "COVID crash (2020-02 → 2020-03)": ("2020-02-19", "2020-03-23"),
    "2022 inflation bear": ("2022-01-03", "2022-10-12"),
    "2025 tariff shock (2025-02 → 2025-04)": ("2025-02-19", "2025-04-08"),
}


def equity_curve(returns: pd.Series) -> pd.Series:
    return (1.0 + returns.fillna(0.0)).cumprod()


def drawdown(returns: pd.Series) -> pd.Series:
    eq = equity_curve(returns)
    return eq / eq.cummax() - 1.0


def _longest_underwater(dd: pd.Series) -> int:
    longest = cur = 0
    for under in (dd < -1e-12).to_numpy():
        cur = cur + 1 if under else 0
        longest = max(longest, cur)
    return longest


def monthly_returns(returns: pd.Series) -> pd.Series:
    r = returns.dropna()
    grouped = (1.0 + r).groupby([r.index.year, r.index.month]).prod() - 1.0
    grouped.index = pd.PeriodIndex([pd.Period(year=y, month=m, freq="M") for y, m in grouped.index])
    return grouped


def yearly_returns(returns: pd.Series) -> pd.Series:
    r = returns.dropna()
    return (1.0 + r).groupby(r.index.year).prod() - 1.0


def _safe_div(a: float, b: float) -> float:
    return a / b if b and math.isfinite(b) and abs(b) > 1e-15 else float("nan")


def performance_metrics(
    returns: pd.Series,
    rf: pd.Series | None = None,
    benchmark: pd.Series | None = None,
    periods: int = PERIODS,
) -> dict[str, float]:
    """Headline metrics. ``rf`` is a per-period risk-free return series."""
    r = returns.dropna()
    n = len(r)
    if n < 2:
        return {}
    rf_ = rf.reindex(r.index).fillna(0.0) if rf is not None else pd.Series(0.0, index=r.index)
    ex = r - rf_
    years = n / periods
    eq = equity_curve(r)
    total = float(eq.iloc[-1] - 1.0)
    cagr = float(eq.iloc[-1] ** (1.0 / years) - 1.0) if eq.iloc[-1] > 0 else -1.0
    vol = float(r.std(ddof=1) * math.sqrt(periods))
    sd_ex = float(ex.std(ddof=1))
    sharpe = _safe_div(float(ex.mean()), sd_ex) * math.sqrt(periods)
    downside = float(np.sqrt(np.mean(np.minimum(ex.to_numpy(), 0.0) ** 2)) * math.sqrt(periods))
    sortino = _safe_div(float(ex.mean()) * periods, downside)
    dd = eq / eq.cummax() - 1.0
    max_dd = float(dd.min())
    monthly = monthly_returns(r)
    q05 = float(r.quantile(0.05))
    out: dict[str, float] = {
        "start": str(r.index[0].date()),
        "end": str(r.index[-1].date()),
        "years": years,
        "total_return": total,
        "cagr": cagr,
        "volatility": vol,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_drawdown": max_dd,
        "calmar": _safe_div(cagr, abs(max_dd)),
        "ulcer_index": float(np.sqrt(np.mean(dd.to_numpy() ** 2))),
        "longest_drawdown_days": _longest_underwater(dd),
        "skew": float(sps.skew(r, bias=False)),
        "excess_kurtosis": float(sps.kurtosis(r, fisher=True, bias=False)),
        "var_95": -q05,
        "cvar_95": -float(r[r <= q05].mean()),
        "best_month": float(monthly.max()),
        "worst_month": float(monthly.min()),
        "pct_positive_months": float((monthly > 0).mean()),
        "sharpe_tstat": _safe_div(float(ex.mean()), sd_ex) * math.sqrt(n),
        "mean_rf": float(rf_.mean() * periods),
    }
    if benchmark is not None:
        b = benchmark.reindex(r.index).fillna(0.0)
        bex = b - rf_
        var_b = float(bex.var(ddof=1))
        beta = _safe_div(float(np.cov(ex, bex, ddof=1)[0, 1]), var_b)
        active = r - b
        te = float(active.std(ddof=1) * math.sqrt(periods))
        bm = monthly_returns(b)
        up = bm > 0
        out.update(
            {
                "beta": beta,
                "alpha": float((ex.mean() - beta * bex.mean()) * periods),
                "correlation": float(r.corr(b)),
                "tracking_error": te,
                "information_ratio": _safe_div(float(active.mean()) * periods, te),
                "up_capture": _safe_div(float(monthly[up].mean()), float(bm[up].mean())),
                "down_capture": _safe_div(float(monthly[~up].mean()), float(bm[~up].mean())),
                "benchmark_cagr": float(equity_curve(b).iloc[-1] ** (1.0 / years) - 1.0),
            }
        )
    return out


#: T-bill ETFs: holding them counts as being in cash, not "in the market".
CASH_LIKE = frozenset({"BIL", "SHV", "SGOV"})


def trading_metrics(
    daily: pd.DataFrame,
    trades: pd.DataFrame,
    weights: pd.DataFrame | None = None,
    periods: int = PERIODS,
) -> dict[str, float]:
    """Turnover, exposure and cost drag from a backtest's daily ledger.

    With ``weights``, exposure excludes T-bill ETFs, so a strategy parked in BIL
    counts as out of the market.
    """
    years = len(daily) / periods
    avg_equity = float(daily["equity"].mean())
    costs = float(daily["fees"].sum() + daily["slippage"].sum())
    if weights is not None and not weights.empty:
        risky_cols = [c for c in weights.columns if c not in CASH_LIKE]
        risk = weights[risky_cols].abs().sum(axis=1).reindex(daily.index).fillna(0.0)
    else:
        risk = daily["gross"]
    return {
        "turnover_annual": float(daily["turnover"].sum() / 2.0 / years),
        "avg_gross_exposure": float(daily["gross"].mean()),
        "avg_risk_exposure": float(risk.mean()),
        "time_in_market": float((risk > 0.05).mean()),
        "trades_per_year": float(len(trades) / years) if not trades.empty else 0.0,
        "cost_drag_annual": float(costs / avg_equity / years) if avg_equity > 0 else float("nan"),
        "total_fees": float(daily["fees"].sum()),
        "total_slippage": float(daily["slippage"].sum()),
    }


def window_return(returns: pd.Series, start: str, end: str) -> float:
    r = returns.loc[pd.Timestamp(start) : pd.Timestamp(end)].dropna()
    if len(r) < 2:
        return float("nan")
    return float((1.0 + r).prod() - 1.0)


def crisis_returns(returns: pd.Series) -> dict[str, float]:
    out = {}
    for label, (s, e) in CRISES.items():
        if returns.index[0] <= pd.Timestamp(s) and returns.index[-1] >= pd.Timestamp(e):
            out[label] = window_return(returns, s, e)
    return out


def rolling_sharpe(
    returns: pd.Series, rf: pd.Series | None = None, window: int = 3 * PERIODS
) -> pd.Series:
    ex = returns - (rf.reindex(returns.index).fillna(0.0) if rf is not None else 0.0)
    return ex.rolling(window).mean() / ex.rolling(window).std(ddof=1) * math.sqrt(PERIODS)


def rolling_cagr(returns: pd.Series, window: int = 3 * PERIODS) -> pd.Series:
    log_r = np.log1p(returns.fillna(0.0))
    return np.expm1(log_r.rolling(window).sum() * PERIODS / window)


def split_metrics(
    returns: pd.Series, rf: pd.Series | None, benchmark: pd.Series | None, split: str | None
) -> dict[str, Any]:
    """Metrics before and after ``split`` (e.g. a strategy's publication date)."""
    if not split:
        return {}
    cut = pd.Timestamp(split)
    out: dict[str, Any] = {"split": str(cut.date())}
    pre, post = returns.loc[:cut], returns.loc[cut + pd.Timedelta(days=1) :]
    if len(pre) > PERIODS:
        out["in_sample"] = performance_metrics(pre, rf, benchmark)
    if len(post) > PERIODS:
        out["out_of_sample"] = performance_metrics(post, rf, benchmark)
    return out
