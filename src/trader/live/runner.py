"""Live runner: one strategy, one container, one schedule.

On each trading session ``D`` the runner does exactly what the backtester does at
the close of ``D - delay``:

1. Take market data up to and including the **signal session** ``S = D - delay``,
   refusing to trade if the data is stale.
2. Ask ``strategy.schedule()`` whether ``S`` is a rebalance day (plus an initial
   rebalance on first deployment, mirroring ``initial_rebalance`` in backtests).
3. Call ``strategy.target_weights`` with the same ``Context`` shape, and turn the
   targets into orders with the same ``plan_rebalance``, sized at the close of ``S``.
4. Submit orders that execute at ``D``'s open (``next_open``) or close (``next_close``).

State (last processed session, the shared-account ledger, pending retries) lives
in ``<state_dir>/<instance>/`` and is written atomically. Client order ids are
deterministic (``<instance>-<signal date>-<symbol>-<b|s>``), so a restart can
never double-submit.
"""

from __future__ import annotations

import json
import logging
import os
import signal as signals
import tempfile
import time as time_mod
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from trader.calendar import TradingCalendar
from trader.config import RunConfig
from trader.data.market_data import MarketData
from trader.execution.rebalance import Order, plan_rebalance, validate_weights
from trader.live.broker import NY, Broker, Ledger, OrderRejected, OrderStatus, OrderTicket, now_ny
from trader.strategy.base import Context, Strategy

log = logging.getLogger(__name__)

DataSource = Callable[[pd.Timestamp], MarketData]


