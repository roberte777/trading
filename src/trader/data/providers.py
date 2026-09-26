"""Daily bar providers: Yahoo Finance (free, no keys), Alpaca, and a parquet cache.

Every provider returns split- and dividend-adjusted OHLCV bars indexed by
tz-naive session dates with lowercase columns ``open high low close volume``.
Adjusted prices make ``close.pct_change()`` the total return, which matters: a
backtest on price-only data understates bond and equity-income returns by
several percent per year.
"""

from __future__ import annotations

import json
import logging
import os
import time as time_mod
from abc import ABC, abstractmethod
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from trader.data.market_data import FIELDS

log = logging.getLogger(__name__)

EARLIEST = pd.Timestamp("1970-01-01")
NY = ZoneInfo("America/New_York")
#: Daily bars are treated as final after this New York time (covers 16:00 close + late prints).
SESSION_FINAL = time(16, 30)


def normalize_bars(df: pd.DataFrame) -> pd.DataFrame:
    """Lowercase columns, tz-naive midnight index, sorted, de-duplicated."""
    if df is None or df.empty:
        return pd.DataFrame(
            columns=list(FIELDS), index=pd.DatetimeIndex([], name="date"), dtype=float
        )
    out = df.rename(columns=str.lower)
    out = out[[c for c in FIELDS if c in out.columns]].astype(float)
    for col in FIELDS:
        if col not in out.columns:
            out[col] = float("nan")
    idx = pd.DatetimeIndex(out.index)
    if idx.tz is not None:
        idx = idx.tz_convert("America/New_York").tz_localize(None)
    out.index = idx.normalize()
    out.index.name = "date"
    out = out[~out.index.duplicated(keep="last")].sort_index()
    return out[list(FIELDS)]


def drop_incomplete_session(bars: pd.DataFrame, now: datetime | None = None) -> pd.DataFrame:
    """Drop today's bar until the session has closed (vendors serve a live, partial bar).

    Caching a partial bar would let a later run treat mid-day prices as the close.
    """
    now = now or datetime.now(NY)
    today = pd.Timestamp(now.date())
    cutoff = today + pd.Timedelta(days=1) if now.time() >= SESSION_FINAL else today
    return bars[bars.index < cutoff]


class DataProvider(ABC):
    name: str = "base"

    @abstractmethod
    def fetch(self, symbol: str, start=None, end=None) -> pd.DataFrame:
        """Adjusted daily bars for ``symbol`` in ``[start, end]`` (inclusive)."""


class YahooProvider(DataProvider):
    """Yahoo Finance via yfinance. Free and keyless; history back to each fund's inception.

    ``auto_adjust=True`` back-adjusts OHLC for splits and dividends.
    """

    name = "yahoo"

    def __init__(self, retries: int = 4, pause: float = 2.0) -> None:
        self.retries = retries
        self.pause = pause

    def fetch(self, symbol: str, start=None, end=None) -> pd.DataFrame:
        import yfinance as yf

        start = pd.Timestamp(start) if start is not None else EARLIEST
        end = pd.Timestamp(end) if end is not None else pd.Timestamp.today().normalize()
        last_err: Exception | None = None
        for attempt in range(self.retries):
            try:
                df = yf.Ticker(symbol).history(
                    start=start.strftime("%Y-%m-%d"),
                    end=(end + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
                    interval="1d",
                    auto_adjust=True,
                    actions=False,
                    raise_errors=True,
                )
                bars = normalize_bars(df)
                if bars.empty:
                    raise ValueError(f"yahoo returned no bars for {symbol}")
                return bars.loc[start:end]
            except Exception as err:  # network hiccups and rate limits are common
                last_err = err
                wait = self.pause * (2**attempt)
                log.warning("yahoo fetch %s failed (%s); retry in %.0fs", symbol, err, wait)
                time_mod.sleep(wait)
        raise RuntimeError(f"yahoo fetch failed for {symbol}") from last_err


class AlpacaProvider(DataProvider):
    """Alpaca market data (alpaca-py). Requires ALPACA_API_KEY / ALPACA_SECRET_KEY.

    Uses ``adjustment=all`` so bars match the Yahoo total-return convention. The
    free plan serves SIP history except the latest 15 minutes, which is fine for
    daily bars of completed sessions. Alpaca history starts in 2016, so use Yahoo
    for long backtests and Alpaca for live signals if you prefer a single vendor.
    """

    name = "alpaca"

    def __init__(
        self, api_key: str | None = None, secret_key: str | None = None, feed: str = "sip"
    ) -> None:
        from alpaca.data.historical import StockHistoricalDataClient

        api_key = api_key or os.environ.get("ALPACA_API_KEY")
        secret_key = secret_key or os.environ.get("ALPACA_SECRET_KEY")
        if not api_key or not secret_key:
            raise RuntimeError("AlpacaProvider needs ALPACA_API_KEY and ALPACA_SECRET_KEY")
        self.client = StockHistoricalDataClient(api_key, secret_key)
        self.feed = feed

    def fetch(self, symbol: str, start=None, end=None) -> pd.DataFrame:
        from alpaca.data.enums import Adjustment, DataFeed
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame

        start = pd.Timestamp(start) if start is not None else pd.Timestamp("2016-01-01")
        end = pd.Timestamp(end) if end is not None else pd.Timestamp.today().normalize()
        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Day,
            start=start.to_pydatetime(),
            end=(end + pd.Timedelta(days=1)).to_pydatetime(),
            adjustment=Adjustment.ALL,
            feed=DataFeed(self.feed),
        )
        df = self.client.get_stock_bars(req).df
        if df.empty:
            raise ValueError(f"alpaca returned no bars for {symbol}")
        if isinstance(df.index, pd.MultiIndex):
            df = df.xs(symbol, level="symbol")
        return normalize_bars(df).loc[start:end]


