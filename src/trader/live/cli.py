"""``trader live ...`` commands and the wiring from config to a running LiveRunner.

trader live run                      # daemon; config from $TRADER_CONFIG or $TRADER_STRATEGY
trader live run gtaa --once --dry-run
trader live run configs/strategies/x.yaml --once --session 2026-10-01 --broker local
trader live status x
trader live health x                 # Docker HEALTHCHECK: fresh heartbeat?
"""

from __future__ import annotations

import dataclasses
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

from trader.calendar import TradingCalendar
from trader.config import RunConfig, resolve_config
from trader.data.loader import DataLoader
from trader.data.providers import CachedProvider, default_cache_dir, make_provider
from trader.live.broker import NY, Broker, LocalBroker
from trader.live.runner import LiveRunner


def _truthy(value: str | None) -> bool | None:
    if value is None or value == "":
        return None
    return value.strip().lower() in {"1", "true", "yes", "on"}


def config_from_env(ref: str | None) -> RunConfig:
    ref = ref or os.environ.get("TRADER_CONFIG") or os.environ.get("TRADER_STRATEGY")
    if not ref:
        raise SystemExit(
            "pass a config path or strategy name, or set TRADER_CONFIG / TRADER_STRATEGY"
        )
    run = resolve_config(ref)
    live = run.live
    overrides = {
        "paper": _truthy(os.environ.get("ALPACA_PAPER")),
        "dry_run": _truthy(os.environ.get("TRADER_DRY_RUN")),
        "broker": os.environ.get("TRADER_BROKER") or None,
        "account_mode": os.environ.get("TRADER_ACCOUNT_MODE") or None,
        "allocation": float(os.environ["TRADER_ALLOCATION"])
        if os.environ.get("TRADER_ALLOCATION")
        else None,
    }
    overrides = {k: v for k, v in overrides.items() if v is not None}
    if overrides:
        run = dataclasses.replace(run, live=dataclasses.replace(live, **overrides))
    return run


def make_data_source(run: RunConfig, strategy, calendar: TradingCalendar):
    provider = make_provider(
        run.live.data_provider,
        run.data.cache_dir if run.data.cache_dir != "default" else default_cache_dir(),
    )
    if isinstance(provider, CachedProvider):
        provider.max_age = timedelta(hours=1)
    loader = DataLoader(provider, proxies=run.proxies_for(strategy))
    symbols = strategy.data_symbols()

    def source(signal: pd.Timestamp):
        loader._bars.clear()  # re-read the (refreshed) cache on every run
        return loader.load(symbols, end=signal, calendar=calendar, use_proxies=run.data.use_proxies)

    def prices(symbol: str, session: pd.Timestamp) -> tuple[float, float] | None:
        bars = loader.bars(symbol)
        if session not in bars.index:
            return None
        row = bars.loc[session]
        return float(row["open"]), float(row["close"])

    return source, prices


def make_broker(run: RunConfig, calendar: TradingCalendar, prices, state_root: Path) -> Broker:
    name = run.live.broker.lower()
    if name == "alpaca":
        from trader.live.alpaca_broker import AlpacaBroker

        return AlpacaBroker(paper=run.live.paper)
    if name == "local":
        return LocalBroker(
            state_root / "local_broker.json",
            prices,
            calendar,
            initial_cash=run.live.local_initial_cash,
            costs=run.backtest_config().costs,
        )
    raise SystemExit(f"unknown broker {run.live.broker!r} (alpaca | local)")


def build_runner(run: RunConfig) -> LiveRunner:
    strategy = run.build_strategy()
    calendar = TradingCalendar.nyse(start="1970-01-01")
    source, prices = make_data_source(run, strategy, calendar)
    instance = (
        os.environ.get("TRADER_INSTANCE_ID") or run.live.instance_id or strategy.name
    ).replace("_", "-")
    state_root = Path(os.environ.get("TRADER_STATE_DIR") or run.live.state_dir) / instance
    broker = make_broker(run, calendar, prices, state_root)
    return LiveRunner(run, strategy, broker, calendar, source)


