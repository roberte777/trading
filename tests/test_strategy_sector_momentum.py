"""Hand-built panels where the correct sector ranking is known in advance."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from trader.calendar import TradingCalendar
from trader.data.market_data import MarketData
from trader.strategies.sector_momentum import SECTORS, SectorMomentum
from trader.strategy import Context

MONTHS = pd.period_range("2003-01", "2004-08", freq="M")
THIRD = pytest.approx(1 / 3)


def _path(breaks: dict[str, float]) -> pd.Series:
    """Monthly price level: each breakpoint's value holds until the next one (NaN before the first)."""
    s = pd.Series(np.nan, index=MONTHS)
    for month, value in breaks.items():
        s[pd.Period(month, freq="M")] = value
    return s.ffill()


def _panel(overrides: dict[str, dict[str, float]]) -> tuple[MarketData, TradingCalendar]:
    """Every session in a month closes at that month's level, so month-end closes are exact."""
    cal = TradingCalendar.nyse(start="2002-01-01", end="2005-12-31")
    sessions = cal.sessions_between("2003-01-02", "2004-08-31")
    months = sessions.to_period("M")
    flat = {"2003-01": 100.0}
    paths = {sym: overrides.get(sym, flat) for sym in [*SECTORS, "BIL", "SPY"]}
    close = pd.DataFrame(
        {sym: _path(b).reindex(months).to_numpy() for sym, b in paths.items()}, index=sessions
    )
    frames = {f: close.copy() for f in ("open", "high", "low", "close")}
    frames["volume"] = pd.DataFrame(1e6, index=sessions, columns=close.columns)
    return MarketData(frames), cal


def _decide(strategy: SectorMomentum, data: MarketData, cal: TradingCalendar, when: str):
    i = int(data.index.get_loc(pd.Timestamp(when)))
    ctx = Context(
        now=data.index[i],
        data=data.upto(i),
        positions={},
        weights={},
        equity=100_000.0,
        calendar=cal,
    )
    return strategy.target_weights(ctx)


# Six-month returns to 2004-06-30: XLF +50% (all in June), XLK +30%, XLE +20%, XLV +10%,
# XLU -5% (but +90% over twelve months), everything else 0%. XLRE never lists; XLC lists
# in Feb 2004 and triples by August.
BASE = {
    "XLU": {"2003-01": 100.0, "2003-07": 200.0, "2004-06": 190.0},
    "XLK": {"2003-01": 100.0, "2004-01": 130.0},
    "XLE": {"2003-01": 100.0, "2004-01": 120.0},
    "XLV": {"2003-01": 100.0, "2004-01": 110.0},
    "XLF": {"2003-01": 100.0, "2004-06": 150.0},
    "XLC": {"2004-02": 100.0, "2004-03": 150.0, "2004-08": 300.0},
    "XLRE": {},
}


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        # Published defaults: 6-month return, no skip -> the June jump in XLF counts.
        ({}, {"XLF", "XLK", "XLE"}),
        # Skip the latest month: ranked on Nov 2003 -> May 2004, so XLF's jump is ignored.
        ({"skip_months": 1}, {"XLK", "XLE", "XLV"}),
        # Twelve-month lookback picks up XLU's 2003 rally.
        ({"lookback_months": 12}, {"XLU", "XLF", "XLK"}),
    ],
)
def test_holds_top_three_by_trailing_return(params, expected):
    data, cal = _panel(BASE)
    weights = _decide(SectorMomentum(**params), data, cal, "2004-06-30")
    assert set(weights) == expected
    assert all(w == THIRD for w in weights.values())


def test_top_n_changes_the_number_of_holdings():
    data, cal = _panel(BASE)
    weights = _decide(SectorMomentum(top_n=2), data, cal, "2004-06-30")
    assert weights == {"XLF": 0.5, "XLK": 0.5}


def test_new_sector_needs_lookback_plus_one_month_ends():
    data, cal = _panel(BASE)
    strategy = SectorMomentum()
    # June 2004: XLC has only 5 month-end closes (Feb-Jun) and XLRE has none -> never held.
    june = _decide(strategy, data, cal, "2004-06-30")
    assert "XLC" not in june and "XLRE" not in june
    # August 2004: XLC has 7 month-end closes and the best 6-month return (+200%).
    august = _decide(strategy, data, cal, "2004-08-31")
    assert august["XLC"] == THIRD
    assert "XLRE" not in august
    assert sum(august.values()) == pytest.approx(1.0)


def test_unfilled_slots_go_to_bil():
    only_two = {s: {} for s in SECTORS if s not in ("XLK", "XLE")}
    data, cal = _panel({**BASE, **only_two})
    weights = _decide(SectorMomentum(), data, cal, "2004-06-30")
    assert weights == {"XLK": THIRD, "XLE": THIRD, "BIL": THIRD}


def test_trend_filter_moves_to_bil_when_spy_below_ten_month_sma():
    falling = {**BASE, "SPY": {"2003-01": 200.0, "2004-01": 150.0, "2004-06": 120.0}}
    data, cal = _panel(falling)
    assert _decide(SectorMomentum(trend_filter=True), data, cal, "2004-06-30") == {"BIL": 1.0}
    # The filter is off by default, and SPY itself is never held.
    assert set(_decide(SectorMomentum(), data, cal, "2004-06-30")) == {"XLF", "XLK", "XLE"}

    rising = {**BASE, "SPY": {"2003-01": 100.0, "2004-01": 150.0}}
    data, cal = _panel(rising)
    weights = _decide(SectorMomentum(trend_filter=True), data, cal, "2004-06-30")
    assert set(weights) == {"XLF", "XLK", "XLE"}
