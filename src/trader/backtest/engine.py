"""Event-driven daily backtester.

Timeline for each session ``t`` (mirrors what the live runner does):

1. **Financing** – overnight interest on cash (optional), margin interest, borrow fees.
2. **Fills** – orders decided ``delay`` sessions earlier fill at this session's open
   (``next_open``, i.e. market-on-open) or close (``next_close``, market-on-close),
   with adverse slippage and fees. Sells fill before buys; buys are scaled down if
   cash is short (no accidental leverage).
3. **Mark to market** at the close.
4. **Decision** – if the schedule says so, the strategy sees data up to and
   including this close (never later) and returns target weights, which the shared
   planner turns into whole-share orders sized at this close.

Signals at the close of ``t`` can therefore never trade at the close of ``t``.
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from trader.backtest.result import BacktestResult
from trader.calendar import TradingCalendar, to_session
from trader.data.market_data import MarketData
from trader.execution.costs import CostModel
from trader.execution.rebalance import Order, RebalanceRules, plan_rebalance, validate_weights
from trader.strategy.base import Context, Strategy

log = logging.getLogger(__name__)

EXECUTIONS = ("next_open", "next_close")
#: Sessions an order without a fill price is re-tried before it is abandoned.
MAX_CARRY = 5


@dataclass(frozen=True)
class BacktestConfig:
    start: str | None = None
    end: str | None = None
    initial_capital: float = 100_000.0
    #: ``next_open`` (market-on-open) or ``next_close`` (market-on-close).
    execution: str = "next_open"
    #: Sessions between the signal close and the fill (1 = next session).
    delay: int = 1
    costs: CostModel = field(default_factory=CostModel)
    rules: RebalanceRules = field(default_factory=RebalanceRules)
    #: Accrue the T-bill rate on idle cash. Off by default: Alpaca brokerage cash
    #: earns nothing, so strategies that want T-bill returns should hold BIL.
    cash_interest: bool = False
    #: Annual rate charged on negative cash (margin).
    margin_rate: float = 0.07
    #: Decide ``schedule_shift`` sessions before the schedule's nominal day
    #: (rebalance-timing-luck test).
    schedule_shift: int = 0
    #: Trade to the strategy's targets on the first session instead of waiting
    #: for the first scheduled rebalance.
    initial_rebalance: bool = True
    benchmark: str = "SPY"

    def __post_init__(self) -> None:
        if self.execution not in EXECUTIONS:
            raise ValueError(f"execution must be one of {EXECUTIONS}")
        if self.delay < 1:
            raise ValueError("delay must be >= 1 (a signal cannot trade at its own close)")


class Backtester:
    def __init__(
        self,
        strategy: Strategy,
        data: MarketData,
        calendar: TradingCalendar,
        config: BacktestConfig,
    ) -> None:
        self.strategy = strategy
        self.data = data.full()
        self.calendar = calendar
        self.config = config
        missing = [s for s in strategy.data_symbols() if s not in self.data.symbols]
        if missing:
            raise ValueError(f"data is missing symbols {missing}")

    # -- setup ---------------------------------------------------------------------
    def warmed_start(self) -> pd.Timestamp:
        """First session where every universe symbol has ``warmup`` sessions of history."""
        idx = self.data.index
        firsts = [self.data.first_valid(s) for s in self.strategy.data_symbols()]
        if any(f is None for f in firsts):
            raise ValueError("a strategy symbol has no data")
        i = int(idx.searchsorted(max(firsts))) + self.strategy.warmup()
        return idx[min(i, len(idx) - 1)]

    def _bounds(self) -> tuple[int, int]:
        idx = self.data.index
        warmed = self.warmed_start()
        if self.config.start is None:
            start = warmed
        else:
            start = to_session(self.config.start)
            if start < warmed:
                idx = self.data.index
                late = []
                for sym in self.strategy.data_symbols():
                    first = self.data.first_valid(sym)
                    ready_i = int(idx.searchsorted(first)) + self.strategy.warmup()
                    if ready_i >= len(idx) or idx[ready_i] > start:
                        late.append(f"{sym} (data from {first.date()})")
                log.info(
                    "%s: at the %s start these symbols lack %d sessions of history and must be "
                    "treated as not yet available: %s",
                    self.strategy.name,
                    start.date(),
                    self.strategy.warmup(),
                    ", ".join(late),
                )
        start_i = max(int(idx.searchsorted(start)), 1)
        end_i = (
            len(idx) - 1
            if self.config.end is None
            else int(idx.searchsorted(to_session(self.config.end), side="right")) - 1
        )
        if end_i <= start_i:
            raise ValueError("empty backtest window")
        return start_i, end_i

    def _is_decision(self, i: int, start_i: int) -> bool:
        if i == start_i and self.config.initial_rebalance:
            return True
        session = self.data.index[i]
        if self.config.schedule_shift:
            try:
                session = self.calendar.shift(session, self.config.schedule_shift)
            except IndexError:
                return False
        return self.strategy.schedule().is_rebalance(session, self.calendar)

    # -- main loop -------------------------------------------------------------------
    def run(self) -> BacktestResult:
        cfg, data, strat = self.config, self.data, self.strategy
        idx = data.index
        syms = data.symbols
        col = {s: j for j, s in enumerate(syms)}
        universe = set(strat.universe())
        n = len(syms)
        opens = data.to_numpy("open")
        closes = data.to_numpy("close")
        marks = data.close.ffill().to_numpy(dtype=float)
        rf = data.rf.to_numpy(dtype=float)
        fills = opens if cfg.execution == "next_open" else closes
        start_i, end_i = self._bounds()

        pos = np.zeros(n)
        cash = float(cfg.initial_capital)
        pending: dict[int, list[Order]] = defaultdict(list)
        carried: dict[int, int] = {}
        T = end_i - start_i + 1
        rec_equity = np.zeros(T)
        rec_cash = np.zeros(T)
        rec_weights = np.zeros((T, n))
        rec_traded = np.zeros(T)
        rec_fees = np.zeros(T)
        rec_slip = np.zeros(T)
        rec_financing = np.zeros(T)
        trades: list[dict] = []
        targets_log: list[tuple[pd.Timestamp, dict[str, float]]] = []
        prev_equity = cash

        for r, i in enumerate(range(start_i, end_i + 1)):
            now = idx[i]
            # 1. financing over the night before this session
            if r > 0:
                fin = 0.0
                if cash > 0 and cfg.cash_interest:
                    fin += cash * rf[i]
                elif cash < 0:
                    fin += cash * cfg.margin_rate / 252.0
                if cfg.costs.borrow_rate and (pos < 0).any():
                    short_value = -float(np.nansum(np.where(pos < 0, pos * marks[i - 1], 0.0)))
                    fin -= short_value * cfg.costs.borrow_rate / 252.0
                cash += fin
                rec_financing[r] = fin

            # 2. fills
            if i in pending:
                unfilled: list[Order] = []
                cash, traded, fees, slip = self._execute(
                    pending.pop(i), now, fills[i], marks[i - 1], pos, col, cash, trades, unfilled
                )
                rec_traded[r], rec_fees[r], rec_slip[r] = traded, fees, slip
                # No price for a symbol today (a data gap or halt): try again next session,
                # as a live order would be re-sent, for up to MAX_CARRY sessions.
                for o in unfilled:
                    tries = carried.get(id(o), 0) + 1
                    if tries <= MAX_CARRY and i + 1 <= end_i:
                        carried[id(o)] = tries
                        pending[i + 1].append(o)
                    else:
                        log.warning(
                            "%s: giving up on %s order after %d sessions",
                            strat.name,
                            o.symbol,
                            tries,
                        )

            # 3. mark to market
            held = pos != 0
            value = np.where(held, pos * marks[i], 0.0)
            if np.isnan(value).any():
                bad = [syms[j] for j in np.flatnonzero(np.isnan(value))]
                raise RuntimeError(f"holding {bad} without a price on {now.date()}")
            equity = cash + float(value.sum())
            if equity <= 0:
                raise RuntimeError(f"{strat.name}: equity went non-positive on {now.date()}")
            rec_equity[r], rec_cash[r] = equity, cash
            rec_weights[r] = value / equity
            rec_traded[r] /= prev_equity
            prev_equity = equity

            # 4. decide
            if i + cfg.delay <= end_i and self._is_decision(i, start_i):
                projected = pos.copy()
                for queued in pending.values():
                    for o in queued:
                        projected[col[o.symbol]] += o.qty
                if not cfg.rules.allow_short:
                    # Fills can come in smaller than ordered (cash scaling, sell caps), so
                    # a queued sell can overshoot the eventual holding. A long-only book
                    # never goes below zero; don't let the planner "cover" a phantom short.
                    projected = np.maximum(projected, 0.0)
                positions = {syms[j]: float(projected[j]) for j in np.flatnonzero(projected)}
                weights = {syms[j]: float(value[j] / equity) for j in np.flatnonzero(held)}
                ctx = Context(
                    now=now,
                    data=data.upto(i),
                    positions=positions,
                    weights=weights,
                    equity=equity,
                    calendar=self.calendar,
                )
                targets = strat.target_weights(ctx)
                if targets is not None:
                    targets = validate_weights(targets, cfg.rules, universe)
                    targets_log.append((now, targets))
                    prices = {s: float(marks[i, col[s]]) for s in set(targets) | set(positions)}
                    orders = plan_rebalance(targets, positions, prices, equity, cfg.rules)
                    if orders:
                        pending[i + cfg.delay].extend(orders)

        dates = idx[start_i : end_i + 1]
        equity_s = pd.Series(rec_equity, index=dates, name="equity")
        returns = equity_s.pct_change()
        returns.iloc[0] = equity_s.iloc[0] / cfg.initial_capital - 1.0
        weights_df = pd.DataFrame(rec_weights, index=dates, columns=syms)
        weights_df = weights_df.loc[:, (weights_df != 0).any(axis=0)]
        daily = pd.DataFrame(
            {
                "equity": rec_equity,
                "cash": rec_cash,
                "gross": np.abs(rec_weights).sum(axis=1),
                "turnover": rec_traded,
                "fees": rec_fees,
                "slippage": rec_slip,
                "financing": rec_financing,
            },
            index=dates,
        )
        bench = cfg.benchmark if cfg.benchmark in data.symbols else None
        bench_ret = (
            data.close[bench].ffill().pct_change().loc[dates]
            if bench
            else pd.Series(np.nan, index=dates)
        )
        targets_df = (
            pd.DataFrame(
                [t for _, t in targets_log], index=pd.DatetimeIndex([d for d, _ in targets_log])
            ).fillna(0.0)
            if targets_log
            else pd.DataFrame(index=pd.DatetimeIndex([]))
        )
        proxy_share = _proxy_share(weights_df, data.proxy_mask.loc[dates])
        return BacktestResult(
            strategy=strat.name,
            title=strat.label(),
            params=strat.param_dict(),
            config=cfg,
            returns=returns.rename("returns"),
            benchmark_returns=bench_ret.rename(bench or "benchmark"),
            rf=data.rf.loc[dates].rename("rf"),
            daily=daily,
            weights=weights_df,
            targets=targets_df,
            trades=pd.DataFrame(trades),
            meta={
                "description": strat.description,
                "references": [
                    {"citation": ref.citation, "url": ref.url} for ref in strat.references
                ],
                "publication_date": strat.publication_date,
                "schedule": strat.schedule().describe(),
                "universe": strat.universe(),
                "benchmark": bench,
                "proxy_share": proxy_share,
                "data_first_real": {
                    s: str(data.close[s][~data.proxy_mask[s]].first_valid_index().date())
                    for s in strat.data_symbols()
                    if data.close[s][~data.proxy_mask[s]].first_valid_index() is not None
                },
            },
        )

    def _execute(
        self,
        orders: list[Order],
        now: pd.Timestamp,
        ref_prices: np.ndarray,
        last_marks: np.ndarray,
        pos: np.ndarray,
        col: dict[str, int],
        cash: float,
        trades: list[dict],
        unfilled: list[Order] | None = None,
    ) -> tuple[float, float, float, float]:
        cfg = self.config
        costs = cfg.costs
        traded = fees_total = slip_total = 0.0

        def fill(o: Order, qty: float, ref: float) -> None:
            nonlocal cash, traded, fees_total, slip_total
            j = col[o.symbol]
            px = costs.fill_price(ref, qty, o.symbol)
            fee = costs.fees(qty, px)
            cash -= qty * px + fee
            pos[j] += qty
            if abs(pos[j]) < 1e-9:
                pos[j] = 0.0
            notional = abs(qty) * px
            slip = abs(px - ref) * abs(qty)
            traded += notional
            fees_total += fee
            slip_total += slip
            trades.append(
                {
                    "date": now,
                    "symbol": o.symbol,
                    "qty": qty,
                    "signal_price": o.ref_price,
                    "ref_price": ref,
                    "fill_price": px,
                    "notional": notional,
                    "fees": fee,
                    "slippage": slip,
                    "target_weight": o.target_weight,
                }
            )

        def ref_for(o: Order) -> float | None:
            ref = ref_prices[col[o.symbol]]
            if not math.isfinite(ref) or ref <= 0:
                log.info(
                    "%s: no %s price for %s on %s; order carried to the next session",
                    self.strategy.name,
                    cfg.execution,
                    o.symbol,
                    now.date(),
                )
                if unfilled is not None:
                    unfilled.append(o)
                return None
            return float(ref)

        for o in (o for o in orders if o.qty < 0):
            ref = ref_for(o)
            if ref is None:
                continue
            qty = o.qty
            held = pos[col[o.symbol]]
            if not cfg.rules.allow_short:
                qty = max(qty, -held)
            if qty < 0:
                fill(o, qty, ref)

        buys = [(o, ref_for(o)) for o in orders if o.qty > 0]
        buys = [(o, ref) for o, ref in buys if ref is not None]
        if buys:
            need = sum(o.qty * costs.fill_price(ref, o.qty, o.symbol) for o, ref in buys)
            px_now = np.where(np.isfinite(ref_prices), ref_prices, last_marks)
            equity_now = cash + float(np.nansum(np.where(pos != 0, pos * px_now, 0.0)))
            budget = cash + max(cfg.rules.max_gross - 1.0, 0.0) * equity_now
            scale = 1.0 if need <= budget else max(budget, 0.0) / need
            for o, ref in buys:
                qty = o.qty * scale if scale < 1.0 else o.qty
                if scale < 1.0:
                    qty = (
                        math.trunc(qty * 1e6) / 1e6
                        if cfg.rules.fractional
                        else float(math.floor(qty))
                    )
                if qty > 0:
                    fill(o, qty, ref)
        return cash, traded, fees_total, slip_total


def _proxy_share(weights: pd.DataFrame, proxy_mask: pd.DataFrame) -> float:
    """Fraction of gross exposure-days held in proxy (synthetic) data."""
    if weights.empty:
        return 0.0
    w = weights.abs()
    m = proxy_mask.reindex(index=w.index, columns=w.columns).fillna(False).astype(bool)
    total = float(w.to_numpy().sum())
    return float(w.where(m, 0.0).to_numpy().sum() / total) if total > 0 else 0.0
