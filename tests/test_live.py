from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from trader.backtest.engine import BacktestConfig, Backtester
from trader.config import ExecutionConfig, LiveConfig, RunConfig
from trader.execution.costs import CostModel
from trader.live.broker import (
    NY,
    AccountSnapshot,
    Broker,
    Dividend,
    Ledger,
    LocalBroker,
    OrderRejected,
    OrderStatus,
    OrderTicket,
)
from trader.live.runner import LiveRunner
from trader.strategy import MonthEnd, Strategy

from .conftest import make_market_data

ZERO = CostModel(slippage_bps=0, sec_fee_rate=0, taf_per_share=0, taf_max=0, cat_per_share=0)


class TopTwo(Strategy):
    """Monthly: equal-weight the two best 3-month performers."""

    name = "test_top_two"

    @dataclass(frozen=True)
    class Params:
        lookback: int = 63

    def universe(self):
        return ["SPY", "TLT", "GLD", "EFA"]

    def warmup(self):
        return 70

    def schedule(self):
        return MonthEnd()

    def target_weights(self, ctx):
        close = ctx.close[self.universe()]
        mom = close.iloc[-1] / close.iloc[-1 - self.params.lookback] - 1
        best = mom.sort_values(ascending=False).index[:2]
        return {s: 0.5 for s in best}


class FakeBroker(Broker):
    """In-memory account that fills queued orders at a session's open like the backtester."""

    name = "fake"

    def __init__(self, data, cash=100_000.0):
        self.data = data
        self.cash = cash
        self.pos: dict[str, float] = {}
        self.book: list[dict] = []
        self.mark_session: pd.Timestamp | None = None
        self.reject: dict[str, OrderRejected] = {}
        self.divs: list[Dividend] = []
        self.seq = 0

    def account(self):
        eq = self.cash
        if self.mark_session is not None:
            close = self.data.close.loc[self.mark_session]
            eq += sum(q * close[s] for s, q in self.pos.items())
        return AccountSnapshot(equity=eq, cash=self.cash, buying_power=self.cash)

    def positions(self):
        return dict(self.pos)

    def submit(self, ticket: OrderTicket):
        if any(o["client_order_id"] == ticket.client_order_id for o in self.book):
            raise OrderRejected("client_order_id must be unique", duplicate=True)
        key = f"{ticket.symbol}:{ticket.time_in_force}"
        if key in self.reject:
            raise self.reject.pop(key)
        self.seq += 1
        o = {
            "id": str(self.seq),
            "client_order_id": ticket.client_order_id,
            "symbol": ticket.symbol,
            "qty": ticket.qty,
            "filled_qty": 0.0,
            "price": None,
            "status": "accepted",
            "tif": ticket.time_in_force,
        }
        self.book.append(o)
        return self._st(o)

    def _st(self, o):
        return OrderStatus(
            o["id"],
            o["client_order_id"],
            o["symbol"],
            o["qty"],
            o["filled_qty"],
            o["price"],
            o["status"],
            o["tif"],
        )

    def orders(self, prefix, after=None):
        return [self._st(o) for o in self.book if o["client_order_id"].startswith(prefix)]

    def cancel(self, order_id):
        for o in self.book:
            if o["id"] == order_id and o["status"] == "accepted":
                o["status"] = "canceled"

    def dividends(self, after=None):
        return list(self.divs)

    def fill_open(self, session):
        opens = self.data.open.loc[session]
        todo = [o for o in self.book if o["status"] == "accepted"]
        for o in [o for o in todo if o["qty"] < 0]:
            q = max(o["qty"], -self.pos.get(o["symbol"], 0.0))
            self._fill(o, q, opens[o["symbol"]])
        buys = [o for o in todo if o["qty"] > 0]
        need = sum(o["qty"] * opens[o["symbol"]] for o in buys)
        scale = 1.0 if need <= self.cash else self.cash / need
        for o in buys:
            q = o["qty"] if scale == 1.0 else float(math.floor(o["qty"] * scale))
            self._fill(o, q, opens[o["symbol"]])
        self.mark_session = session

    def _fill(self, o, q, px):
        self.cash -= q * px
        self.pos[o["symbol"]] = self.pos.get(o["symbol"], 0.0) + q
        if abs(self.pos[o["symbol"]]) < 1e-9:
            del self.pos[o["symbol"]]
        o.update(filled_qty=q, price=float(px), status="filled")


def _run_config(**live) -> RunConfig:
    return RunConfig(
        strategy="test_top_two",
        execution=ExecutionConfig(),
        live=LiveConfig(broker="fake", **live),
        backtest=dataclasses.replace(
            RunConfig(strategy="x").backtest,
            costs={
                "slippage_bps": 0,
                "sec_fee_rate": 0,
                "taf_per_share": 0,
                "taf_max": 0,
                "cat_per_share": 0,
            },
        ),
    )


