from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from trader.calendar import TradingCalendar
from trader.data.market_data import FIELDS, MarketData
from trader.strategies.keller_daa import DefensiveAssetAllocation
from trader.strategy import Context

DECISION = "2011-06-30"  # last session of June 2011

# Daily log-growth (x 1e-4). Constant growth makes 13612W monotonic in the rate,
# so the ranking is known in advance. Both canaries (VWO, BND) are positive here.
BASE = {
    "SPY": 6,
    "IWM": 5,
    "QQQ": 12,
    "VGK": 1,
    "EWJ": 2,
    "VWO": 3,
    "VNQ": 10,
    "GSG": 11,
    "GLD": 9,
    "TLT": 4,
    "HYG": 7,
    "LQD": 8,
    "SHY": 0.5,
    "IEF": 0.7,
    "BND": 0.2,
}


def _ctx(growth: dict[str, float], first_valid: dict[str, str] | None = None, holes=()):
    cal = TradingCalendar.nyse(start="2008-01-01", end="2012-12-31")
    sessions = cal.sessions_between("2009-01-02", DECISION)
    t = np.arange(len(sessions), dtype=float)
    close = pd.DataFrame({s: 100.0 * np.exp(g * 1e-4 * t) for s, g in growth.items()}, sessions)
    for sym, first in (first_valid or {}).items():
        close.loc[: pd.Timestamp(first) - pd.Timedelta(days=1), sym] = np.nan
    for sym, day in holes:
        close.loc[pd.Timestamp(day), sym] = np.nan
    frames = {f: close.copy() for f in FIELDS}
    frames["volume"] = close.notna() * 1e6
    data = MarketData(frames)
    return Context(now=sessions[-1], data=data, positions={}, weights={}, equity=1e5, calendar=cal)


def _approx(weights: dict[str, float]):
    return pytest.approx(weights, abs=1e-12)


def test_both_canaries_good_holds_top_six_risky():
    w = DefensiveAssetAllocation().target_weights(_ctx(BASE))
    top6 = ["QQQ", "GSG", "VNQ", "GLD", "LQD", "HYG"]
    assert w == _approx({s: 1 / 6 for s in top6})


def test_one_bad_canary_moves_half_into_best_cash_asset():
    growth = {**BASE, "BND": -1, "LQD": -0.3}
    w = DefensiveAssetAllocation().target_weights(_ctx(growth))
    # CF = 1/2: top 3 risky at 1/6 each, 50% in the best of SHY/IEF/LQD (IEF).
    assert w == _approx({"QQQ": 1 / 6, "GSG": 1 / 6, "VNQ": 1 / 6, "IEF": 0.5})


def test_both_bad_canaries_go_fully_to_best_cash_asset_even_if_negative():
    growth = {**BASE, "VWO": -3, "BND": -1, "SHY": -0.5, "IEF": -2, "LQD": -3}
    w = DefensiveAssetAllocation().target_weights(_ctx(growth))
    assert w == _approx({"SHY": 1.0})


def test_risky_assets_are_not_trend_filtered():
    # Canaries good, but every risky asset except QQQ is falling: still top 6 held.
    growth = {s: -g for s, g in BASE.items()}
    growth.update({"QQQ": 2, "VWO": 3, "BND": 0.2})
    w = DefensiveAssetAllocation().target_weights(_ctx(growth))
    assert w == _approx({s: 1 / 6 for s in ["VWO", "QQQ", "VGK", "EWJ", "TLT", "IWM"]})


def test_lqd_as_risky_and_cash_asset_weights_are_summed():
    growth = {**BASE, "BND": -1, "LQD": 20}
    w = DefensiveAssetAllocation().target_weights(_ctx(growth))
    assert w == _approx({"LQD": 1 / 6 + 0.5, "QQQ": 1 / 6, "GSG": 1 / 6})


def test_symbol_without_twelve_months_of_data_gets_no_weight():
    # GSG has the second-best momentum but only 8 months of history: not ranked.
    w = DefensiveAssetAllocation().target_weights(_ctx(BASE, first_valid={"GSG": "2010-10-01"}))
    assert "GSG" not in w
    assert w == _approx({s: 1 / 6 for s in ["QQQ", "VNQ", "GLD", "LQD", "HYG", "SPY"]})


def test_missing_canary_counts_as_bad():
    w = DefensiveAssetAllocation().target_weights(_ctx(BASE, first_valid={"BND": "2011-01-03"}))
    assert w == _approx({"QQQ": 1 / 6, "GSG": 1 / 6, "VNQ": 1 / 6, "LQD": 0.5})


def test_missing_month_end_bar_is_carried_forward():
    # A proxy with no bar on a month-end (GC=F on day-after-Thanksgiving half days)
    # must not knock the symbol out for the next 12 months.
    ctx = _ctx(BASE, holes=[("GLD", "2010-12-31"), ("GLD", "2011-03-31")])
    w = DefensiveAssetAllocation().target_weights(ctx)
    assert w.get("GLD") == pytest.approx(1 / 6)


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        # T=5, CF = floor(0.5 * 5) / 5 = 0.4: top 3 at 1/5, 40% cash.
        ({"top_n": 5}, {"QQQ": 0.2, "GSG": 0.2, "VNQ": 0.2, "IEF": 0.4}),
        # B=1: one bad canary is already 100% cash.
        ({"breadth": 1}, {"IEF": 1.0}),
    ],
)
def test_easy_trading_rounding_and_breadth(params, expected):
    growth = {**BASE, "BND": -1, "LQD": -0.3}
    w = DefensiveAssetAllocation(**params).target_weights(_ctx(growth))
    assert w == _approx(expected)


def test_cash_fraction_table():
    daa = DefensiveAssetAllocation()
    assert [daa.cash_fraction(b) for b in (0, 1, 2)] == [0.0, 0.5, 1.0]
    t5 = DefensiveAssetAllocation(top_n=5)
    assert [t5.cash_fraction(b) for b in (0, 1, 2)] == pytest.approx([0.0, 0.4, 1.0])
