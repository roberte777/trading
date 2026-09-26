"""High-level backtest orchestration: load data, run, evaluate, robustness suite."""

from __future__ import annotations

import dataclasses
import logging
import math
import os
import subprocess
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime
from typing import Any

import pandas as pd

from trader.analytics.metrics import (
    crisis_returns,
    performance_metrics,
    split_metrics,
    trading_metrics,
    yearly_returns,
)
from trader.analytics.stats import bootstrap_ci, deflated_sharpe, probabilistic_sharpe
from trader.backtest.engine import BacktestConfig, Backtester
from trader.backtest.result import BacktestResult
from trader.calendar import TradingCalendar
from trader.config import RunConfig
from trader.data.loader import DataLoader
from trader.data.market_data import MarketData
from trader.data.providers import make_provider
from trader.data.proxies import proxies_for
from trader.strategy.base import Strategy
from trader.strategy.schedule import Daily

log = logging.getLogger(__name__)

#: Metrics kept for each robustness variant.
VARIANT_KEYS = (
    "cagr",
    "volatility",
    "sharpe",
    "sortino",
    "max_drawdown",
    "calmar",
    "turnover_annual",
    "cost_drag_annual",
    "sharpe_daily",
    "start",
    "end",
)


def load_market_data(
    strategy: Strategy, run: RunConfig, extra: list[str] | None = None
) -> tuple[MarketData, TradingCalendar]:
    provider = make_provider(run.data.provider, run.data.cache_dir, offline=run.data.offline)
    proxies = run.proxies_for(strategy)
    if run.data.use_proxies and extra:
        proxies = {**proxies_for(extra), **proxies}
    loader = DataLoader(provider, proxies=proxies)
    symbols = [*strategy.data_symbols(), run.backtest.benchmark, *(extra or [])]
    end = pd.Timestamp(run.backtest.end) if run.backtest.end else pd.Timestamp.today().normalize()
    calendar = TradingCalendar.nyse(start="1970-01-01", end=end + pd.Timedelta(days=400))
    data = loader.load(symbols, end=end, calendar=calendar, use_proxies=run.data.use_proxies)
    return data, calendar


def run_one(
    strategy: Strategy, data: MarketData, calendar: TradingCalendar, config: BacktestConfig
) -> BacktestResult:
    return Backtester(strategy, data, calendar, config).run()


def evaluate(result: BacktestResult, bootstrap: bool = True) -> dict[str, Any]:
    """Full metric set for a single result (stored in summary.json)."""
    r, rf, b = result.returns, result.rf, result.benchmark_returns
    m: dict[str, Any] = performance_metrics(r, rf, b)
    m.update(trading_metrics(result.daily, result.trades))
    ex = (r - rf.reindex(r.index).fillna(0.0)).dropna()
    m["sharpe_daily"] = float(ex.mean() / ex.std(ddof=1)) if ex.std(ddof=1) > 0 else float("nan")
    m["psr_vs_zero"] = probabilistic_sharpe(ex)
    m["crises"] = crisis_returns(r)
    m["yearly"] = {str(k): float(v) for k, v in yearly_returns(r).items()}
    m["benchmark_yearly"] = (
        {str(k): float(v) for k, v in yearly_returns(b).items()} if b.notna().any() else {}
    )
    m["oos"] = split_metrics(r, rf, b, result.meta.get("publication_date"))
    if bootstrap:
        m["bootstrap"] = bootstrap_ci(r, rf, b)
    m["proxy_share"] = result.meta.get("proxy_share", 0.0)
    return m


def _variant_summary(result: BacktestResult) -> dict[str, Any]:
    m = performance_metrics(result.returns, result.rf, result.benchmark_returns)
    m.update(trading_metrics(result.daily, result.trades))
    ex = (result.returns - result.rf.reindex(result.returns.index).fillna(0.0)).dropna()
    m["sharpe_daily"] = float(ex.mean() / ex.std(ddof=1)) if ex.std(ddof=1) > 0 else float("nan")
    return {k: m.get(k) for k in VARIANT_KEYS}