class StateStore:
    """Tiny JSON state file with atomic writes."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "state.json"
        self.data: dict[str, Any] = json.loads(self.path.read_text()) if self.path.exists() else {}

    def save(self) -> None:
        fd, tmp = tempfile.mkstemp(dir=self.root, prefix=".state.")
        with os.fdopen(fd, "w") as f:
            json.dump(self.data, f, indent=1, default=str)
        os.replace(tmp, self.path)

    def write_report(self, session: pd.Timestamp, report: dict[str, Any]) -> Path:
        runs = self.root / "runs"
        runs.mkdir(exist_ok=True)
        p = runs / f"{session.date()}.json"
        p.write_text(json.dumps(report, indent=1, default=str))
        return p

    def heartbeat(self) -> None:
        (self.root / "heartbeat").write_text(datetime.now(NY).isoformat(timespec="seconds"))


@dataclass
class RunReport:
    instance: str
    session: str
    signal_session: str
    status: str  # skipped | no_change | planned | submitted | dry_run | halted | error
    reason: str = ""
    equity: float | None = None
    targets: dict[str, float] = field(default_factory=dict)
    positions: dict[str, float] = field(default_factory=dict)
    orders: list[dict[str, Any]] = field(default_factory=list)
    submitted: list[dict[str, Any]] = field(default_factory=list)
    retries: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class LiveRunner:
    def __init__(
        self,
        run: RunConfig,
        strategy: Strategy,
        broker: Broker,
        calendar: TradingCalendar,
        data_source: DataSource,
        clock: Callable[[], datetime] = now_ny,
    ) -> None:
        self.run = run
        self.cfg = run.live
        self.strategy = strategy
        self.broker = broker
        self.calendar = calendar
        self.data_source = data_source
        self.clock = clock
        self.instance = (
            os.environ.get("TRADER_INSTANCE_ID") or self.cfg.instance_id or strategy.name
        ).replace("_", "-")
        if len(self.instance) > 60:
            raise ValueError("instance_id must be <= 60 characters")
        state_root = Path(os.environ.get("TRADER_STATE_DIR") or self.cfg.state_dir) / self.instance
        self.state = StateStore(state_root)
        self.rules = run.execution.rules()
        self.costs = run.backtest_config().costs
        self.mode = run.execution.mode
        self.delay = run.execution.delay
        if self.cfg.account_mode not in {"dedicated", "shared"}:
            raise ValueError("live.account_mode must be 'dedicated' or 'shared'")
        if self.cfg.order_style not in {"market", "auction"}:
            raise ValueError("live.order_style must be 'market' or 'auction'")
        if self.rules.fractional and self.cfg.order_style == "auction":
            raise ValueError(
                "Alpaca auction (opg/cls) orders cannot be fractional; use order_style: market"
            )
        if self.cfg.account_mode == "shared" and not self.cfg.allocation:
            raise ValueError(
                "shared account_mode needs live.allocation (dollars assigned to this strategy)"
            )

    # -- timing -------------------------------------------------------------------------
    def _session_close(self, session: pd.Timestamp) -> time:
        close = self.calendar.close_time(session)
        return close.tz_convert(NY).time() if close is not None else time(16, 0)

    def run_window(self, session: pd.Timestamp) -> tuple[datetime, datetime]:
        """[start, cutoff) in New York time during which orders for ``session`` may be sent."""
        day = session.date()
        if self.mode == "next_open":
            start = self.cfg.resolved_run_at(self.mode)
            cutoff = time(9, 28) if self.cfg.order_style == "auction" else time(9, 29)
        else:
            close = datetime.combine(day, self._session_close(session))
            start = self.cfg.run_at or (close - timedelta(minutes=25)).time().strftime("%H:%M")
            cutoff = (
                close - timedelta(minutes=10 if self.cfg.order_style == "auction" else 5)
            ).time()
        h, m = map(int, str(start).split(":"))
        return datetime.combine(day, time(h, m), NY), datetime.combine(day, cutoff, NY)

    def time_in_force(self) -> str:
        if self.cfg.order_style == "auction":
            return "opg" if self.mode == "next_open" else "cls"
        return "day"

    # -- account view ---------------------------------------------------------------------
    def _ledger(self) -> Ledger | None:
        if self.cfg.account_mode != "shared":
            return None
        raw = self.state.data.get("ledger")
        return Ledger.from_dict(raw) if raw else Ledger(cash=float(self.cfg.allocation))

    def sync(self) -> Ledger | None:
        """Bring the shared-account ledger up to date with fills and dividends."""
        ledger = self._ledger()
        if ledger is None:
            return None
        after = self.state.data.get("last_sync")
        after = (pd.Timestamp(after) - pd.Timedelta(days=5)).isoformat() if after else None
        for o in self.broker.orders(prefix=self.instance + "-", after=after):
            ledger.apply_order(o, self.costs)
        for d in self.broker.dividends(after=ledger.created_at[:10]):
            ledger.apply_dividend(d)
        self.state.data["ledger"] = ledger.to_dict()
        self.state.data["last_sync"] = self.clock().isoformat(timespec="seconds")
        self.state.save()
        account = self.broker.positions()
        for sym, qty in ledger.positions.items():
            if account.get(sym, 0.0) + 1e-6 < qty:
                log.error(
                    "%s: ledger holds %.4f %s but the account only %.4f — another process sold our shares?",
                    self.instance,
                    qty,
                    sym,
                    account.get(sym, 0.0),
                )
        return ledger

    def _book(self, prices: dict[str, float]) -> tuple[dict[str, float], float]:
        """(positions, equity) as the strategy should see them."""
        universe = set(self.strategy.universe())
        ledger = self.sync()
        if ledger is not None:
            return dict(ledger.positions), ledger.equity(prices)
        positions = self.broker.positions()
        foreign = {s: q for s, q in positions.items() if s not in universe}
        if foreign and self.cfg.foreign_positions == "fail":
            raise RuntimeError(f"account holds symbols outside the universe: {sorted(foreign)}")
        own = {s: q for s, q in positions.items() if s in universe}
        equity = self.broker.account().equity * self.cfg.capital_fraction
        return own, equity

    # -- one run ------------------------------------------------------------------------------
    def signal_session(self, session: pd.Timestamp) -> pd.Timestamp:
        return self.calendar.shift(session, -self.delay)

    def is_decision(self, signal: pd.Timestamp) -> tuple[bool, str]:
        if self.cfg.initial_rebalance and not self.state.data.get("initialized"):
            return True, "initial rebalance"
        if self.strategy.schedule().is_rebalance(signal, self.calendar):
            return True, f"scheduled ({self.strategy.schedule().describe()})"
        return False, f"not a rebalance day ({self.strategy.schedule().describe()})"

    def halted(self) -> bool:
        return (
            os.environ.get("TRADER_HALT", "").lower() in {"1", "yes", "true"}
            or (self.state.root / "HALT").exists()
        )

    def run_once(
        self,
        session: pd.Timestamp | None = None,
        *,
        force: bool = False,
        dry_run: bool | None = None,
    ) -> RunReport:
        dry = self.cfg.dry_run if dry_run is None else dry_run
        today = pd.Timestamp(self.clock().date())
        session = (
            pd.Timestamp(session)
            if session is not None
            else self.calendar.latest_session_on_or_before(today)
        )
        if not self.calendar.is_session(session):
            raise ValueError(f"{session.date()} is not a trading session")
        signal = self.signal_session(session)
        report = RunReport(self.instance, str(session.date()), str(signal.date()), status="skipped")
        try:
            if self.halted():
                report.status, report.reason = "halted", "TRADER_HALT or HALT file present"
                return self._finish(session, report, record=False)
            decide, why = self.is_decision(signal)
            if force:
                decide, why = True, "forced"
            report.reason = why
            if self.state.data.get("last_signal") == str(signal.date()) and not force:
                report.status, report.reason = "skipped", "already processed this signal session"
                return self._finish(session, report, record=False)
            if not decide:
                self.sync()
                self.state.data["last_session"] = str(session.date())
                return self._finish(session, report)

            data = self.data_source(signal)
            stale = {
                s: data.close[s].last_valid_index()
                for s in self.strategy.universe()
                if data.close[s].last_valid_index() != signal
            }
            if data.index[-1] != signal or stale:
                detail = ", ".join(
                    f"{s} last {d.date() if d is not None else 'never'}" for s, d in stale.items()
                )
                raise RuntimeError(
                    f"stale data for signal session {signal.date()}: {detail or data.index[-1].date()}"
                )
            closes = data.close.iloc[-1]
            prices = {
                s: float(closes[s])
                for s in self.strategy.universe()
                if s in closes and pd.notna(closes[s])
            }
            positions, equity = self._book(prices)
            report.positions, report.equity = positions, equity
            weights = (
                {s: q * prices.get(s, 0.0) / equity for s, q in positions.items()}
                if equity > 0
                else {}
            )
            ctx = Context(
                now=signal,
                data=data,
                positions=positions,
                weights=weights,
                equity=equity,
                calendar=self.calendar,
            )
            targets = self.strategy.target_weights(ctx)
            if targets is None:
                report.status, report.reason = "no_change", "strategy returned None"
                self._mark_done(session, signal, dry)
                return self._finish(session, report)
            targets = validate_weights(targets, self.rules, set(self.strategy.universe()))
            report.targets = targets
            orders = plan_rebalance(targets, positions, prices, equity, self.rules)
            if self.cfg.account_mode == "shared":
                orders = self._fit_cash(orders, positions, prices, equity)
            report.orders = [asdict(o) for o in orders]
            traded = sum(o.notional for o in orders)
            if equity > 0 and traded / equity > self.cfg.max_turnover:
                raise RuntimeError(
                    f"turnover guard: {traded / equity:.2f}x equity exceeds {self.cfg.max_turnover}x"
                )
            if not orders:
                report.status = "no_change"
                self._mark_done(session, signal, dry)
                return self._finish(session, report)
            if dry:
                report.status = "dry_run"
                return self._finish(session, report)
            if self.broker.account().trading_blocked:
                raise RuntimeError("account is blocked from trading")
            self._cancel_stale()
            report.submitted, report.retries = self._submit(orders, signal)
            report.status = "submitted"
            self._mark_done(session, signal, dry)
            return self._finish(session, report)
        except Exception as err:
            log.exception("%s: run for %s failed", self.instance, session.date())
            report.status = "error"
            report.errors.append(f"{type(err).__name__}: {err}")
            return self._finish(session, report)

    def _fit_cash(
        self,
        orders: list[Order],
        positions: dict[str, float],
        prices: dict[str, float],
        equity: float,
    ) -> list[Order]:
        """Shared accounts: never spend more than the ledger's own cash."""
        ledger = self._ledger()
        cash = ledger.cash if ledger else equity
        proceeds = sum(-o.qty * o.ref_price for o in orders if o.qty < 0)
        buys = [o for o in orders if o.qty > 0]
        need = sum(o.notional for o in buys) * (1 + self.costs.slippage_bps / 1e4)
        budget = cash + proceeds
        if need <= budget or need <= 0:
            return orders
        scale = max(budget, 0.0) / need
        fitted = [o for o in orders if o.qty < 0]
        for o in buys:
            q = o.qty * scale
            q = int(q) if not self.rules.fractional else int(q * 1e6) / 1e6
            if q > 0:
                fitted.append(Order(o.symbol, float(q), o.ref_price, o.target_weight))
        return fitted

    def _cancel_stale(self) -> None:
        after = (pd.Timestamp(self.clock().date()) - pd.Timedelta(days=7)).isoformat()
        for o in self.broker.orders(prefix=self.instance + "-", after=after):
            if o.is_open:
                log.info("%s: cancelling stale order %s", self.instance, o.client_order_id)
                self.broker.cancel(o.id)

    def client_order_id(self, signal: pd.Timestamp, o: Order, attempt: int = 0) -> str:
        side = "b" if o.qty > 0 else "s"
        suffix = f"-r{attempt}" if attempt else ""
        return f"{self.instance}-{signal:%Y%m%d}-{o.symbol}-{side}{suffix}"[:128]

    def _submit(self, orders: list[Order], signal: pd.Timestamp) -> tuple[list[dict], list[dict]]:
        tif = self.time_in_force()
        submitted: list[dict] = []
        retries: list[dict] = []
        for o in orders:  # sells first (plan_rebalance ordering)
            ticket = OrderTicket(o.symbol, o.qty, tif, self.client_order_id(signal, o))
            try:
                st = self.broker.submit(ticket)
            except OrderRejected as rej:
                if rej.duplicate:
                    log.info("%s: %s already submitted", self.instance, ticket.client_order_id)
                    continue
                if rej.auction_not_allowed and tif != "day":
                    log.warning(
                        "%s: auction orders refused (%s); falling back to day market orders",
                        self.instance,
                        rej,
                    )
                    tif = "day"
                    ticket = OrderTicket(o.symbol, o.qty, tif, ticket.client_order_id)
                    try:
                        st = self.broker.submit(ticket)
                    except OrderRejected as rej2:
                        retries.append(self._retry_entry(o, signal, str(rej2)))
                        continue
                elif rej.wash_trade:
                    log.warning(
                        "%s: %s rejected as potential wash trade; will retry after the open",
                        self.instance,
                        ticket.client_order_id,
                    )
                    retries.append(self._retry_entry(o, signal, str(rej)))
                    continue
                else:
                    raise
            log.info(
                "%s: submitted %s %s %s (%s)",
                self.instance,
                "BUY" if o.qty > 0 else "SELL",
                abs(o.qty),
                o.symbol,
                tif,
            )
            submitted.append(_status_dict(st))
        if retries:
            self.state.data["pending_retries"] = retries
            self.state.save()
        return submitted, retries

    @staticmethod
    def _retry_entry(o: Order, signal: pd.Timestamp, why: str) -> dict:
        return {"order": asdict(o), "signal": str(signal.date()), "reason": why, "attempt": 0}

    def retry_pending(self) -> list[dict]:
        """Re-submit orders rejected earlier (e.g. wash-trade protection) as day market orders."""
        pending = self.state.data.get("pending_retries") or []
        still: list[dict] = []
        done: list[dict] = []
        for entry in pending:
            o = Order(**entry["order"])
            attempt = entry["attempt"] + 1
            ticket = OrderTicket(
                o.symbol,
                o.qty,
                "day",
                self.client_order_id(pd.Timestamp(entry["signal"]), o, attempt),
            )
            try:
                done.append(_status_dict(self.broker.submit(ticket)))
            except OrderRejected as rej:
                if attempt < 5 and (rej.wash_trade or rej.auction_not_allowed):
                    still.append({**entry, "attempt": attempt, "reason": str(rej)})
                else:
                    log.error("%s: giving up on %s: %s", self.instance, ticket.client_order_id, rej)
        self.state.data["pending_retries"] = still
        self.state.save()
        return done

    def _mark_done(self, session: pd.Timestamp, signal: pd.Timestamp, dry: bool) -> None:
        if dry:
            return
        self.state.data.update(
            last_signal=str(signal.date()),
            last_session=str(session.date()),
            initialized=True,
        )

    def _finish(self, session: pd.Timestamp, report: RunReport, record: bool = True) -> RunReport:
        payload = asdict(report)
        if record:
            self.state.data["last_report"] = {
                k: payload[k] for k in ("session", "signal_session", "status", "reason")
            }
            self.state.save()
            self.state.write_report(session, payload)
        level = logging.ERROR if report.status == "error" else logging.INFO
        log.log(
            level,
            "%s: %s %s — %s (%d orders)",
            self.instance,
            report.session,
            report.status,
            report.reason,
            len(report.orders),
        )
        return report

    # -- daemon ----------------------------------------------------------------------------------
    def run_forever(self, poll_seconds: float = 30.0) -> None:
        stop = {"flag": False}

        def _stop(*_):
            stop["flag"] = True
            log.info("%s: shutting down", self.instance)

        signals.signal(signals.SIGTERM, _stop)
        signals.signal(signals.SIGINT, _stop)
        log.info(
            "%s: live runner started — strategy=%s mode=%s style=%s account=%s broker=%s",
            self.instance,
            self.strategy.name,
            self.mode,
            self.cfg.order_style,
            self.cfg.account_mode,
            self.broker.name,
        )
        while not stop["flag"]:
            self.state.heartbeat()
            now = self.clock()
            day = pd.Timestamp(now.date())
            if self.calendar.is_session(day):
                start, cutoff = self.run_window(day)
                if start <= now < cutoff and self.state.data.get("last_session") != str(day.date()):
                    self.run_once(day)
                if self.state.data.get("pending_retries"):
                    open_at = datetime.combine(now.date(), time(9, 30), NY) + timedelta(
                        minutes=self.cfg.retry_after_open_minutes
                    )
                    if now >= open_at:
                        self.retry_pending()
            for _ in range(int(poll_seconds)):
                if stop["flag"]:
                    break
                time_mod.sleep(1)


def _status_dict(st: OrderStatus) -> dict:
    return asdict(st)