class CachedProvider(DataProvider):
    """Parquet cache in front of another provider.

    The full available history is cached per symbol and refreshed when the cache is
    older than ``max_age`` and the request extends past the cached data. ``offline``
    serves only what is cached (for reproducible re-runs).
    """

    def __init__(
        self,
        inner: DataProvider,
        root: str | Path,
        max_age: timedelta = timedelta(hours=12),
        offline: bool = False,
    ) -> None:
        self.inner = inner
        self.root = Path(root) / inner.name
        self.max_age = max_age
        self.offline = offline
        self.name = inner.name

    def _paths(self, symbol: str) -> tuple[Path, Path]:
        safe = symbol.replace("^", "_").replace("/", "_").replace("=", "_")
        return self.root / f"{safe}.parquet", self.root / f"{safe}.json"

    def fetch(self, symbol: str, start=None, end=None) -> pd.DataFrame:
        start = pd.Timestamp(start) if start is not None else EARLIEST
        end = pd.Timestamp(end) if end is not None else pd.Timestamp.today().normalize()
        data_path, meta_path = self._paths(symbol)
        if data_path.exists() and meta_path.exists():
            meta = json.loads(meta_path.read_text())
            fetched_at = datetime.fromisoformat(meta["fetched_at"])
            fresh = datetime.now(UTC) - fetched_at < self.max_age
            cached = pd.read_parquet(data_path)
            covers_end = not cached.empty and cached.index[-1] >= end
            if self.offline or fresh or covers_end:
                return cached.loc[start:end]
        elif self.offline:
            raise FileNotFoundError(f"{symbol} not in offline cache {self.root}")
        bars = drop_incomplete_session(
            self.inner.fetch(symbol, EARLIEST, pd.Timestamp.today().normalize())
        )
        self.root.mkdir(parents=True, exist_ok=True)
        bars.to_parquet(data_path)
        meta_path.write_text(
            json.dumps(
                {
                    "symbol": symbol,
                    "provider": self.inner.name,
                    "fetched_at": datetime.now(UTC).isoformat(),
                    "first": str(bars.index[0].date()) if len(bars) else None,
                    "last": str(bars.index[-1].date()) if len(bars) else None,
                    "rows": len(bars),
                },
                indent=2,
            )
        )
        return bars.loc[start:end]


def default_cache_dir() -> Path:
    """``$TRADER_CACHE_DIR`` or ``~/.cache/trader`` — shared by every worktree on the machine."""
    env = os.environ.get("TRADER_CACHE_DIR")
    if env:
        return Path(env).expanduser()
    base = os.environ.get("XDG_CACHE_HOME") or "~/.cache"
    return Path(base).expanduser() / "trader"


def make_provider(
    name: str = "yahoo", cache_dir: str | Path | None = "default", offline: bool = False, **kwargs
) -> DataProvider:
    """Build a provider by name, wrapped in the parquet cache unless ``cache_dir`` is None."""
    if cache_dir == "default":
        cache_dir = default_cache_dir()
    name = name.lower()
    if name == "yahoo":
        inner: DataProvider = YahooProvider(**kwargs)
    elif name == "alpaca":
        inner = AlpacaProvider(**kwargs)
    else:
        raise ValueError(f"unknown data provider {name!r}")
    if cache_dir is None:
        return inner
    return CachedProvider(inner, cache_dir, offline=offline)
