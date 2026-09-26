"""Unit tests for the volatility-managed SPY strategy on hand-built price paths.

Every month of the synthetic SPY path has a constant daily return ``x_m`` except for
two sessions at ``x_m + a_m`` and ``x_m - a_m``. The monthly mean is then exactly
``x_m`` and the realized variance (sum of squared demeaned returns) is exactly
``2 * a_m**2``, whatever the month's length. ``x_m`` varies from month to month so the
monthly returns have a non-zero spread.

If every calibration month has the same RV ``v``, both calibrations give ``c = v``
(expanding: ``std(F) / std(F / v) = v``; mean_rv: ``mean(RV) = v``), so the SPY
weight is ``min(1, v / RV_t)``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from trader.calendar import TradingCalendar
from trader.data.market_data import MarketData
from trader.strategies.vol_managed_spy import VolatilityManagedSPY
from trader.strategy import Context

A = 0.01  # base daily shock -> RV = 2 * A**2 in a normal month
CAL = TradingCalendar.nyse(start="1999-01-01", end="2012-12-31")


def _spy_returns(sessions: pd.DatetimeIndex, shocks: dict[str, float], seed: int = 3):
    """Daily returns: month drift x_m plus +/- a_m on the month's 2nd and 3rd sessions."""
    rng = np.random.default_rng(seed)
    r = np.zeros(len(sessions))
    month = sessions.to_period("M")
    for m in month.unique():
        pos = np.flatnonzero(month == m)
        x = rng.normal(0.0005, 0.001)
        a = A * shocks.get(str(m), 1.0)
        r[pos] = x
        r[pos[1]] += a
        r[pos[2]] -= a
    r[0] = 0.0  # the first close has no return
    return r


def _market(
    shocks: dict[str, float] | None = None,
    start: str = "2000-01-03",
    end: str = "2011-12-30",
    spy_first: str | None = None,
) -> MarketData:
    sessions = CAL.sessions_between(start, end)
    spy = 100.0 * np.cumprod(1.0 + _spy_returns(sessions, shocks or {}))
    bil = 100.0 * np.cumprod(np.full(len(sessions), 1.0 + 0.02 / 252))
    close = pd.DataFrame({"SPY": spy, "BIL": bil}, index=sessions)
    if spy_first is not None:
        close.loc[close.index < pd.Timestamp(spy_first), "SPY"] = np.nan
    frames = {f: close.copy() for f in ("open", "high", "low", "close")}
    frames["volume"] = pd.DataFrame(1e6, index=sessions, columns=close.columns)
    return MarketData(frames, rf=pd.Series(0.0, index=sessions))


def _month_end(month: str) -> pd.Timestamp:
    p = pd.Period(month, "M")
    return CAL.sessions_between(p.start_time, p.end_time)[-1]


def _decide(strategy, data: MarketData, when: pd.Timestamp) -> dict[str, float]:
    view = data.upto_date(when)
    assert view.now == when
    ctx = Context(now=when, data=view, positions={}, weights={}, equity=100_000.0, calendar=CAL)
    return dict(strategy.target_weights(ctx))


def test_high_variance_month_halves_spy_and_rest_goes_to_bills():
    # June 2010 has twice the usual variance -> w = v / 2v = 0.5 under 1/RV scaling.
    data = _market(shocks={"2010-06": np.sqrt(2.0)})
    w = _decide(VolatilityManagedSPY(), data, _month_end("2010-06"))
    assert w["SPY"] == pytest.approx(0.5, rel=1e-6)
    assert w["BIL"] == pytest.approx(0.5, rel=1e-6)

    w = _decide(VolatilityManagedSPY(calibration="mean_rv"), data, _month_end("2010-06"))
    assert w["SPY"] == pytest.approx(0.5, rel=1e-6)

    # Volatility scaling: c' = sqrt(v), sqrt(RV_t) = sqrt(2v) -> w = 1/sqrt(2).
    for calibration in ("expanding", "mean_rv"):
        s = VolatilityManagedSPY(scaling="vol", calibration=calibration)
        w = _decide(s, data, _month_end("2010-06"))
        assert w["SPY"] == pytest.approx(1.0 / np.sqrt(2.0), rel=1e-6)
        assert w["BIL"] == pytest.approx(1.0 - 1.0 / np.sqrt(2.0), rel=1e-6)


def test_calm_month_is_capped_at_fully_invested():
    # RV at a quarter of normal -> c / RV = 4, capped at 1: no leverage, no BIL.
    data = _market(shocks={"2010-06": 0.5})
    assert _decide(VolatilityManagedSPY(), data, _month_end("2010-06")) == {"SPY": 1.0}


def test_calibration_needs_120_complete_month_pairs():
    # Jan 2000 is incomplete (the first close has no return), so complete months start
    # in Feb 2000. At the end of month t, pairs (RV_m, F_m+1) need m+1 <= t-1:
    # Feb 2010 has 119 pairs (hold 100% SPY), Mar 2010 has 120 (rule active).
    data = _market(shocks={"2010-02": np.sqrt(2.0), "2010-03": np.sqrt(2.0)})
    strategy = VolatilityManagedSPY()
    assert _decide(strategy, data, _month_end("2010-02")) == {"SPY": 1.0}
    w = _decide(strategy, data, _month_end("2010-03"))
    assert w["SPY"] == pytest.approx(0.5, rel=1e-6)


def test_spy_without_data_gets_no_weight():
    # SPY only starts in 2005: before that everything is in BIL; afterwards SPY is held
    # at 100% until 120 months of calibration history exist.
    data = _market(spy_first="2005-03-01", shocks={"2005-06": 3.0})
    strategy = VolatilityManagedSPY()
    assert _decide(strategy, data, _month_end("2004-12")) == {"BIL": 1.0}
    assert _decide(strategy, data, _month_end("2005-06")) == {"SPY": 1.0}


def test_mid_month_decision_uses_trailing_month_of_sessions():
    # Off a month-end (first session of a backtest, timing-luck shifts) the current
    # calendar month is incomplete, so RV comes from the last 21 sessions instead.
    data = _market(shocks={"2010-06": 2.0})
    when = CAL.sessions_between("2010-06-15", "2010-06-15")[0]
    view = data.upto_date(when)
    f = view.close["SPY"].pct_change().iloc[-21:]
    rv_window = float(((f - f.mean()) ** 2).sum())
    expected = min(1.0, 2 * A**2 / rv_window)  # all calibration months have RV 2*A^2
    assert expected < 1.0
    w = _decide(VolatilityManagedSPY(), data, when)
    assert w["SPY"] == pytest.approx(expected, rel=1e-6)


def test_decision_ignores_later_data():
    data = _market(shocks={"2010-06": np.sqrt(2.0)})
    when = _month_end("2010-06")
    frames = {f: data.field(f).copy() for f in ("open", "high", "low", "close", "volume")}
    later = frames["close"].index > when
    for f in ("open", "high", "low", "close"):
        frames[f].loc[later, "SPY"] *= 3.0
    shocked = MarketData(frames, rf=data.rf)
    strategy = VolatilityManagedSPY()
    assert _decide(strategy, shocked, when) == _decide(strategy, data, when)


def test_rejects_unknown_options_and_leverage():
    with pytest.raises(ValueError):
        VolatilityManagedSPY(calibration="full_sample")
    with pytest.raises(ValueError):
        VolatilityManagedSPY(scaling="log")
    with pytest.raises(ValueError):
        VolatilityManagedSPY(cap=1.5)
