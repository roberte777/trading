"""Turn target weights into orders. Shared verbatim by the backtester and the live
runner, so share rounding, bands and exits behave identically in both."""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping
from dataclasses import dataclass

log = logging.getLogger(__name__)

EPS = 1e-9


@dataclass(frozen=True)
class Order:
    symbol: str
    qty: float  # signed: > 0 buy, < 0 sell
    ref_price: float  # price used for sizing (last close)
    target_weight: float

    @property
    def side(self) -> str:
        return "buy" if self.qty > 0 else "sell"

    @property
    def notional(self) -> float:
        return abs(self.qty) * self.ref_price


@dataclass(frozen=True)
class RebalanceRules:
    fractional: bool = False
    #: Skip adjustments whose weight change is smaller than this (entries/exits always trade).
    rebalance_band: float = 0.0
    #: Skip orders smaller than this many dollars.
    min_order_value: float = 1.0
    #: Fraction of equity kept uninvested when sizing, to absorb overnight gaps.
    cash_buffer: float = 0.0
    max_gross: float = 1.0
    allow_short: bool = False


class WeightError(ValueError):
    pass


def validate_weights(
    targets: Mapping[str, float], rules: RebalanceRules, universe: set[str] | None = None
) -> dict[str, float]:
    """Check and clean strategy output: finite, allowed symbols, sign and gross limits."""
    clean: dict[str, float] = {}
    for sym, w in targets.items():
        w = float(w)
        if not math.isfinite(w):
            raise WeightError(f"non-finite weight for {sym}: {w}")
        if universe is not None and sym not in universe:
            raise WeightError(f"{sym} is not in the strategy universe")
        if w < -EPS and not rules.allow_short:
            raise WeightError(f"negative weight for {sym} but shorting is disabled")
        if abs(w) > EPS:
            clean[sym] = w
    gross = sum(abs(w) for w in clean.values())
    if gross > rules.max_gross + 1e-6:
        log.warning("gross weight %.4f exceeds limit %.2f; scaling down", gross, rules.max_gross)
        clean = {k: v * rules.max_gross / gross for k, v in clean.items()}
    return clean


def _round_shares(shares: float, fractional: bool) -> float:
    if fractional:
        # Alpaca accepts up to 9 decimals; truncate toward zero so we never overspend.
        return math.trunc(shares * 1e6) / 1e6
    return float(math.trunc(shares + (1e-9 if shares > 0 else -1e-9)))


def plan_rebalance(
    targets: Mapping[str, float],
    positions: Mapping[str, float],
    prices: Mapping[str, float],
    equity: float,
    rules: RebalanceRules | None = None,
) -> list[Order]:
    """Orders that move ``positions`` (shares) to ``targets`` (weights of ``equity``).

    Sells are listed before buys. Symbols without a valid price are skipped with a
    warning (the position is left as is).
    """
    rules = rules or RebalanceRules()
    if equity <= 0:
        raise ValueError(f"equity must be positive, got {equity}")
    investable = equity * (1.0 - rules.cash_buffer)
    orders: list[Order] = []
    for sym in sorted(set(targets) | {s for s, q in positions.items() if abs(q) > EPS}):
        w = float(targets.get(sym, 0.0))
        cur = float(positions.get(sym, 0.0))
        price = prices.get(sym)
        if price is None or not math.isfinite(price) or price <= 0:
            if abs(w) > EPS or abs(cur) > EPS:
                log.warning("no valid price for %s; leaving position unchanged", sym)
            continue
        tgt = 0.0 if abs(w) <= EPS else _round_shares(w * investable / price, rules.fractional)
        delta = tgt - cur
        if abs(delta) <= EPS:
            continue
        exiting = abs(tgt) <= EPS
        entering = abs(cur) <= EPS
        if not (exiting or entering):
            cur_w = cur * price / equity
            if abs(w - cur_w) < rules.rebalance_band:
                continue
        if not exiting and abs(delta) * price < rules.min_order_value:
            continue
        orders.append(Order(sym, delta, price, w))
    orders.sort(key=lambda o: (o.qty > 0, o.symbol))
    return orders
