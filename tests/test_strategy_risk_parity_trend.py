"""Unit tests for the risk parity + trend filter strategy (Clare et al. 2016)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from trader.calendar import TradingCalendar
from trader.data.market_data import MarketData
from trader.strategies.risk_parity_trend import RiskParityTrend
from trader.strategy import Context

UNIVERSE = ["SPY", "EFA", "EEM", "IEF", "DBC", "VNQ", "BIL"]
START, END = "2010-01-01", "2011-06-30"


def _monthly_path(returns: list[float], p0: float = 100.0) -> np.ndarray:
    return p0 * np.cumprod([1.0, *(1.0 + np.asarray(returns))])


def _alternating(up: float, down: float, n: int) -> list[float]:
    return [up if k % 2 == 0 else down for k in range(n)]


def _context(month_closes: dict[str, np.ndarray], no_print_today: tuple[str, ...] = ()):
    """Daily panel whose close is flat within each month, so month-end closes are exact.

    Each path is aligned to the *last* months of the window (its last element is the
    current month); earlier months, and symbols without a path, are NaN. Symbols in
    ``no_print_today`` have no bar on the decision session.
    """
    cal = TradingCalendar.nyse(start="2009-01-01", end="2012-12-31")
    sessions = cal.sessions_between(START, END)
    months = sessions.to_period("M")
    uniq = months.unique()
    close = pd.DataFrame(np.nan, index=sessions, columns=UNIVERSE)
    for sym, path in month_closes.items():
        by_month = pd.Series(path, index=uniq[-len(path) :])
        close[sym] = by_month.reindex(months).to_numpy()
    for sym in no_print_today:
        close.loc[close.index[-1], sym] = np.nan
    frames = {f: close.copy() for f in ("open", "high", "low", "close")}
    frames["volume"] = close.notna().astype(float) * 1e6
    data = MarketData(frames)
    now = sessions[-1]
    return Context(
        now=now,
        data=data.upto(len(sessions) - 1),
        positions={},
        weights={},
        equity=100_000.0,
        calendar=cal,
    )


N_MONTHS = 18  # month-ends 2010-01 .. 2011-06; eligibility needs 13
BIL_PATH = _monthly_path([0.001] * (N_MONTHS - 1))


def test_inverse_vol_weights_and_trend_filter():
    # SPY and IEF trend up; IEF's returns are exactly half of SPY's, so its volatility
    # is half and its inverse-vol weight twice SPY's. EEM has SPY's volatility but
    # trends down, so its risk-parity weight goes to BIL.
    n = N_MONTHS - 1
    ctx = _context(
        {
            "SPY": _monthly_path(_alternating(0.04, -0.02, n)),
            "IEF": _monthly_path(_alternating(0.02, -0.01, n)),
            "EEM": _monthly_path(_alternating(-0.04, 0.02, n)),
            "BIL": BIL_PATH,
        }
    )
    w = RiskParityTrend().target_weights(ctx)
    assert set(w) == {"SPY", "IEF", "BIL"}
    assert w["SPY"] == pytest.approx(0.25)
    assert w["IEF"] == pytest.approx(0.50)
    assert w["BIL"] == pytest.approx(0.25)
    assert sum(w.values()) == pytest.approx(1.0)


def test_all_assets_below_sma_goes_fully_to_bil():
    n = N_MONTHS - 1
    ctx = _context(
        {
            "SPY": _monthly_path(_alternating(-0.04, 0.02, n)),
            "IEF": _monthly_path(_alternating(-0.02, 0.01, n)),
            "BIL": BIL_PATH,
        }
    )
    assert RiskParityTrend().target_weights(ctx) == pytest.approx({"BIL": 1.0})


def test_close_equal_to_sma_is_not_in_trend():
    # SPY moves for eight months, then sits at exactly 100 for ten: the close equals its
    # 10-month SMA (the rule needs close > SMA) while its 12-month volatility is non-zero.
    spy = np.array([90.0, 95.0, 92.0, 97.0, 94.0, 99.0, 96.0, 101.0] + [100.0] * 10)
    ctx = _context({"SPY": spy, "IEF": _monthly_path([0.01, -0.005] * 8 + [0.01]), "BIL": BIL_PATH})
    w = RiskParityTrend().target_weights(ctx)
    assert "SPY" not in w
    assert set(w) == {"IEF", "BIL"}


def test_assets_without_enough_history_get_no_weight():
    # DBC exists but has only 12 month-end closes (needs 13); VNQ has no data at all;
    # EFA has data but none on the decision day. Weights are computed over the
    # assets that are available, and the rest stays in BIL.
    n = N_MONTHS - 1
    ctx = _context(
        {
            "SPY": _monthly_path(_alternating(0.04, -0.02, n)),
            "IEF": _monthly_path(_alternating(0.02, -0.01, n)),
            "DBC": _monthly_path(_alternating(0.03, -0.01, 11)),
            "EFA": _monthly_path(_alternating(0.03, -0.01, n)),
            "BIL": BIL_PATH,
        },
        no_print_today=("EFA",),
    )
    w = RiskParityTrend().target_weights(ctx)
    assert set(w) == {"SPY", "IEF"}
    assert w["SPY"] == pytest.approx(1 / 3)
    assert w["IEF"] == pytest.approx(2 / 3)


def test_asset_becomes_eligible_with_thirteen_month_ends():
    n = N_MONTHS - 1
    ctx = _context(
        {
            "SPY": _monthly_path(_alternating(0.04, -0.02, n)),
            "DBC": _monthly_path(_alternating(0.04, -0.02, 12)),  # 13 month-end closes
            "BIL": BIL_PATH,
        }
    )
    w = RiskParityTrend().target_weights(ctx)
    assert w == pytest.approx({"SPY": 0.5, "DBC": 0.5})


def test_missing_bil_leaves_remainder_uninvested():
    n = N_MONTHS - 1
    ctx = _context(
        {
            "SPY": _monthly_path(_alternating(0.04, -0.02, n)),
            "EEM": _monthly_path(_alternating(-0.04, 0.02, n)),
        }
    )
    w = RiskParityTrend().target_weights(ctx)
    assert w == pytest.approx({"SPY": 0.5})