def _runner(tmp_path, data, cal, broker, strategy=None, **live):
    run = _run_config(state_dir=str(tmp_path), **live)
    clock = lambda: datetime(2030, 1, 1, 8, 45, tzinfo=NY)  # noqa: E731
    return LiveRunner(
        run, strategy or TopTwo(), broker, cal, lambda s: data.upto_date(s), clock=clock
    )


@pytest.fixture(scope="module")
def market():
    return make_market_data(
        ["SPY", "TLT", "GLD", "EFA"], start="2004-01-02", end="2007-12-31", seed=3
    )


def test_live_runner_matches_backtest_exactly(tmp_path, market):
    data, cal = market
    start, end = pd.Timestamp("2005-01-03"), pd.Timestamp("2006-12-29")
    bt = Backtester(
        TopTwo(),
        data,
        cal,
        BacktestConfig(start=str(start.date()), end=str(end.date()), costs=ZERO),
    ).run()

    broker = FakeBroker(data)
    runner = _runner(tmp_path, data, cal, broker)
    live_targets = {}
    for day in cal.sessions_between(cal.next_session(start), end):
        rep = runner.run_once(day)
        assert rep.status != "error", rep.errors
        if rep.targets:
            live_targets[pd.Timestamp(rep.signal_session)] = rep.targets
        broker.fill_open(day)

    bt_targets = {d: {k: v for k, v in row.items() if v} for d, row in bt.targets.iterrows()}
    assert live_targets.keys() == bt_targets.keys()
    for d in bt_targets:
        assert live_targets[d] == pytest.approx(bt_targets[d])
    final_live = broker.account().equity
    assert final_live == pytest.approx(bt.equity.iloc[-1], rel=1e-9)
    bt_trades = bt.trades[["symbol", "qty"]].to_numpy().tolist()
    live_fills = [[o["symbol"], o["filled_qty"]] for o in broker.book if o["status"] == "filled"]
    assert live_fills == bt_trades


def test_idempotent_and_client_ids(tmp_path, market):
    data, cal = market
    broker = FakeBroker(data)
    runner = _runner(tmp_path, data, cal, broker)
    day = pd.Timestamp("2005-02-01")  # signal 2005-01-31 = month end
    first = runner.run_once(day)
    assert first.status == "submitted" and first.submitted
    assert all(o["client_order_id"].startswith("test-top-two-20050131-") for o in first.submitted)
    assert all(o["time_in_force"] == "day" for o in first.submitted)
    again = runner.run_once(day)
    assert again.status == "skipped"
    assert len(broker.book) == len(first.submitted)


def test_non_rebalance_day_does_nothing(tmp_path, market):
    data, cal = market
    broker = FakeBroker(data)
    runner = _runner(tmp_path, data, cal, broker, initial_rebalance=False)
    rep = runner.run_once(pd.Timestamp("2005-02-10"))
    assert rep.status == "skipped" and "not a rebalance day" in rep.reason
    assert broker.book == []


def test_dry_run_submits_nothing(tmp_path, market):
    data, cal = market
    broker = FakeBroker(data)
    runner = _runner(tmp_path, data, cal, broker)
    rep = runner.run_once(pd.Timestamp("2005-02-01"), dry_run=True)
    assert rep.status == "dry_run" and rep.orders
    assert broker.book == []


def test_stale_data_blocks_trading(tmp_path, market):
    data, cal = market
    broker = FakeBroker(data)
    run = _run_config(state_dir=str(tmp_path))
    stale = lambda s: data.upto_date(cal.prev_session(s))  # noqa: E731
    runner = LiveRunner(run, TopTwo(), broker, cal, stale)
    rep = runner.run_once(pd.Timestamp("2005-02-01"))
    assert rep.status == "error" and "stale data" in rep.errors[0]
    assert broker.book == []


def test_halt_file(tmp_path, market):
    data, cal = market
    broker = FakeBroker(data)
    runner = _runner(tmp_path, data, cal, broker)
    (runner.state.root / "HALT").write_text("stop")
    assert runner.run_once(pd.Timestamp("2005-02-01")).status == "halted"
    assert broker.book == []


def test_auction_fallback_and_wash_trade_retry(tmp_path, market):
    data, cal = market
    broker = FakeBroker(data)
    runner = _runner(tmp_path, data, cal, broker, order_style="auction")
    probe = runner.run_once(pd.Timestamp("2005-02-01"), dry_run=True)
    syms = [o["symbol"] for o in probe.orders]
    broker.reject[f"{syms[0]}:opg"] = OrderRejected(
        "opg orders not allowed for this account", auction_not_allowed=True
    )
    broker.reject[f"{syms[1]}:day"] = OrderRejected(
        "potential wash trade detected", wash_trade=True
    )
    rep = runner.run_once(pd.Timestamp("2005-02-01"))
    assert rep.status == "submitted"
    assert {o["time_in_force"] for o in rep.submitted} == {"day"}
    assert len(rep.retries) == 1 and rep.retries[0]["order"]["symbol"] == syms[1]
    done = runner.retry_pending()
    assert done and done[0]["client_order_id"].endswith("-r1")
    assert runner.state.data["pending_retries"] == []


