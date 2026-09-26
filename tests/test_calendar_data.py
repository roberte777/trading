from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from trader.calendar import TradingCalendar
from trader.data.loader import clean_bars, risk_free_series, splice, tbill_index
from trader.strategy import MonthEnd, MonthStart, WeekEnd


@pytest.fixture(scope="module")
def cal():
    return TradingCalendar.nyse(start="2019-01-01", end="2026-12-31")


def test_month_end_and_holidays(cal):
    assert cal.is_month_end("2024-05-31")
    assert not cal.is_session("2024-07-04")
    assert cal.next_session("2024-07-03") == pd.Timestamp("2024-07-05")
    # Good Friday 2024-03-29 is a holiday, so March ends on the 28th.
    assert cal.is_month_end("2024-03-28")
    assert cal.session_of_month("2024-04-01") == 1
    assert cal.sessions_left_in_month("2024-03-26") == 2


def test_schedules(cal):
    assert MonthEnd().is_rebalance(pd.Timestamp("2024-03-28"), cal)
    assert MonthEnd(offset=1).is_rebalance(pd.Timestamp("2024-03-27"), cal)
    assert MonthStart(2).is_rebalance(pd.Timestamp("2024-04-02"), cal)
    assert WeekEnd().is_rebalance(pd.Timestamp("2024-03-28"), cal)  # Friday was a holiday
    assert MonthEnd(months=(3, 6, 9, 12)).is_rebalance(pd.Timestamp("2024-06-28"), cal)
    assert not MonthEnd(months=(3, 6, 9, 12)).is_rebalance(pd.Timestamp("2024-05-31"), cal)


def _bars(dates, closes):
    idx = pd.DatetimeIndex(dates)
    c = np.asarray(closes, dtype=float)
    return pd.DataFrame({"open": c, "high": c, "low": c, "close": c, "volume": 1.0}, index=idx)


def test_splice_uses_proxy_returns_before_inception():
    proxy = _bars(["2020-01-01", "2020-01-02", "2020-01-03", "2020-01-06"], [10, 11, 12, 13])
    primary = _bars(["2020-01-03", "2020-01-06"], [120, 130])
    out, mask = splice(primary, proxy)
    assert list(out.index) == list(proxy.index)
    assert out["close"].tolist() == pytest.approx([100, 110, 120, 130])
    assert mask.tolist() == [True, True, False, False]
    assert np.isnan(out["volume"].iloc[0])


def test_clean_bars_repairs_ohlc():
    df = _bars(["2020-01-01", "2020-01-02", "2020-01-03"], [10, 11, -1])
    df.loc["2020-01-02", "high"] = 5.0
    out = clean_bars(df, "X")
    assert len(out) == 2
    assert out.loc["2020-01-02", "high"] == 11.0


def test_tbill_index_and_rf_are_causal():
    idx = pd.bdate_range("2020-01-01", periods=5)
    irx = pd.DataFrame({"close": [5.0, 5.0, 10.0, 10.0, 10.0]}, index=idx)
    rf = risk_free_series(irx, idx)
    assert rf.iloc[0] == 0.0
    assert rf.iloc[2] == pytest.approx(0.05 / 252)  # yesterday's 5%, not today's 10%
    assert rf.iloc[3] == pytest.approx(0.10 / 252)
    tb = tbill_index(irx, idx, fee=0.0)
    assert tb["close"].pct_change().iloc[3] == pytest.approx(0.10 / 252)
