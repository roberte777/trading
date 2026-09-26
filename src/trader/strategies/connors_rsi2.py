"""Connors & Alvarez RSI(2) short-term mean reversion, run on a basket of liquid ETFs.

Chapter 9 of *Short Term Trading Strategies That Work* (2008) buys the S&P 500 when
its 2-period Wilder RSI closes below 5 while the close is above the 200-day SMA,
and sells when the close rises above the 5-day SMA. No stops. Here the same rules
run on 13 liquid US equity ETFs with fixed 20% slots (at most five positions),
idle capital in T-bills (BIL), and fills at the next session's open.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from trader.data.proxies import proxies_for
from trader.indicators import rsi
from trader.strategy import Context, Daily, Reference, Strategy, register

#: The traded basket: four broad index ETFs and the nine Select Sector SPDRs.
RISKY: tuple[str, ...] = (
    "SPY",
    "QQQ",
    "IWM",
    "DIA",
    "XLB",
    "XLE",
    "XLF",
    "XLI",
    "XLK",
    "XLP",
    "XLU",
    "XLV",
    "XLY",
)

#: Rows of history for the Wilder RSI. The seed's weight after this many rows is
#: (1 - 1/n)^rows, i.e. 2^-100 for n = 2, so the truncated RSI equals the full one.
RSI_ROWS = 100

#: A projected position worth less than this fraction of a slot is dust, not a
#: holding. With ``delay >= 2`` the engine can leave a few stray shares when a pending
#: buy fills scaled down but the queued exit was sized to the full order; dust must
#: not occupy a slot (or be topped up to one), so it is sold instead.
DUST_SLOT_FRACTION = 0.1


@register
class ConnorsRSI2(Strategy):
    name = "connors_rsi2"
    title = "Connors RSI(2) mean reversion (ETF basket)"
    description = (
        "Buy an ETF when its 2-period Wilder RSI closes below 5 while the close is above "
        "its 200-day SMA; sell when the close rises above the 5-day SMA (no stops). Runs "
        "on SPY, QQQ, IWM, DIA and the nine sector SPDRs with fixed 20% slots (at most "
        "five positions, lowest RSI first); idle capital sits in BIL. Evaluated every "
        "close, filled at the next open."
    )
    references = (
        Reference(
            "Connors, L. & Alvarez, C. (2008), Short Term Trading Strategies That Work, "
            "TradingMarkets Publishing, ISBN 978-0981923901, ch. 9 (2-period RSI)",
            "https://www.biblio.com/book/short-term-trading-strategies-work-larry/d/1510291032",
        ),
        Reference(
            "Connors, L. & Alvarez, C. (2009), High Probability ETF Trading: 7 Professional "
            "Strategies to Improve Your ETF Trading, TradingMarkets, ISBN 978-0615297415",
            "https://www.biblio.com/9780615297415",
        ),
        Reference(
            "StockCharts ChartSchool, RSI(2) (secondary statement of the chapter 9 rules)",
            "https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/rsi-2",
        ),
        Reference(
            "Baltussen, G., van Bekkum, S. & Da, Z. (2019), Indexing and Stock Market Serial "
            "Dependence Around the World, Journal of Financial Economics 132(1), 26-48",
            "https://doi.org/10.1016/j.jfineco.2018.07.016",
        ),
        Reference(
            "Nagel, S. (2012), Evaporating Liquidity, Review of Financial Studies 25(7), 2005-2039",
            "https://academic.oup.com/rfs/article-abstract/25/7/2005/1602153",
        ),
    )
    publication_date = "2008-11-01"
    proxies = proxies_for([*RISKY, "BIL"])

    @dataclass(frozen=True)
    class Params:
        rsi_period: int = 2
        entry_threshold: float = 5.0
        trend_sma: int = 200
        exit_sma: int = 5
        slot_weight: float = 0.20
        cash_asset: str = "BIL"

    param_grid = {
        "entry_threshold": [10.0, 15.0],
        "exit_sma": [3, 10],
        "trend_sma": [150],
        "slot_weight": [0.1, 0.33],
    }

    def universe(self) -> list[str]:
        return [*RISKY, self.params.cash_asset]

    def _rsi_rows(self) -> int:
        return max(RSI_ROWS, 10 * self.params.rsi_period)

    def warmup(self) -> int:
        p = self.params
        return max(p.trend_sma, p.exit_sma, self._rsi_rows() + 1) + 5

    def schedule(self):
        return Daily()

    def max_positions(self) -> int:
        return int(math.floor(1.0 / self.params.slot_weight + 1e-9))

    def _held(self, ctx: Context, sym: str, price: float) -> bool:
        """Long (projected) position of at least a tenth of a slot; pending entries count."""
        qty = float(ctx.positions.get(sym, 0.0))
        if qty <= 0:
            return False
        if not np.isfinite(price) or ctx.equity <= 0:
            return True
        return qty * price / ctx.equity >= DUST_SLOT_FRACTION * self.params.slot_weight

    def target_weights(self, ctx: Context):
        p = self.params
        risky = list(RISKY)
        hist = ctx.history("close", self.warmup())[risky]
        last = hist.iloc[-1]

        # 200-day trend filter: needs a full window of real (non-NaN) closes.
        trend_win = hist.iloc[-p.trend_sma :]
        trend = trend_win.mean(skipna=False) if len(trend_win) >= p.trend_sma else last * np.nan
        exit_win = hist.iloc[-p.exit_sma :]
        exit_level = exit_win.mean(skipna=False) if len(exit_win) >= p.exit_sma else last * np.nan
        rsi_now = rsi(hist.iloc[-(self._rsi_rows() + 1) :], p.rsi_period).iloc[-1]

        held = {sym for sym in risky if self._held(ctx, sym, last[sym])}
        weights: dict[str, float] = {}

        # Exits and continuing holdings. "Held" includes pending entries, which the
        # engine projects into ``positions`` but not yet into ``weights``.
        for sym in risky:
            if sym not in held:
                continue
            px, level = last[sym], exit_level[sym]
            if np.isfinite(px) and np.isfinite(level) and px > level:
                continue  # exit: omitted symbols are sold at the next open
            weights[sym] = float(ctx.weights.get(sym, p.slot_weight))

        # Entries into free slots, lowest RSI first.
        candidates: list[tuple[float, str]] = []
        for sym in risky:
            if sym in held:
                continue
            px, sma_long, r = last[sym], trend[sym], rsi_now[sym]
            if not (np.isfinite(px) and np.isfinite(sma_long) and np.isfinite(r)):
                continue  # not listed yet, or not enough history
            if px > sma_long and r < p.entry_threshold:
                candidates.append((float(r), sym))
        free = max(self.max_positions() - len(weights), 0)
        budget = 1.0 - sum(weights.values())
        for _, sym in sorted(candidates)[:free]:
            w = min(p.slot_weight, budget)
            if w <= 1e-9:
                break
            weights[sym] = w
            budget -= w

        # Idle capital earns T-bills.
        rest = 1.0 - sum(weights.values())
        if rest > 1e-9 and ctx.is_tradable(p.cash_asset):
            weights[p.cash_asset] = rest
        return weights
