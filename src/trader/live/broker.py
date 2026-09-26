"""Broker interface used by the live runner, plus a file-backed local simulator.

The runner only talks to this interface, so the Alpaca adapter stays thin and the
runner can be tested against an in-memory broker.
"""

from __future__ import annotations

import json
import os
import tempfile
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from trader.calendar import TradingCalendar
from trader.execution.costs import CostModel

NY = ZoneInfo("America/New_York")


def now_ny() -> datetime:
    return datetime.now(NY)


@dataclass(frozen=True)
class AccountSnapshot:
    equity: float
    cash: float
    buying_power: float
    trading_blocked: bool = False


@dataclass(frozen=True)
class OrderTicket:
    symbol: str
    qty: float  # signed: > 0 buy, < 0 sell
    time_in_force: str  # "opg" | "cls" | "day"
    client_order_id: str


@dataclass(frozen=True)
class OrderStatus:
    id: str
    client_order_id: str
    symbol: str
    qty: float  # signed
    filled_qty: float  # signed, same sign as qty
    filled_avg_price: float | None
    status: str
    time_in_force: str = "day"
    submitted_at: str | None = None

    @property
    def is_open(self) -> bool:
        return self.status in {
            "new",
            "accepted",
            "pending_new",
            "partially_filled",
            "held",
            "accepted_for_bidding",
            "pending_replace",
        }


@dataclass(frozen=True)
class Dividend:
    id: str
    symbol: str
    date: str
    per_share: float


class OrderRejected(Exception):
    def __init__(
        self,
        message: str,
        *,
        wash_trade: bool = False,
        auction_not_allowed: bool = False,
        duplicate: bool = False,
    ) -> None:
        super().__init__(message)
        self.wash_trade = wash_trade
        self.auction_not_allowed = auction_not_allowed
        self.duplicate = duplicate


class Broker(ABC):
    name = "broker"

    @abstractmethod
    def account(self) -> AccountSnapshot: ...

    @abstractmethod
    def positions(self) -> dict[str, float]:
        """Account-level positions, symbol -> signed shares."""

    @abstractmethod
    def submit(self, ticket: OrderTicket) -> OrderStatus: ...

    @abstractmethod
    def orders(self, prefix: str, after: str | None = None) -> list[OrderStatus]:
        """All orders (open and closed) whose client_order_id starts with ``prefix``."""

    @abstractmethod
    def cancel(self, order_id: str) -> None: ...

    def dividends(self, after: str | None = None) -> list[Dividend]:
        """Cash dividends paid to the account (per share), newest last."""
        return []


