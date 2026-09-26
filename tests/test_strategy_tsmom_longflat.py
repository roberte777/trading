from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from trader.calendar import TradingCalendar
from trader.data.market_data import MarketData
from trader.indicators import month_end
from trader.strategies.tsmom_longflat import RISKY, TimeSeriesMomentum
from trader.strategy import Context

START, DECISION = "2004-01-02", "2006-06-30"  # 2006-06-30 is a month-end session


def _alternating(n: int, drift: float, amp: float) -> np.ndarray:
    """Daily returns drift +/- amp. Scaling amp scales the EWMA vol exactly."""
    return drift + amp * np.where(np.arange(n) % 2 == 0, 1.0, -1.0)


def _context(returns: dict[str, np.ndarray | None], first_valid: dict[str, str] | None = None):
    """A Context at DECISION's close. ``None`` returns = flat 0.01%/day (unused filler)."""
    cal = TradingCalendar.nyse(start="2003-01-01", end="2007-12-31")
    sessions = cal.sessions_between(START, DECISION)
    n = len(sessions)
    close = pd.DataFrame(index=sessions, columns=[*RISKY, "BIL"], dtype=float)
    for sym in close.columns:
        r = returns.get(sym)
        if r is None:
            r = np.full(n, 0.0001)
        close[sym] = 100.0 * np.cumprod(1.0 + r)
    for sym, first in (first_valid or {}).items():
        close.loc[: pd.Timestamp(first) - pd.Timedelta(days=1), sym] = np.nan
    frames = {f: close.copy() for f in ("open", "high", "low", "close")}
    frames["volume"] = close * 0.0 + 1e6
    data = MarketData(frames, rf=pd.Series(0.0002, index=sessions))
    ctx = Context(now=sessions[-1], data=data, positions={}, weights={}, equity=1.0, calendar=cal)
    return ctx, close


def _excess_12m(close: pd.DataFrame, sym: str) -> float:
    m = month_end(close)
    r = m.iloc[-1] / m.iloc[-13] - 1.0
    return float(r[sym] - r["BIL"])


def _base_returns(n: int) -> dict[str, np.ndarray]:
    # Every risky asset except the four under test falls hard, so it is flat but
    # still eligible: its risk slot counts in the budget. Give them the same vol.
    out = {s: _alternating(n, -0.001, 0.01) for s in RISKY}
    out["BIL"] = np.full(n, 0.0002)  # ~5%/yr T-bills
    return out


def test_signal_and_budget_over_all_eligible_assets():
    n = len(TradingCalendar.nyse("2003-01-01", "2007-12-31").sessions_between(START, DECISION))
    rets = _base_returns(n)
    rets["SPY"] = _alternating(n, 0.0005, 0.01)  # up, vol a
    rets["EFA"] = _alternating(n, 0.0005, 0.02)  # up, vol 2a -> half the budget
    rets["TLT"] = _alternating(n, -0.0005, 0.01)  # down -> flat
    rets["IEF"] = _alternating(n, 0.00015, 0.01)  # up, but less than T-bills -> flat
    ctx, close = _context(rets)
    raw_ief = month_end(close)["IEF"]
    assert raw_ief.iloc[-1] / raw_ief.iloc[-13] - 1.0 > 0  # a raw-return rule would buy it
    assert _excess_12m(close, "IEF") < 0
    assert _excess_12m(close, "SPY") > 0 and _excess_12m(close, "EFA") > 0

    w = TimeSeriesMomentum().target_weights(ctx)

    # 13 eligible assets: 12 with vol a (budget 1) and EFA with vol 2a (budget 1/2).
    unit = 1.0 / 12.5
    assert set(w) == {"SPY", "EFA", "BIL"}
    assert w["SPY"] == pytest.approx(unit, rel=1e-9)
    assert w["EFA"] == pytest.approx(unit / 2, rel=1e-9)
    assert w["BIL"] == pytest.approx(1.0 - 1.5 * unit, rel=1e-9)

    # Control run: the trend filter off holds every eligible asset at its budget.
    control = TimeSeriesMomentum(trend_filter=False).target_weights(ctx)
    assert control.get("BIL", 0.0) == pytest.approx(0.0, abs=1e-12)
    assert control["TLT"] == pytest.approx(unit, rel=1e-9)
    assert sum(control.values()) == pytest.approx(1.0)


def test_asset_without_enough_history_gets_no_weight_or_budget():
    n = len(TradingCalendar.nyse("2003-01-01", "2007-12-31").sessions_between(START, DECISION))
    rets = _base_returns(n)
    rets["SPY"] = _alternating(n, 0.0005, 0.01)
    rets["GLD"] = _alternating(n, 0.003, 0.01)  # strong uptrend, but ...
    rets["DBC"] = _alternating(n, 0.003, 0.01)
    # ... GLD has no data at all yet; DBC has data but only ~8 month-ends.
    ctx, _ = _context(rets, first_valid={"GLD": "2007-01-02", "DBC": "2005-11-01"})
    assert not ctx.is_tradable("GLD")

    w = TimeSeriesMomentum().target_weights(ctx)

    assert "GLD" not in w and "DBC" not in w
    unit = 1.0 / 11  # 11 eligible assets, all with the same vol
    assert w["SPY"] == pytest.approx(unit, rel=1e-9)
    assert w["BIL"] == pytest.approx(1.0 - unit, rel=1e-9)


def test_blend_signal_counts_horizons():
    n = len(TradingCalendar.nyse("2003-01-01", "2007-12-31").sessions_between(START, DECISION))
    rets = _base_returns(n)
    # Rallies for most of the year, then falls over the last 3 months (~63 sessions):
    # 12-month excess > 0, 3- and 1-month excess < 0 -> 1/3 of its budget.
    spy = _alternating(n, 0.003, 0.01)
    spy[-63:] -= 0.004
    rets["SPY"] = spy
    ctx, close = _context(rets)
    assert _excess_12m(close, "SPY") > 0

    w_blend = TimeSeriesMomentum(signal="blend").target_weights(ctx)
    w_12 = TimeSeriesMomentum().target_weights(ctx)

    assert w_blend["SPY"] == pytest.approx(w_12["SPY"] / 3, rel=1e-9)
    assert w_blend["BIL"] == pytest.approx(1.0 - w_blend["SPY"], rel=1e-9)


def test_rejects_unknown_signal():
    with pytest.raises(ValueError):
        TimeSeriesMomentum(signal="6")
