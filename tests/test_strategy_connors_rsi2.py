from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from trader.backtest.engine import BacktestConfig, Backtester
from trader.calendar import TradingCalendar
from trader.data.market_data import MarketData
from trader.strategies.connors_rsi2 import RISKY, ConnorsRSI2
from trader.strategy import Context

N = 260  # sessions of history handed to the strategy


def _rising(n: int = N, rate: float = 0.001) -> np.ndarray:
    """Steady uptrend: above its 200-day SMA, RSI(2) = 100, never a signal."""
    return 100.0 * (1.0 + rate) ** np.arange(n)


def _dip(moves: list[float], rate: float = 0.001, n: int = N) -> np.ndarray:
    """Uptrend whose last ``len(moves)`` sessions follow the given daily returns."""
    px = _rising(n - len(moves), rate)
    for m in moves:
        px = np.append(px, px[-1] * (1.0 + m))
    return px


def _market(paths: dict[str, np.ndarray]) -> tuple[MarketData, TradingCalendar]:
    cal = TradingCalendar.nyse(start="2000-01-01", end="2003-12-31")
    sessions = cal.sessions_between("2001-01-02", "2003-12-31")[:N]
    cols = {sym: paths.get(sym, _rising()) for sym in [*RISKY, "BIL"]}
    close = pd.DataFrame(cols, index=sessions)
    frames = {f: close.copy() for f in ("open", "high", "low", "close")}
    frames["volume"] = close * 0 + 1e6
    return MarketData(frames), cal


def _ctx(data: MarketData, cal, positions=None, weights=None) -> Context:
    return Context(
        now=data.index[-1],
        data=data,
        positions=positions or {},
        weights=weights or {},
        equity=100_000.0,
        calendar=cal,
    )


def test_entry_needs_rsi_below_5_and_close_above_200_sma():
    data, cal = _market(
        {
            # Three -2% days in an uptrend: RSI(2) ~ 1, still above the 200-day SMA.
            "XLE": _dip([-0.02, -0.02, -0.02]),
            # The same dip in a downtrend: below the 200-day SMA -> no entry.
            "XLF": _dip([-0.02, -0.02, -0.02], rate=-0.001),
            # A shallow dip after strong gains: RSI(2) stays well above 5.
            "XLK": _dip([-0.001], rate=0.01),
        }
    )
    w = ConnorsRSI2().target_weights(_ctx(data, cal))
    assert w == pytest.approx({"XLE": 0.2, "BIL": 0.8})


def test_more_candidates_than_slots_takes_lowest_rsi():
    # All seven dips stay above the 200-day SMA; the deeper the dip, the lower the RSI.
    drops = {"SPY": -0.010, "QQQ": -0.012, "IWM": -0.014, "DIA": -0.016, "XLB": -0.018}
    drops |= {"XLI": -0.020, "XLP": -0.022}
    data, cal = _market({s: _dip([d, d, d]) for s, d in drops.items()})
    w = ConnorsRSI2().target_weights(_ctx(data, cal))
    # Seven signals, five 20% slots: the five deepest dips (lowest RSI) win; no cash left.
    assert w == pytest.approx({s: 0.2 for s in ("IWM", "DIA", "XLB", "XLI", "XLP")})


def test_exit_above_5_sma_and_holdings_keep_current_weight():
    data, cal = _market(
        {
            # Held, rebounded above its 5-day SMA -> exit.
            "XLE": _dip([-0.03, -0.03, 0.05]),
            # Held, still below its 5-day SMA -> keep the current (drifted) weight.
            "XLF": _dip([-0.03, -0.03, -0.03]),
            # Entry still pending (in positions, not yet in weights) -> one slot.
            "XLK": _dip([-0.02, -0.02, -0.02]),
            # New signal fills one of the free slots.
            "XLV": _dip([-0.02, -0.02, -0.02]),
        }
    )
    ctx = _ctx(
        data,
        cal,
        positions={"XLE": 160.0, "XLF": 150.0, "XLK": 155.0, "BIL": 600.0},
        weights={"XLE": 0.21, "XLF": 0.19, "BIL": 0.60},
    )
    w = ConnorsRSI2().target_weights(ctx)
    assert w == pytest.approx({"XLF": 0.19, "XLK": 0.2, "XLV": 0.2, "BIL": 0.41})


def test_dust_position_does_not_occupy_a_slot():
    # Five 20% slots: four real holdings plus two stray shares of XLE (a leftover of a
    # scaled-down fill). The dust is not a holding, so the new XLV signal gets the slot.
    held = {s: 0.2 for s in ("SPY", "QQQ", "IWM", "DIA")}
    falling = {s: _dip([-0.01, -0.01, -0.01]) for s in held}  # below 5-day SMA: no exit
    data, cal = _market({**falling, "XLV": _dip([-0.02, -0.02, -0.02])})
    ctx = _ctx(data, cal, positions={**{s: 150.0 for s in held}, "XLE": 2.0}, weights=held)
    w = ConnorsRSI2().target_weights(ctx)
    assert w == pytest.approx({**held, "XLV": 0.2})


def test_symbol_without_enough_history_gets_no_weight():
    late = _dip([-0.02, -0.02, -0.02])
    late[:150] = np.nan  # listed 110 sessions ago: no 200-day SMA yet
    missing_today = _dip([-0.02, -0.02, -0.02])
    missing_today[-1] = np.nan  # no bar today
    data, cal = _market({"XLU": late, "XLY": missing_today})
    w = ConnorsRSI2().target_weights(_ctx(data, cal))
    assert w == pytest.approx({"BIL": 1.0})


def test_backtest_never_holds_a_symbol_before_its_data_exists():
    from .conftest import make_market_data

    strategy = ConnorsRSI2()
    data, cal = make_market_data(
        [*strategy.universe()],
        start="2001-01-02",
        end="2006-12-29",
        seed=3,
        first_valid={"XLK": "2004-06-01"},
    )
    res = Backtester(strategy, data, cal, BacktestConfig(start="2002-01-02")).run()
    first_ok = data.close["XLK"].first_valid_index()
    assert len(res.trades) > 0
    if "XLK" in res.weights:
        assert (res.weights.loc[: first_ok - pd.Timedelta(days=1), "XLK"] == 0).all()
    xlk = res.trades[res.trades["symbol"] == "XLK"]
    # An entry needs a full 200-day SMA of real closes after listing.
    assert xlk.empty or xlk["date"].min() > data.index[data.index.get_loc(first_ok) + 199]
    assert (res.targets.sum(axis=1) <= 1.0 + 1e-9).all()
