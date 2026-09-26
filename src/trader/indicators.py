"""Causal indicator helpers shared by strategies.

Every function only uses data at or before each row, so evaluating on a
truncated history gives the same value as evaluating on the full history.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def sma(x: pd.Series | pd.DataFrame, n: int) -> pd.Series | pd.DataFrame:
    return x.rolling(n, min_periods=n).mean()


def rsi(close: pd.Series | pd.DataFrame, n: int = 14) -> pd.Series | pd.DataFrame:
    """Wilder's RSI (the definition used by Connors & Alvarez)."""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()
    avg_loss = loss.ewm(alpha=1.0 / n, adjust=False, min_periods=n).mean()
    rs = avg_gain / avg_loss
    out = 100.0 - 100.0 / (1.0 + rs)
    # No losses in the window -> RSI 100; no gains -> 0.
    out = out.where(avg_loss != 0, 100.0)
    return out.where(avg_gain.notna())


def month_end(close: pd.Series | pd.DataFrame) -> pd.Series | pd.DataFrame:
    """Last available observation of each calendar month."""
    return close.groupby([close.index.year, close.index.month]).tail(1)


def trailing_return(close: pd.Series | pd.DataFrame, lookback: int, skip: int = 0):
    """Return from ``lookback + skip`` rows ago to ``skip`` rows ago, at the last row.

    With month-end closes, ``trailing_return(m, 12, 1)`` is the classic 12-1 momentum.
    """
    if len(close) < lookback + skip + 1:
        return close.iloc[-1] * np.nan
    end = close.iloc[-1 - skip]
    begin = close.iloc[-1 - skip - lookback]
    return end / begin - 1.0


def momentum_13612w(monthly: pd.Series | pd.DataFrame):
    """Keller & Keuning's 13612W: (12*r1 + 4*r3 + 2*r6 + r12) / 4 on month-end closes."""
    r = {k: trailing_return(monthly, k) for k in (1, 3, 6, 12)}
    return (12 * r[1] + 4 * r[3] + 2 * r[6] + r[12]) / 4.0


def realized_vol(close: pd.Series | pd.DataFrame, n: int, annualize: bool = True):
    """Sample std of the last ``n`` daily returns, at the last row."""
    rets = close.pct_change().iloc[-n:]
    vol = rets.std(ddof=1)
    return vol * np.sqrt(TRADING_DAYS) if annualize else vol


def ewma_vol(
    close: pd.Series | pd.DataFrame,
    com: float = 60.0,
    annualize: bool = True,
    min_periods: int = 60,
):
    """Exponentially weighted volatility at the last row (Moskowitz-Ooi-Pedersen use com=60)."""
    vol = close.pct_change().ewm(com=com, min_periods=min_periods).std().iloc[-1]
    return vol * np.sqrt(TRADING_DAYS) if annualize else vol


def normalize_weights(weights: dict[str, float], total: float = 1.0) -> dict[str, float]:
    s = sum(weights.values())
    if s <= 0:
        return {}
    return {k: total * v / s for k, v in weights.items()}
