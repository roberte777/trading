"""Alpaca adapter (alpaca-py). Deliberately thin: all decisions live in the runner.

Credentials come from ``ALPACA_API_KEY`` / ``ALPACA_SECRET_KEY``. Paper trading is
the default. Trading real money requires both ``paper: false`` in the config (or
``ALPACA_PAPER=false``) *and* ``TRADER_ALLOW_LIVE=yes``.

Notes from Alpaca's docs that shape this adapter:

* ``opg``/``cls`` auction orders must arrive before 9:28 / 15:50 ET and may be
  restricted to certain account tiers. The runner falls back to ``day`` market
  orders queued before the open when an auction order is refused.
* Fractional and notional orders are only accepted with ``time_in_force=day``.
* ``client_order_id`` must be unique per account (<= 128 chars). The runner
  derives it deterministically, so a crashed and restarted container cannot
  double-submit.
* Positions are account-level. Several strategies sharing one account must run
  in ``account_mode: shared`` (see ``Ledger``).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime

from trader.live.broker import (
    AccountSnapshot,
    Broker,
    Dividend,
    OrderRejected,
    OrderStatus,
    OrderTicket,
)

log = logging.getLogger(__name__)


def _f(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def _enum(x) -> str:
    return str(getattr(x, "value", x)).lower()


class AlpacaBroker(Broker):
    name = "alpaca"

    def __init__(
        self, paper: bool = True, api_key: str | None = None, secret_key: str | None = None
    ) -> None:
        from alpaca.trading.client import TradingClient

        api_key = api_key or os.environ.get("ALPACA_API_KEY")
        secret_key = secret_key or os.environ.get("ALPACA_SECRET_KEY")
        if not api_key or not secret_key:
            raise RuntimeError("set ALPACA_API_KEY and ALPACA_SECRET_KEY")
        if not paper and os.environ.get("TRADER_ALLOW_LIVE", "").lower() != "yes":
            raise RuntimeError(
                "refusing to trade a live account: set TRADER_ALLOW_LIVE=yes to confirm"
            )
        self.paper = paper
        self.client = TradingClient(api_key, secret_key, paper=paper)

    def account(self) -> AccountSnapshot:
        a = self.client.get_account()
        return AccountSnapshot(
            equity=_f(a.equity),
            cash=_f(a.cash),
            buying_power=_f(a.buying_power),
            trading_blocked=bool(a.trading_blocked or a.account_blocked),
        )

    def positions(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for p in self.client.get_all_positions():
            qty = abs(_f(p.qty))
            out[p.symbol] = -qty if _enum(p.side) == "short" else qty
        return out

    def submit(self, ticket: OrderTicket) -> OrderStatus:
        from alpaca.common.exceptions import APIError
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest

        qty = abs(ticket.qty)
        req = MarketOrderRequest(
            symbol=ticket.symbol,
            # Whole-share sizing keeps qty integral, which auction orders require.
            qty=int(qty) if float(qty).is_integer() else qty,
            side=OrderSide.BUY if ticket.qty > 0 else OrderSide.SELL,
            time_in_force=TimeInForce(ticket.time_in_force),
            client_order_id=ticket.client_order_id,
        )
        try:
            return self._status(self.client.submit_order(req))
        except APIError as err:
            msg = str(err).lower()
            raise OrderRejected(
                str(err),
                wash_trade="wash trade" in msg,
                auction_not_allowed=ticket.time_in_force in {"opg", "cls"}
                and (
                    "not allowed" in msg
                    or "not permitted" in msg
                    or "not supported" in msg
                    or "time_in_force" in msg
                ),
                duplicate="client_order_id" in msg and "unique" in msg,
            ) from err

    def orders(self, prefix: str, after: str | None = None) -> list[OrderStatus]:
        from alpaca.trading.enums import QueryOrderStatus
        from alpaca.trading.requests import GetOrdersRequest

        req = GetOrdersRequest(
            status=QueryOrderStatus.ALL,
            limit=500,
            after=datetime.fromisoformat(after) if after else None,
            direction="asc",
        )
        return [
            self._status(o)
            for o in self.client.get_orders(req)
            if (o.client_order_id or "").startswith(prefix)
        ]

    def cancel(self, order_id: str) -> None:
        self.client.cancel_order_by_id(order_id)

    def dividends(self, after: str | None = None) -> list[Dividend]:
        params = {"after": after} if after else {}
        rows = self.client.get("/account/activities/DIV", params) or []
        out = []
        for r in rows:
            per_share = _f(r.get("per_share_amount"))
            if not per_share and _f(r.get("qty")):
                per_share = _f(r.get("net_amount")) / _f(r.get("qty"))
            out.append(
                Dividend(
                    id=str(r.get("id")),
                    symbol=str(r.get("symbol")),
                    date=str(r.get("date")),
                    per_share=per_share,
                )
            )
        return out

    @staticmethod
    def _status(o) -> OrderStatus:
        sign = -1.0 if _enum(o.side) == "sell" else 1.0
        return OrderStatus(
            id=str(o.id),
            client_order_id=o.client_order_id or "",
            symbol=o.symbol,
            qty=sign * _f(o.qty),
            filled_qty=sign * _f(o.filled_qty),
            filled_avg_price=_f(o.filled_avg_price) or None,
            status=_enum(o.status),
            time_in_force=_enum(o.time_in_force),
            submitted_at=o.submitted_at.isoformat() if getattr(o, "submitted_at", None) else None,
        )
