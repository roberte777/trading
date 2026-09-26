"""Backtest output container with a stable on-disk format.

A result folder looks like::

    results/<strategy>/
        summary.json     # params, config, metrics, metadata, references
        daily.parquet    # equity, returns, benchmark, rf, gross, turnover, costs
        weights.parquet  # end-of-day weights per symbol
        targets.parquet  # strategy targets on each decision date
        trades.parquet   # every simulated fill
        variants.json    # robustness-suite metrics (when run with --suite)
        variant_returns.parquet  # daily returns of each robustness variant

``trader compare results/*`` reads any number of these folders.
"""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd


def _jsonable(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: _jsonable(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, pd.Timestamp):
        return str(obj.date())
    if hasattr(obj, "item"):
        return obj.item()
    return obj


@dataclass
class BacktestResult:
    strategy: str
    title: str
    params: dict[str, Any]
    config: Any
    returns: pd.Series
    benchmark_returns: pd.Series
    rf: pd.Series
    daily: pd.DataFrame
    weights: pd.DataFrame
    targets: pd.DataFrame
    trades: pd.DataFrame
    meta: dict[str, Any] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    variants: dict[str, Any] = field(default_factory=dict)
    #: Daily returns of every robustness variant (columns), for trial-count corrections.
    variant_returns: pd.DataFrame = field(default_factory=pd.DataFrame)

    @property
    def equity(self) -> pd.Series:
        return self.daily["equity"]

    @property
    def start(self) -> pd.Timestamp:
        return self.returns.index[0]

    @property
    def end(self) -> pd.Timestamp:
        return self.returns.index[-1]

    def save(self, folder: str | Path) -> Path:
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        daily = self.daily.copy()
        daily["returns"] = self.returns
        daily["benchmark"] = self.benchmark_returns
        daily["rf"] = self.rf
        daily.index.name = "date"
        daily.to_parquet(folder / "daily.parquet")
        self.weights.rename_axis("date").to_parquet(folder / "weights.parquet")
        self.targets.rename_axis("date").to_parquet(folder / "targets.parquet")
        trades = (
            self.trades if not self.trades.empty else pd.DataFrame({"date": pd.to_datetime([])})
        )
        trades.to_parquet(folder / "trades.parquet")
        summary = {
            "strategy": self.strategy,
            "title": self.title,
            "params": self.params,
            "config": self.config,
            "start": self.start,
            "end": self.end,
            "benchmark": self.benchmark_returns.name,
            "metrics": self.metrics,
            "meta": self.meta,
        }
        (folder / "summary.json").write_text(
            json.dumps(_jsonable(summary), indent=2, default=str) + "\n"
        )
        if self.variants:
            (folder / "variants.json").write_text(
                json.dumps(_jsonable(self.variants), indent=2, default=str) + "\n"
            )
        if not self.variant_returns.empty:
            vr = self.variant_returns.rename_axis("date").astype("float32")
            vr.to_parquet(folder / "variant_returns.parquet")
        return folder

    @classmethod
    def load(cls, folder: str | Path) -> BacktestResult:
        folder = Path(folder)
        summary = json.loads((folder / "summary.json").read_text())
        daily = pd.read_parquet(folder / "daily.parquet")
        returns = daily.pop("returns")
        bench = daily.pop("benchmark").rename(summary.get("benchmark") or "benchmark")
        rf = daily.pop("rf")
        variants_path = folder / "variants.json"
        trades = pd.read_parquet(folder / "trades.parquet")
        return cls(
            strategy=summary["strategy"],
            title=summary["title"],
            params=summary["params"],
            config=summary["config"],
            returns=returns,
            benchmark_returns=bench,
            rf=rf,
            daily=daily,
            weights=pd.read_parquet(folder / "weights.parquet"),
            targets=pd.read_parquet(folder / "targets.parquet"),
            trades=trades,
            meta=summary.get("meta", {}),
            metrics=summary.get("metrics", {}),
            variants=json.loads(variants_path.read_text()) if variants_path.exists() else {},
            variant_returns=(
                pd.read_parquet(folder / "variant_returns.parquet").astype(float)
                if (folder / "variant_returns.parquet").exists()
                else pd.DataFrame()
            ),
        )