# ---------------------------------------------------------------------------------------
class LocalBroker(Broker):
    """A file-backed simulated account for forward tests without Alpaca keys.

    Orders placed before the open (``day``/``opg``) fill at that session's open;
    later ones at the next session's open. ``cls`` orders placed before 15:50 ET
    fill at that session's close. Fills use the backtest cost model. Dividends are
    not simulated.
    """

    name = "local"

    def __init__(
        self,
        path: str | Path,
        price_source: Callable[[str, pd.Timestamp], tuple[float, float] | None],
        calendar: TradingCalendar,
        clock: Callable[[], datetime] = now_ny,
        initial_cash: float = 100_000.0,
        costs: CostModel | None = None,
    ) -> None:
        self.path = Path(path)
        self.price_source = price_source
        self.calendar = calendar
        self.clock = clock
        self.costs = costs or CostModel()
        if self.path.exists():
            self.state = json.loads(self.path.read_text())
        else:
            self.state = {"cash": initial_cash, "positions": {}, "orders": [], "seq": 0}
            self._save()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, prefix=".broker.")
        with os.fdopen(fd, "w") as f:
            json.dump(self.state, f, indent=1)
        os.replace(tmp, self.path)

    def _fill_session(self, tif: str) -> pd.Timestamp:
        now = self.clock()
        day = pd.Timestamp(now.date())
        cutoff = time(15, 50) if tif == "cls" else time(9, 30)
        if self.calendar.is_session(day) and now.time() < cutoff:
            return day
        return self.calendar.next_session(day)

    def _settle(self) -> None:
        changed = False
        for o in self.state["orders"]:
            if o["status"] != "accepted":
                continue
            px = self.price_source(o["symbol"], pd.Timestamp(o["fill_session"]))
            if px is None:
                continue
            ref = px[1] if o["time_in_force"] == "cls" else px[0]
            qty = o["qty"]
            held = self.state["positions"].get(o["symbol"], 0.0)
            if qty < 0:
                qty = max(qty, -held)
            price = self.costs.fill_price(ref, qty)
            self.state["cash"] -= qty * price + self.costs.fees(qty, price)
            self.state["positions"][o["symbol"]] = held + qty
            if abs(self.state["positions"][o["symbol"]]) < 1e-9:
                del self.state["positions"][o["symbol"]]
            o.update(status="filled", filled_qty=qty, filled_avg_price=price)
            changed = True
        if changed:
            self._save()

    def _last_close(self, symbol: str) -> float:
        day = self.calendar.latest_session_on_or_before(self.clock().date())
        for _ in range(10):
            px = self.price_source(symbol, day)
            if px is not None:
                return px[1]
            day = self.calendar.prev_session(day)
        return 0.0

    def account(self) -> AccountSnapshot:
        self._settle()
        value = sum(q * self._last_close(s) for s, q in self.state["positions"].items())
        eq = self.state["cash"] + value
        return AccountSnapshot(
            equity=eq, cash=self.state["cash"], buying_power=max(self.state["cash"], 0.0)
        )

    def positions(self) -> dict[str, float]:
        self._settle()
        return dict(self.state["positions"])

    def submit(self, ticket: OrderTicket) -> OrderStatus:
        for o in self.state["orders"]:
            if o["client_order_id"] == ticket.client_order_id:
                raise OrderRejected("client_order_id must be unique", duplicate=True)
        self.state["seq"] += 1
        order = {
            "id": f"local-{self.state['seq']}",
            "client_order_id": ticket.client_order_id,
            "symbol": ticket.symbol,
            "qty": ticket.qty,
            "filled_qty": 0.0,
            "filled_avg_price": None,
            "status": "accepted",
            "time_in_force": ticket.time_in_force,
            "fill_session": str(self._fill_session(ticket.time_in_force).date()),
            "submitted_at": self.clock().isoformat(timespec="seconds"),
        }
        self.state["orders"].append(order)
        self._save()
        return _status(order)

    def orders(self, prefix: str, after: str | None = None) -> list[OrderStatus]:
        self._settle()
        return [_status(o) for o in self.state["orders"] if o["client_order_id"].startswith(prefix)]

    def cancel(self, order_id: str) -> None:
        for o in self.state["orders"]:
            if o["id"] == order_id and o["status"] == "accepted":
                o["status"] = "canceled"
        self._save()


def _status(o: dict) -> OrderStatus:
    return OrderStatus(
        id=o["id"],
        client_order_id=o["client_order_id"],
        symbol=o["symbol"],
        qty=o["qty"],
        filled_qty=o.get("filled_qty") or 0.0,
        filled_avg_price=o.get("filled_avg_price"),
        status=o["status"],
        time_in_force=o.get("time_in_force", "day"),
        submitted_at=o.get("submitted_at"),
    )


@dataclass
class Ledger:
    """A strategy's own slice of a shared account, rebuilt from its own fills.

    Alpaca gives each user one live account, so several strategy containers may
    share it. Positions are account-level, so each container tracks the shares and
    cash that belong to it from the orders it placed (matched by client_order_id
    prefix) and the dividends paid on its shares.
    """

    cash: float
    positions: dict[str, float] = field(default_factory=dict)
    applied_orders: dict[str, float] = field(default_factory=dict)
    applied_dividends: list[str] = field(default_factory=list)
    fees: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))

    def apply_order(self, o: OrderStatus, costs: CostModel) -> bool:
        done = self.applied_orders.get(o.id, 0.0)
        delta = o.filled_qty - done
        if abs(delta) < 1e-12 or not o.filled_avg_price:
            return False
        fee = costs.fees(delta, o.filled_avg_price)
        self.cash -= delta * o.filled_avg_price + fee
        self.fees += fee
        new = self.positions.get(o.symbol, 0.0) + delta
        if abs(new) < 1e-9:
            self.positions.pop(o.symbol, None)
        else:
            self.positions[o.symbol] = new
        self.applied_orders[o.id] = o.filled_qty
        return True

    def apply_dividend(self, d: Dividend) -> bool:
        if d.id in self.applied_dividends:
            return False
        self.applied_dividends.append(d.id)
        shares = self.positions.get(d.symbol, 0.0)
        if shares:
            self.cash += shares * d.per_share
        return bool(shares)

    def equity(self, prices: dict[str, float]) -> float:
        return self.cash + sum(q * prices.get(s, 0.0) for s, q in self.positions.items())

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> Ledger:
        return cls(**d)
