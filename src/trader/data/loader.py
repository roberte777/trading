"""Assemble a session-aligned ``MarketData`` panel from a provider.

Handles three things that decide whether a backtest is believable:

* **Cleaning** – drops non-positive prices, repairs OHLC ordering, logs suspicious jumps.
* **Pre-inception proxies** – most ETFs launched 2002-2007. To test through the
  2000-2002 bear market, a symbol's history can be extended backwards with the
  *returns* of an older proxy (e.g. VUSTX before TLT). Proxy rows are flagged in
  ``MarketData.proxy_mask`` so reports can say how much of a result is synthetic.
* **Risk-free rate** – daily T-bill accrual from the 13-week yield (^IRX), lagged
  one session so it is known in advance.

Synthetic series use an ``@`` prefix. ``@tbill`` is a T-bill total-return index
built from ^IRX (net of a small fee), used as the pre-2007 proxy for BIL.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping

import numpy as np
import pandas as pd

from trader.calendar import TradingCalendar, to_session
from trader.data.market_data import FIELDS, MarketData
from trader.data.providers import DataProvider

log = logging.getLogger(__name__)

RISK_FREE_SYMBOL = "^IRX"
TBILL_FEE = 0.001  # ~ BIL/SHV expense ratio, deducted from the synthetic T-bill index


def clean_bars(df: pd.DataFrame, symbol: str, jump_threshold: float = 0.35) -> pd.DataFrame:
    """Basic sanity repairs for vendor daily bars. Returns a new frame."""
    out = df.copy()
    out = out[np.isfinite(out["close"]) & (out["close"] > 0)]
    for col in ("open", "high", "low"):
        bad = ~np.isfinite(out[col]) | (out[col] <= 0)
        out.loc[bad, col] = out.loc[bad, "close"]
    hi = out[["open", "high", "low", "close"]].max(axis=1)
    lo = out[["open", "high", "low", "close"]].min(axis=1)
    out["high"] = hi
    out["low"] = lo
    out["volume"] = out["volume"].where(np.isfinite(out["volume"]) & (out["volume"] >= 0))
    if symbol.startswith("^"):  # yield/index series: large relative moves are normal near zero
        return out
    rets = out["close"].pct_change().abs()
    jumps = rets[rets > jump_threshold]
    for when, r in jumps.items():
        log.warning(
            "%s: %.0f%% close-to-close move on %s — check vendor data", symbol, 100 * r, when.date()
        )
    return out


def tbill_index(
    irx: pd.DataFrame | pd.Series, sessions: pd.DatetimeIndex, fee: float = TBILL_FEE
) -> pd.DataFrame:
    """Synthetic T-bill total-return bars from the ^IRX yield (percent)."""
    y = irx["close"] if isinstance(irx, pd.DataFrame) else irx
    y = y.reindex(sessions).ffill().bfill() / 100.0
    daily = (y.shift(1).fillna(y.iloc[0]) - fee) / 252.0
    price = 100.0 * (1.0 + daily).cumprod()
    bars = pd.DataFrame(
        {"open": price, "high": price, "low": price, "close": price, "volume": np.nan}
    )
    bars.index.name = "date"
    return bars


def risk_free_series(irx: pd.DataFrame | None, sessions: pd.DatetimeIndex) -> pd.Series:
    """Per-session T-bill return, using the prior session's yield (no look-ahead)."""
    if irx is None or irx.empty:
        return pd.Series(0.0, index=sessions, name="rf")
    y = irx["close"].reindex(sessions).ffill().bfill() / 100.0
    rf = (y.shift(1) / 252.0).fillna(0.0)
    rf.name = "rf"
    return rf


def splice(primary: pd.DataFrame, proxy: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Extend ``primary`` backwards using ``proxy`` returns.

    Proxy bars before the primary's first date are rescaled so the two series join
    at the primary's first close; returns before that date are the proxy's returns.
    Volume is unknown for proxy rows (NaN).
    """
    if primary.empty:
        mask = pd.Series(True, index=proxy.index)
        return proxy.assign(volume=np.nan), mask
    first = primary.index[0]
    anchor = proxy.loc[:first]
    if anchor.empty:
        return primary, pd.Series(False, index=primary.index)
    scale = primary["close"].iloc[0] / anchor["close"].iloc[-1]
    head = proxy.loc[proxy.index < first].copy()
    for col in ("open", "high", "low", "close"):
        head[col] = head[col] * scale
    head["volume"] = np.nan
    out = pd.concat([head, primary])
    mask = pd.Series(out.index < first, index=out.index)
    return out, mask


class DataLoader:
    """Loads and caches cleaned per-symbol bars, then builds ``MarketData`` panels."""

    def __init__(self, provider: DataProvider, proxies: Mapping[str, str] | None = None) -> None:
        self.provider = provider
        self.proxies = dict(proxies or {})
        self._bars: dict[str, pd.DataFrame] = {}

    def bars(self, symbol: str) -> pd.DataFrame:
        if symbol not in self._bars:
            self._bars[symbol] = clean_bars(self.provider.fetch(symbol), symbol)
        return self._bars[symbol]

    def _series(
        self,
        symbol: str,
        sessions: pd.DatetimeIndex,
        use_proxies: bool,
        seen: frozenset[str] = frozenset(),
    ) -> tuple[pd.DataFrame, pd.Series]:
        if symbol in seen:
            raise ValueError(f"proxy cycle through {symbol}")
        if symbol == "@tbill":
            bars = tbill_index(self.bars(RISK_FREE_SYMBOL), sessions)
            return bars, pd.Series(True, index=bars.index)
        bars = self.bars(symbol)
        proxy = self.proxies.get(symbol) if use_proxies else None
        if not proxy:
            return bars, pd.Series(False, index=bars.index)
        pbars, pmask = self._series(proxy, sessions, use_proxies, seen | {symbol})
        out, mask = splice(bars, pbars)
        return out, mask

    def load(
        self,
        symbols: Iterable[str],
        *,
        start=None,
        end=None,
        calendar: TradingCalendar | None = None,
        use_proxies: bool = False,
        risk_free: str | None = RISK_FREE_SYMBOL,
    ) -> MarketData:
        symbols = list(dict.fromkeys(symbols))
        end = to_session(end) if end is not None else to_session(pd.Timestamp.today())
        cal = calendar or TradingCalendar.nyse(start="1970-01-01", end=end + pd.Timedelta(days=400))
        sessions = cal.sessions[cal.sessions <= end]
        if start is not None:
            sessions = sessions[sessions >= to_session(start)]
        per_symbol: dict[str, pd.DataFrame] = {}
        masks: dict[str, pd.Series] = {}
        for sym in symbols:
            bars, mask = self._series(sym, sessions, use_proxies)
            per_symbol[sym] = bars
            masks[sym] = mask
        # Trim leading sessions where no symbol has data yet.
        firsts = [b.index[0] for b in per_symbol.values() if len(b)]
        if firsts:
            sessions = sessions[sessions >= min(firsts)]
        frames = {
            f: pd.DataFrame(
                {s: per_symbol[s][f].reindex(sessions) for s in symbols}, index=sessions
            )
            for f in FIELDS
        }
        proxy_mask = pd.DataFrame(
            {s: masks[s].reindex(sessions).fillna(False).astype(bool) for s in symbols},
            index=sessions,
        )
        rf = None
        if risk_free:
            try:
                rf = risk_free_series(self.bars(risk_free), sessions)
            except Exception as err:  # the risk-free rate is a nicety, not a hard dependency
                log.warning("risk-free series unavailable (%s); using 0", err)
        return MarketData(frames, rf=rf, proxy_mask=proxy_mask)
