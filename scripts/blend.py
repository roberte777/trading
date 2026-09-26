"""Evaluate running several strategies side by side (one container each).

Each strategy gets a fixed share of capital, and the shares are reset monthly
(equivalent to topping up / trimming each container's allocation once a month).
Prints metrics for the blend next to its members and SPY, over their common window.

    python scripts/blend.py results/faber_gtaa results/vol_managed_spy results/connors_rsi2
    python scripts/blend.py results/a results/b --weights 0.6 0.4 --json reports/blend.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from trader.analytics.metrics import crisis_returns, performance_metrics, yearly_returns
from trader.backtest.result import BacktestResult


def blend_returns(returns: pd.DataFrame, weights: np.ndarray) -> pd.Series:
    """Daily returns of a monthly-rebalanced fixed-weight mix of return streams."""
    out = []
    for _, month in returns.groupby([returns.index.year, returns.index.month]):
        growth = (1.0 + month).cumprod()
        value = growth.mul(weights, axis=1).sum(axis=1)
        prev = np.r_[1.0, value.to_numpy()[:-1]]
        out.append(pd.Series(value.to_numpy() / prev - 1.0, index=month.index))
    return pd.concat(out).rename("blend")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results", nargs="+")
    ap.add_argument("--weights", nargs="*", type=float)
    ap.add_argument("--json", help="write metrics to this file")
    args = ap.parse_args(argv)

    loaded = [BacktestResult.load(p) for p in args.results]
    start = max(r.start for r in loaded)
    end = min(r.end for r in loaded)
    rets = pd.DataFrame({r.strategy: r.returns.loc[start:end] for r in loaded}).fillna(0.0)
    rets.iloc[0] = 0.0
    w = np.asarray(args.weights or [1.0 / len(loaded)] * len(loaded), dtype=float)
    if len(w) != len(loaded) or not np.isclose(w.sum(), 1.0):
        sys.exit("--weights must give one weight per result and sum to 1")
    rf = loaded[0].rf.loc[start:end]
    spy = loaded[0].benchmark_returns.loc[start:end]
    blend = blend_returns(rets, w)

    rows = {"blend": performance_metrics(blend, rf, spy)}
    for col in rets:
        rows[col] = performance_metrics(rets[col], rf, spy)
    rows["SPY"] = performance_metrics(spy.fillna(0.0), rf)
    keys = ["cagr", "volatility", "sharpe", "sortino", "max_drawdown", "calmar", "worst_month", "beta"]
    print(f"Window {start.date()} → {end.date()}; weights {dict(zip(rets.columns, [round(float(x), 3) for x in w], strict=True))}\n")
    print(f"{'':28s}" + "".join(f"{k:>14s}" for k in keys))
    for name, m in rows.items():
        cells = []
        for k in keys:
            v = m.get(k)
            if v is None:
                cells.append(f"{'–':>14s}")
            elif k in {"sharpe", "sortino", "calmar", "beta"}:
                cells.append(f"{v:14.2f}")
            else:
                cells.append(f"{100 * v:13.1f}%")
        print(f"{name:28s}" + "".join(cells))
    corr = rets.resample("ME").apply(lambda x: (1 + x).prod() - 1).corr()
    print("\nMonthly return correlation:\n" + corr.round(2).to_string())
    print("\nBlend in stress windows:")
    for k, v in crisis_returns(blend).items():
        print(f"  {k:45s} {100 * v:7.1f}%")
    if args.json:
        payload = {
            "window": [str(start.date()), str(end.date())],
            "weights": dict(zip(rets.columns, w.tolist(), strict=True)),
            "metrics": rows,
            "correlation": corr.round(3).to_dict(),
            "crises": crisis_returns(blend),
            "yearly": {str(k): float(v) for k, v in yearly_returns(blend).items()},
        }
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(payload, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
