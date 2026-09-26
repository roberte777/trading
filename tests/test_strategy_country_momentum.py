from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from trader.calendar import TradingCalendar
from trader.data.market_data import MarketData
from trader.strategies.country_momentum import CASH, COUNTRIES, CountryMomentum
from trader.strategy import Context

EARLY = [s for s in COUNTRIES if s not in ("EDEN", "ENOR")]  # the 15 markets listed by 1996


def _panel(
    growth: dict[str, float],
    start: str = "2010-01-04",
    end: str = "2015-06-30",
    first_valid: dict[str, str] | None = None,
) -> tuple[MarketData, TradingCalendar]:
    """Deterministic prices: each symbol compounds at its own constant daily rate."""
    cal = TradingCalendar.nyse(start="2009-01-01", end="2016-12-31")
    sessions = cal.sessions_between(start, end)
    t = np.arange(len(sessions))
    close = pd.DataFrame(
        {s: 100.0 * (1.0 + growth.get(s, 0.0)) ** t for s in [*COUNTRIES, CASH]},
        index=sessions,
    )
    for sym, first in (first_valid or {}).items():
        close.loc[close.index < pd.Timestamp(first), sym] = np.nan
    frames = {f: close.copy() for f in ("open", "high", "low", "close")}
    frames["volume"] = close.notna() * 1e6
    return MarketData(frames, rf=pd.Series(0.0, index=sessions)), cal


def _decide(strategy: CountryMomentum, data: MarketData, cal: TradingCalendar, when: str):
    view = data.upto_date(when)
    ctx = Context(now=view.now, data=view, positions={}, weights={}, equity=100_000.0, calendar=cal)
    return strategy.target_weights(ctx)


def _ranked_growth() -> dict[str, float]:
    """Distinct daily drifts; EARLY[0] grows fastest, EARLY[-1] slowest."""
    g = {s: 0.0010 - 0.0001 * k for k, s in enumerate(EARLY)}
    g[CASH] = 0.0001
    return g


NOT_YET = {"EDEN": "2020-01-02", "ENOR": "2020-01-02"}


def test_top_tercile_equal_weighted():
    data, cal = _panel(_ranked_growth(), first_valid=NOT_YET)
    w = _decide(CountryMomentum(), data, cal, "2013-12-31")
    # 15 eligible markets -> round(15/3) = 5 holdings at 20% each.
    assert w == pytest.approx({s: 0.2 for s in EARLY[:5]})


def test_top_fraction_rounding():
    data, cal = _panel(_ranked_growth(), first_valid=NOT_YET)
    w = _decide(CountryMomentum(top_fraction=0.2), data, cal, "2013-12-31")
    assert w == pytest.approx({s: 1 / 3 for s in EARLY[:3]})  # 15 * 0.2 = 3
    w = _decide(CountryMomentum(top_fraction=0.5), data, cal, "2013-12-31")
    assert w == pytest.approx({s: 1 / 8 for s in EARLY[:8]})  # 7.5 rounds half up to 8


def test_new_listing_needs_full_history():
    # EDEN grows fastest of all, but only starts trading in June 2013.
    growth = {**_ranked_growth(), "EDEN": 0.0030}
    data, cal = _panel(growth, first_valid={"EDEN": "2013-06-03", "ENOR": "2020-01-02"})
    strat = CountryMomentum()
    # End-June 2014: only 13 EDEN month-end closes (Jun 2013 .. Jun 2014) -> not eligible.
    w = _decide(strat, data, cal, "2014-06-30")
    assert "EDEN" not in w
    assert w == pytest.approx({s: 0.2 for s in EARLY[:5]})
    # Before its data exists it can never be selected.
    w = _decide(strat, data, cal, "2013-05-31")
    assert "EDEN" not in w
    # End-July 2014: 14 month-end closes -> eligible, 16 markets -> round(16/3) = 5.
    w = _decide(strat, data, cal, "2014-07-31")
    assert w == pytest.approx({s: 0.2 for s in ["EDEN", *EARLY[:4]]})


def test_skip_month_ignores_latest_month():
    growth = _ranked_growth()
    data, cal = _panel(growth, first_valid=NOT_YET)
    # EWU is flat for years, then jumps 50% during the latest month.
    close = data.close.copy()
    ewu = close["EWU"].copy()
    ewu.loc[:] = 100.0
    ewu.loc["2013-12-02":] = 150.0
    frames = {f: close.assign(EWU=ewu) for f in ("open", "high", "low", "close")}
    frames["volume"] = data.volume
    data = MarketData(frames, rf=data.rf)

    w = _decide(CountryMomentum(), data, cal, "2013-12-31")  # MOM2-12: jump is skipped
    assert "EWU" not in w
    w = _decide(CountryMomentum(skip_months=0), data, cal, "2013-12-31")  # MOM1-12
    assert "EWU" in w and len(w) == 5


def test_absolute_filter_sends_losing_slots_to_bil():
    # Only the two fastest markets rise; everything else falls. BIL accrues.
    growth = {s: -0.0003 - 0.0001 * k for k, s in enumerate(EARLY)}
    growth.update({EARLY[0]: 0.0010, EARLY[1]: 0.0008, CASH: 0.0001})
    data, cal = _panel(growth, first_valid=NOT_YET)
    w = _decide(CountryMomentum(), data, cal, "2013-12-31")
    assert w == pytest.approx({s: 0.2 for s in EARLY[:5]})
    w = _decide(CountryMomentum(abs_filter=True), data, cal, "2013-12-31")
    assert w == pytest.approx({EARLY[0]: 0.2, EARLY[1]: 0.2, CASH: 0.6})


def test_no_eligible_market_holds_bil():
    data, cal = _panel(_ranked_growth(), start="2010-01-04", end="2010-12-31")
    w = _decide(CountryMomentum(), data, cal, "2010-11-30")
    assert w == {CASH: 1.0}
