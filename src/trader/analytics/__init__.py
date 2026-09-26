"""Performance metrics, statistical tests and reports."""

from trader.analytics.metrics import (
    CRISES,
    crisis_returns,
    drawdown,
    equity_curve,
    monthly_returns,
    performance_metrics,
    rolling_cagr,
    rolling_sharpe,
    split_metrics,
    trading_metrics,
    yearly_returns,
)
from trader.analytics.stats import (
    bootstrap_ci,
    deflated_sharpe,
    expected_max_sharpe,
    probabilistic_sharpe,
)

__all__ = [
    "CRISES",
    "bootstrap_ci",
    "crisis_returns",
    "deflated_sharpe",
    "drawdown",
    "equity_curve",
    "expected_max_sharpe",
    "monthly_returns",
    "performance_metrics",
    "probabilistic_sharpe",
    "rolling_cagr",
    "rolling_sharpe",
    "split_metrics",
    "trading_metrics",
    "yearly_returns",
]