def test_shared_account_ledger(tmp_path, market):
    data, cal = market
    broker = FakeBroker(data, cash=1_000_000.0)
    runner = _runner(tmp_path, data, cal, broker, account_mode="shared", allocation=50_000.0)
    rep = runner.run_once(pd.Timestamp("2005-02-01"))
    assert rep.equity == pytest.approx(50_000.0)
    notional = sum(abs(o["qty"]) * o["ref_price"] for o in rep.orders)
    assert notional <= 50_000.0
    broker.fill_open(pd.Timestamp("2005-02-01"))
    # Another strategy's fills in the same account must not leak into this ledger.
    broker.pos["TLT"] = broker.pos.get("TLT", 0.0) + 1000
    held = next(iter(broker.pos))
    broker.divs.append(Dividend(id="d1", symbol=held, date="2005-02-15", per_share=0.5))
    ledger = runner.sync()
    own = {o["symbol"]: o["filled_qty"] for o in broker.book}
    assert ledger.positions == pytest.approx(own)
    spent = sum(o["filled_qty"] * o["price"] for o in broker.book)
    div = 0.5 * own.get(held, 0.0)
    assert ledger.cash == pytest.approx(50_000.0 - spent + div)
    # Re-syncing is idempotent.
    assert runner.sync().cash == pytest.approx(ledger.cash)


def test_ledger_apply_is_incremental_for_partial_fills():
    led = Ledger(cash=1000.0)
    o1 = OrderStatus("1", "x-1", "SPY", 10, 4, 100.0, "partially_filled")
    o2 = OrderStatus("1", "x-1", "SPY", 10, 10, 100.0, "filled")
    assert led.apply_order(o1, ZERO) and led.positions["SPY"] == 4
    assert led.apply_order(o2, ZERO) and led.positions["SPY"] == 10
    assert not led.apply_order(o2, ZERO)
    assert led.cash == pytest.approx(0.0)


def test_run_windows_respect_half_days(tmp_path, market):
    data, cal_short = market
    from trader.calendar import TradingCalendar

    cal = TradingCalendar.nyse(start="2024-01-01", end="2026-12-31")
    runner = _runner(tmp_path, data, cal, FakeBroker(data))
    start, cutoff = runner.run_window(pd.Timestamp("2025-11-28"))
    assert (start.hour, start.minute, cutoff.hour, cutoff.minute) == (8, 45, 9, 29)
    run = dataclasses.replace(
        _run_config(state_dir=str(tmp_path)), execution=ExecutionConfig(mode="next_close")
    )
    close_runner = LiveRunner(run, TopTwo(), FakeBroker(data), cal, lambda s: data.upto_date(s))
    start, cutoff = close_runner.run_window(pd.Timestamp("2025-11-28"))  # 13:00 early close
    assert (start.hour, start.minute) == (12, 35)
    assert (cutoff.hour, cutoff.minute) == (12, 55)
    start, cutoff = close_runner.run_window(pd.Timestamp("2025-12-01"))
    assert (start.hour, start.minute, cutoff.hour, cutoff.minute) == (15, 35, 15, 55)


def test_local_broker_fills_at_the_open(tmp_path, market):
    data, cal = market
    now = {"t": datetime(2005, 2, 1, 8, 50, tzinfo=NY)}

    def prices(sym, session):
        if session not in data.index:
            return None
        return float(data.open.loc[session, sym]), float(data.close.loc[session, sym])

    b = LocalBroker(
        tmp_path / "b.json", prices, cal, clock=lambda: now["t"], initial_cash=10_000, costs=ZERO
    )
    b.submit(OrderTicket("SPY", 10, "day", "t-1"))
    assert b.positions() == {"SPY": 10}
    assert b.state["cash"] == pytest.approx(10_000 - 10 * data.open.loc["2005-02-01", "SPY"])
    now["t"] = datetime(2005, 2, 1, 10, 0, tzinfo=NY)
    b.submit(OrderTicket("SPY", -10, "day", "t-2"))
    order = b.state["orders"][-1]
    assert order["fill_session"] == "2005-02-02"
    with pytest.raises(OrderRejected):
        b.submit(OrderTicket("SPY", 1, "day", "t-2"))
    assert np.isfinite(b.account().equity)
