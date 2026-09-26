"""Run configuration: one YAML file per strategy drives both backtests and live.

Example (``configs/strategies/faber_gtaa.yaml``)::

    strategy: faber_gtaa
    params: {}                 # defaults = the published parameters
    execution:                 # shared by backtest AND live, so they cannot drift
      mode: next_open          # decide at close, market-on-open next session
      fractional: false
      rebalance_band: 0.0
    data:
      provider: yahoo
      use_proxies: true
    backtest:
      start: 2000-01-03
      costs: {slippage_bps: 5}
    live:
      broker: alpaca
      paper: true
"""

from __future__ import annotations

import dataclasses
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from trader.backtest.engine import BacktestConfig
from trader.execution.costs import CostModel
from trader.execution.rebalance import RebalanceRules


def _build[T](cls: type[T], values: dict[str, Any] | None, where: str) -> T:
    values = dict(values or {})
    names = {f.name for f in dataclasses.fields(cls)}  # type: ignore[arg-type]
    unknown = set(values) - names
    if unknown:
        raise ValueError(f"{where}: unknown keys {sorted(unknown)}; allowed: {sorted(names)}")
    for k, v in values.items():
        if hasattr(v, "isoformat"):
            values[k] = v.isoformat()
    return cls(**values)


@dataclass(frozen=True)
class ExecutionConfig:
    mode: str = "next_open"
    delay: int = 1
    fractional: bool = False
    rebalance_band: float = 0.0
    min_order_value: float = 1.0
    cash_buffer: float = 0.0
    max_gross: float = 1.0
    allow_short: bool = False

    def rules(self) -> RebalanceRules:
        return RebalanceRules(
            fractional=self.fractional,
            rebalance_band=self.rebalance_band,
            min_order_value=self.min_order_value,
            cash_buffer=self.cash_buffer,
            max_gross=self.max_gross,
            allow_short=self.allow_short,
        )


@dataclass(frozen=True)
class DataConfig:
    provider: str = "yahoo"
    #: Parquet cache location; "default" = $TRADER_CACHE_DIR or ~/.cache/trader.
    cache_dir: str = "default"
    use_proxies: bool = True
    #: Extra/override proxies merged over the strategy's own.
    proxies: dict[str, str] = field(default_factory=dict)
    offline: bool = False


@dataclass(frozen=True)
class BacktestSection:
    start: str | None = None
    end: str | None = None
    initial_capital: float = 100_000.0
    costs: dict[str, float] = field(default_factory=dict)
    cash_interest: bool = False
    margin_rate: float = 0.07
    initial_rebalance: bool = True
    benchmark: str = "SPY"


@dataclass(frozen=True)
class LiveConfig:
    #: ``alpaca`` or ``local`` (a file-backed simulated account for forward tests).
    broker: str = "alpaca"
    paper: bool = True
    #: Log the orders that would be sent, but send nothing.
    dry_run: bool = False
    #: Unique name for this deployment (prefixes client order ids and the state
    #: folder). Defaults to the strategy name; set it when running the same
    #: strategy twice against one account.
    instance_id: str | None = None
    #: ``dedicated``: the strategy owns the account (times ``capital_fraction``).
    #: ``shared``: several strategies share one account; this one trades only its
    #: own ledger, seeded with ``allocation`` dollars.
    account_mode: str = "dedicated"
    allocation: float | None = None
    capital_fraction: float = 1.0
    #: ``market``: day market orders queued before the open (works on every Alpaca
    #: account). ``auction``: opg/cls auction orders (falls back to market if the
    #: account is not permitted to use them).
    order_style: str = "market"
    #: Market data for live signals. ``yahoo`` matches the backtest data exactly.
    data_provider: str = "yahoo"
    #: New York time to start the run (default 08:45 for next_open; 25 minutes
    #: before the close for next_close).
    run_at: str | None = None
    #: Orders rejected before the open (e.g. wash-trade protection when another
    #: strategy trades the same symbol) are retried this many minutes after the open.
    retry_after_open_minutes: int = 5
    #: Trade to the strategy's targets on first deployment instead of waiting for
    #: the next scheduled rebalance (mirrors the backtest default).
    initial_rebalance: bool = True
    state_dir: str = "state"
    #: Abort a rebalance whose traded notional exceeds this multiple of equity.
    max_turnover: float = 2.2
    #: Dedicated accounts holding non-universe symbols: ``ignore`` or ``fail``.
    foreign_positions: str = "ignore"
    #: Starting cash for the ``local`` broker.
    local_initial_cash: float = 100_000.0

    def resolved_run_at(self, mode: str) -> str:
        return self.run_at or ("08:45" if mode == "next_open" else "15:35")


@dataclass(frozen=True)
class RunConfig:
    strategy: str
    params: dict[str, Any] = field(default_factory=dict)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    data: DataConfig = field(default_factory=DataConfig)
    backtest: BacktestSection = field(default_factory=BacktestSection)
    live: LiveConfig = field(default_factory=LiveConfig)
    source: str | None = None

    def backtest_config(self, **overrides: Any) -> BacktestConfig:
        bt = self.backtest
        cfg = BacktestConfig(
            start=bt.start,
            end=bt.end,
            initial_capital=bt.initial_capital,
            execution=self.execution.mode,
            delay=self.execution.delay,
            costs=_build(CostModel, bt.costs, "backtest.costs"),
            rules=self.execution.rules(),
            cash_interest=bt.cash_interest,
            margin_rate=bt.margin_rate,
            initial_rebalance=bt.initial_rebalance,
            benchmark=bt.benchmark,
        )
        return dataclasses.replace(cfg, **overrides) if overrides else cfg

    def build_strategy(self):
        from trader.strategy.registry import get_strategy

        return get_strategy(self.strategy)(**self.params)

    def proxies_for(self, strategy) -> dict[str, str]:
        return {**strategy.proxies, **self.data.proxies} if self.data.use_proxies else {}


def load_config(path: str | Path) -> RunConfig:
    path = Path(path)
    raw = yaml.safe_load(path.read_text()) or {}
    return config_from_dict(raw, source=str(path))


def config_from_dict(raw: dict[str, Any], source: str | None = None) -> RunConfig:
    raw = dict(raw)
    if "strategy" not in raw:
        raise ValueError(f"{source or 'config'}: missing `strategy`")
    allowed = {"strategy", "params", "execution", "data", "backtest", "live"}
    unknown = set(raw) - allowed
    if unknown:
        raise ValueError(f"{source or 'config'}: unknown top-level keys {sorted(unknown)}")
    return RunConfig(
        strategy=raw["strategy"],
        params=dict(raw.get("params") or {}),
        execution=_build(ExecutionConfig, raw.get("execution"), "execution"),
        data=_build(DataConfig, raw.get("data"), "data"),
        backtest=_build(BacktestSection, raw.get("backtest"), "backtest"),
        live=_build(LiveConfig, raw.get("live"), "live"),
        source=source,
    )


def resolve_config(ref: str, config_dir: str | Path = "configs/strategies") -> RunConfig:
    """Accept a path to a YAML file or a bare strategy name.

    A bare name uses ``configs/strategies/<name>.yaml`` when it exists, otherwise the
    strategy's defaults. ``TRADER_CONFIG_DIR`` overrides the directory.
    """
    p = Path(ref)
    if p.suffix in {".yaml", ".yml"} or p.exists():
        return load_config(p)
    candidate = Path(os.environ.get("TRADER_CONFIG_DIR", config_dir)) / f"{ref}.yaml"
    if candidate.exists():
        return load_config(candidate)
    return RunConfig(strategy=ref)
