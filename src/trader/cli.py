"""Command line interface: ``trader <command> ...``.

trader list                                  # registered strategies
trader data fetch SPY TLT ^IRX               # warm the data cache
trader backtest faber_gtaa --suite           # base run + robustness suite
trader backtest configs/strategies/x.yaml --start 2005-01-01 --out results/x
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger("trader")


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    for noisy in ("yfinance", "urllib3", "peewee", "curl_cffi"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _parse_params(items: list[str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for item in items or []:
        if "=" not in item:
            raise SystemExit(f"--param expects key=value, got {item!r}")
        key, value = item.split("=", 1)
        out[key] = yaml.safe_load(value)
    return out


def _fmt_pct(x: Any) -> str:
    return f"{100 * x:6.2f}%" if isinstance(x, (int, float)) else str(x)


def cmd_list(args: argparse.Namespace) -> int:
    from trader.strategy.registry import all_strategies

    for name, cls in all_strategies().items():
        pub = f" [{cls.publication_date}]" if cls.publication_date else ""
        print(f"{name:28s} {cls.title}{pub}")
        if args.verbose:
            s = cls()
            print(
                f"{'':28s} universe: {', '.join(s.universe())}; schedule: {s.schedule().describe()}"
            )
            for ref in cls.references:
                print(f"{'':28s} - {ref.citation}")
    return 0


def cmd_data_fetch(args: argparse.Namespace) -> int:
    from trader.data.providers import make_provider

    provider = make_provider(args.provider, args.cache_dir)
    for sym in args.symbols:
        bars = provider.fetch(sym)
        print(f"{sym:8s} {bars.index[0].date()} → {bars.index[-1].date()}  ({len(bars)} bars)")
    return 0


def cmd_backtest(args: argparse.Namespace) -> int:
    import dataclasses

    from trader.backtest.runner import backtest
    from trader.config import resolve_config

    run = resolve_config(args.strategy)
    params = _parse_params(args.param)
    if params:
        run = dataclasses.replace(run, params={**run.params, **params})
    if args.offline:
        run = dataclasses.replace(run, data=dataclasses.replace(run.data, offline=True))
    if args.no_proxies:
        run = dataclasses.replace(run, data=dataclasses.replace(run.data, use_proxies=False))
    overrides = {k: v for k, v in {"start": args.start, "end": args.end}.items() if v}
    result = backtest(run, suite=args.suite, workers=args.workers, **overrides)
    out = Path(args.out or f"results/{result.strategy}")
    result.save(out)
    m = result.metrics
    print(f"\n{result.title}  ({m['start']} → {m['end']}, {m['years']:.1f}y)")
    for key in (
        "cagr",
        "volatility",
        "sharpe",
        "sortino",
        "max_drawdown",
        "calmar",
        "turnover_annual",
        "cost_drag_annual",
    ):
        val = m.get(key)
        shown = (
            f"{val:6.2f}"
            if key in {"sharpe", "sortino", "calmar"}
            else (_fmt_pct(val) if key != "turnover_annual" else f"{val:6.2f}x")
        )
        print(f"  {key:18s} {shown}")
    if "benchmark_cagr" in m:
        print(f"  {'benchmark_cagr':18s} {_fmt_pct(m['benchmark_cagr'])}")
    if result.variants:
        print("\n  robustness suite:")
        for name, v in result.variants.items():
            vm = v["metrics"]
            if isinstance(vm, dict):
                print(
                    f"    {name:28s} CAGR {_fmt_pct(vm['cagr'])}  Sharpe {vm['sharpe']:5.2f}  MaxDD {_fmt_pct(vm['max_drawdown'])}"
                )
            else:
                print(f"    {name:28s} {vm}")
    print(f"\nsaved → {out}")
    if args.json:
        print(json.dumps({k: m[k] for k in ("cagr", "sharpe", "max_drawdown")}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="trader", description="Daily-bar algorithmic trading harness")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("list", help="list registered strategies")
    sp.add_argument(
        "-v", "--verbose", action="store_true", help="show universe, schedule and sources"
    )
    sp.set_defaults(func=cmd_list)

    sp = sub.add_parser("data", help="market data utilities")
    dsub = sp.add_subparsers(dest="data_command", required=True)
    fp = dsub.add_parser("fetch", help="download symbols into the cache")
    fp.add_argument("symbols", nargs="+")
    fp.add_argument("--provider", default="yahoo")
    fp.add_argument("--cache-dir", default="default")
    fp.set_defaults(func=cmd_data_fetch)

    sp = sub.add_parser("backtest", help="backtest a strategy (name or config path)")
    sp.add_argument("strategy", help="strategy name or path to a YAML config")
    sp.add_argument("--suite", action="store_true", help="also run the robustness suite")
    sp.add_argument("--start")
    sp.add_argument("--end")
    sp.add_argument("--param", action="append", default=[], help="override a parameter: key=value")
    sp.add_argument("--out", help="result folder (default results/<strategy>)")
    sp.add_argument("--offline", action="store_true", help="only use cached data")
    sp.add_argument(
        "--no-proxies", action="store_true", help="disable pre-inception proxy splicing"
    )
    sp.add_argument("--workers", type=int)
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_backtest)

    for extend in _EXTENSIONS:
        extend(sub)
    return p


#: Other modules append subcommand builders here (compare, live, ...).
_EXTENSIONS: list = []


def _load_extensions() -> None:
    import importlib

    for mod in ("trader.analytics.report", "trader.live.cli"):
        try:
            module = importlib.import_module(mod)
        except ModuleNotFoundError as err:
            # Optional extension not present in this build; re-raise real import errors.
            if not err.name or not mod.startswith(err.name):
                raise
            continue
        register = getattr(module, "register_cli", None)
        if register is not None and register not in _EXTENSIONS:
            _EXTENSIONS.append(register)


def main(argv: list[str] | None = None) -> int:
    _load_extensions()
    parser = build_parser()
    args = parser.parse_args(argv)
    _setup_logging(args.verbose)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    sys.exit(main())