def suite_variants(
    strategy: Strategy, base: BacktestConfig, data: MarketData
) -> dict[str, tuple[dict[str, Any], BacktestConfig, str]]:
    """Named variants: (param overrides, backtest config, description)."""
    v: dict[str, tuple[dict[str, Any], BacktestConfig, str]] = {}
    r = dataclasses.replace
    for mult in (0.0, 2.0, 4.0):
        v[f"costs_{mult:g}x"] = (
            {},
            r(base, costs=base.costs.scaled(mult)),
            f"all trading costs x{mult:g}",
        )
    other = "next_close" if base.execution == "next_open" else "next_open"
    v[f"exec_{other}"] = (
        {},
        r(base, execution=other),
        f"fill at {other.replace('_', ' ')} instead of {base.execution.replace('_', ' ')}",
    )
    v["delay_2"] = ({}, r(base, delay=base.delay + 1), "fills one extra session after the signal")
    if not isinstance(strategy.schedule(), Daily):
        for shift in (5, 10):
            v[f"shift_{shift}"] = (
                {},
                r(base, schedule_shift=shift),
                f"decide {shift} sessions before the scheduled day (timing luck)",
            )
    for name, values in strategy.param_grid.items():
        current = getattr(strategy.params, name)
        for val in values:
            if val != current:
                v[f"param_{name}={val}"] = (
                    {name: val},
                    base,
                    f"{name} = {val} (default {current})",
                )
    # Only symbols that actually use proxy history matter here: an ETF that simply
    # lists late (e.g. XLC in 2018) has no proxy rows and must not delay the variant.
    firsts = []
    for s in strategy.universe():
        if not data.proxy_mask[s].any():
            continue
        real = data.close[s][~data.proxy_mask[s]].first_valid_index()
        if real is not None:
            firsts.append(real)
    if firsts:
        real_start = max(firsts) + pd.Timedelta(days=int(strategy.warmup() * 1.5))
        if base.start is None or real_start > pd.Timestamp(base.start):
            v["etf_era"] = (
                {},
                r(base, start=str(real_start.date())),
                f"start {real_start.date()} — no proxy data held",
            )
    return v


def suite_symbols(strategy: Strategy) -> list[str]:
    """Symbols needed by parameter variants but not by the default parameters."""
    needed: list[str] = []
    for name, values in strategy.param_grid.items():
        for val in values:
            try:
                needed.extend(strategy.with_params(**{name: val}).data_symbols())
            except Exception as err:  # an invalid combination fails later, visibly
                log.debug("variant %s=%s: %s", name, val, err)
    base = set(strategy.data_symbols())
    return [s for s in dict.fromkeys(needed) if s not in base]


def _run_variant(args: tuple) -> tuple[str, dict[str, Any] | str, pd.Series | None]:
    name, strategy, data, calendar, cfg = args
    try:
        result = Backtester(strategy, data, calendar, cfg).run()
        return name, _variant_summary(result), result.returns
    except Exception as err:  # a failing variant should not sink the suite
        return name, f"error: {err}", None


def run_suite(
    strategy: Strategy,
    data: MarketData,
    calendar: TradingCalendar,
    base: BacktestConfig,
    workers: int | None = None,
    returns_out: dict[str, pd.Series] | None = None,
) -> dict[str, Any]:
    """Run every robustness variant. Daily returns are collected into ``returns_out``."""
    variants = suite_variants(strategy, base, data)
    jobs = [
        (name, strategy.with_params(**ov) if ov else strategy, data, calendar, cfg)
        for name, (ov, cfg, _) in variants.items()
    ]
    workers = workers or min(len(jobs), max(1, (os.cpu_count() or 2) - 1))
    out: dict[str, Any] = {}
    if workers > 1 and len(jobs) > 1:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            finished = list(pool.map(_run_variant, jobs))
    else:
        finished = [_run_variant(job) for job in jobs]
    for name, summary, rets in finished:
        out[name] = summary
        if returns_out is not None and rets is not None:
            returns_out[name] = rets
    return {name: {"description": variants[name][2], "metrics": out[name]} for name in variants}


def backtest(
    run: RunConfig, suite: bool = False, workers: int | None = None, **overrides: Any
) -> BacktestResult:
    """Load data, run the base backtest, evaluate it and (optionally) the robustness suite."""
    strategy = run.build_strategy()
    extra = suite_symbols(strategy) if suite else None
    data, calendar = load_market_data(strategy, run, extra=extra)
    cfg = run.backtest_config(**overrides)
    result = run_one(strategy, data, calendar, cfg)
    result.metrics = evaluate(result)
    result.meta.update(_provenance(run))
    if suite:
        variant_returns: dict[str, pd.Series] = {}
        result.variants = run_suite(
            strategy, data, calendar, cfg, workers, returns_out=variant_returns
        )
        result.variant_returns = pd.DataFrame(variant_returns)
        base_sr = result.metrics["sharpe_daily"]
        trials = [base_sr] + [
            v["metrics"]["sharpe_daily"]
            for v in result.variants.values()
            if isinstance(v["metrics"], dict)
            and v["metrics"].get("sharpe_daily") is not None
            and not math.isnan(v["metrics"]["sharpe_daily"])
        ]
        ex = (result.returns - result.rf).dropna()
        result.metrics["dsr_local"] = deflated_sharpe(ex, trials)
    return result


def _provenance(run: RunConfig) -> dict[str, Any]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=5
        ).stdout.strip()
    except Exception:
        commit = ""
    return {
        "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "git_commit": commit or None,
        "data_provider": run.data.provider,
        "use_proxies": run.data.use_proxies,
        "config_source": run.source,
    }