def _cmd_run(args) -> int:
    run = config_from_env(args.config)
    if args.broker:
        run = dataclasses.replace(run, live=dataclasses.replace(run.live, broker=args.broker))
    runner = build_runner(run)
    if args.once:
        session = pd.Timestamp(args.session) if args.session else None
        report = runner.run_once(session, force=args.force, dry_run=True if args.dry_run else None)
        print(json.dumps(dataclasses.asdict(report), indent=1, default=str))
        return 1 if report.status == "error" else 0
    if args.dry_run:
        runner.cfg = dataclasses.replace(runner.cfg, dry_run=True)
    runner.run_forever()
    return 0


def _cmd_status(args) -> int:
    run = config_from_env(args.config)
    runner = build_runner(run)
    st = runner.state.data
    print(
        f"instance      {runner.instance}  (strategy {runner.strategy.name}, broker {runner.broker.name}, {run.live.account_mode})"
    )
    print(f"last session  {st.get('last_session')}   last signal {st.get('last_signal')}")
    if st.get("last_report"):
        print(f"last report   {st['last_report']}")
    if st.get("ledger"):
        led = st["ledger"]
        print(f"ledger cash   {led['cash']:.2f}   positions {led['positions']}")
    if st.get("pending_retries"):
        print(f"pending       {len(st['pending_retries'])} retries")
    if args.broker:
        acct = runner.broker.account()
        print(
            f"account       equity {acct.equity:.2f} cash {acct.cash:.2f} blocked {acct.trading_blocked}"
        )
        print(f"positions     {runner.broker.positions()}")
    return 0


def _cmd_health(args) -> int:
    run = config_from_env(args.config)
    strategy = run.build_strategy()
    instance = (
        os.environ.get("TRADER_INSTANCE_ID") or run.live.instance_id or strategy.name
    ).replace("_", "-")
    beat = Path(os.environ.get("TRADER_STATE_DIR") or run.live.state_dir) / instance / "heartbeat"
    if not beat.exists():
        print("no heartbeat yet")
        return 1
    age = datetime.now(NY) - datetime.fromisoformat(beat.read_text().strip())
    ok = age.total_seconds() <= args.max_age
    print(f"heartbeat {age.total_seconds():.0f}s ago ({'ok' if ok else 'stale'})")
    return 0 if ok else 1


def register_cli(sub) -> None:
    sp = sub.add_parser("live", help="run a strategy against a broker")
    lsub = sp.add_subparsers(dest="live_command", required=True)

    rp = lsub.add_parser("run", help="run the live loop (or one session with --once)")
    rp.add_argument(
        "config",
        nargs="?",
        help="config path or strategy name (default: $TRADER_CONFIG / $TRADER_STRATEGY)",
    )
    rp.add_argument("--once", action="store_true", help="process a single session and exit")
    rp.add_argument("--session", help="session to process with --once (YYYY-MM-DD, default: today)")
    rp.add_argument("--dry-run", action="store_true", help="plan orders but submit nothing")
    rp.add_argument("--force", action="store_true", help="rebalance even if the schedule says no")
    rp.add_argument("--broker", choices=["alpaca", "local"], help="override the configured broker")
    rp.set_defaults(func=_cmd_run)

    stp = lsub.add_parser("status", help="show state, ledger and (optionally) broker positions")
    stp.add_argument("config", nargs="?")
    stp.add_argument("--broker", action="store_true", help="also query the broker")
    stp.set_defaults(func=_cmd_status)

    hp = lsub.add_parser("health", help="exit 0 if the runner heartbeat is fresh")
    hp.add_argument("config", nargs="?")
    hp.add_argument("--max-age", type=int, default=600, help="seconds")
    hp.set_defaults(func=_cmd_health)
