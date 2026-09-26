# trader

A daily-bar algorithmic trading harness. It backtests strategies realistically, compares them side by side, and runs each strategy as its own container against Alpaca.

## Results

Twelve published strategies were researched, implemented and backtested from 2000 to 2026 against SPY and 60/40, with robustness suites, deflated Sharpe ratios, and out-of-sample splits at each source's publication date. Start with **[docs/results.md](docs/results.md)**, which has the findings and the recommended deployment. The interactive reports are in `reports/`:

- `comparison.html`: the main comparison
- `comparison-tranched.html`: timing-luck-free versions
- `comparison-etf-era.html`: real ETF data only

The research behind the strategy selection is in [docs/research/](docs/research/README.md).

## Quick start

```sh
nix develop            # or `direnv allow` once; pins Python 3.12, uv, ruff, just and syncs .venv
trader list -v         # registered strategies, their universe, schedule and sources
trader backtest sixty_forty --suite          # base run + robustness suite -> results/sixty_forty
trader backtest configs/strategies/buy_and_hold.yaml --start 2005-01-03
just test              # unit + contract tests
```

The first backtest downloads daily bars from Yahoo Finance into `~/.cache/trader` (override with `TRADER_CACHE_DIR`). Every worktree on the machine shares this cache. No API keys are needed for backtesting.

## Comparing strategies

```sh
trader compare results/                     # every result folder under results/
trader compare results/a results/b --out reports/ab.html
```

This writes `comparison.html` (a self-contained interactive report with no external assets), `comparison.md` (leaderboard and scorecards) and `comparison.json` (the full payload). All strategies are aligned on their **common date window**, so every number compares like with like. Each strategy gets a scorecard of robustness checks:

* holds up after publication
* significant under the Deflated Sharpe Ratio across all trials
* survives 2× costs
* stable across parameter neighbours
* insensitive to execution timing
* better risk-adjusted return and shallower drawdown than SPY

## Running live

Each strategy is its own container, built from one image and selected with `TRADER_STRATEGY`:

```sh
docker build -t trader .
docker run --rm -e TRADER_STRATEGY=sixty_forty -e TRADER_BROKER=local trader live run --once --dry-run
docker compose -f deploy/docker-compose.yml up -d        # one service block per strategy
```

Paper trading is the default. See [docs/deploy.md](docs/deploy.md) for accounts (dedicated vs a shared account with per-strategy ledgers), order styles, the kill switch and other safety rails, and where live fills will differ from the backtest.

## Design

```
            configs/strategies/<name>.yaml   (one file drives backtest AND live)
                              │
                     ┌────────┴────────┐
                     ▼                 ▼
              trader backtest     trader live            (one container per strategy)
                     │                 │
   DataLoader ──► MarketData ──► Strategy.target_weights(ctx) ──► plan_rebalance ──► orders
   (Yahoo/Alpaca,   (truncated     (stateless, pure)          (shared sizing,     │
    proxies, rf)     at decision                               bands, rounding)   │
                     close)                                          ┌────────────┴──────────┐
                                                                     ▼                       ▼
                                                        SimulatedBroker (costs,       Alpaca OPG/CLS
                                                        next open/close fills)        orders
```

* **Strategies are stateless functions** from history plus current holdings to target weights. They never place orders and don't know whether they are running in a backtest or live. See `src/trader/strategy/base.py`.
* **The same code runs in both paths.** Backtest and live share the calendar (`TradingCalendar`), the schedules (`MonthEnd`, `Daily`, ...), and the order planner (`plan_rebalance`: whole-share sizing, bands, exits). The only thing that differs is where orders go.
* **Adding a strategy means adding one file.** Drop a module into `src/trader/strategies/` with a `@register`-decorated class. It is auto-discovered, and there is no central list to edit, so parallel strategy branches don't conflict.

## Backtest realism

| Concern | How it is handled |
|---|---|
| Look-ahead | Strategies receive a view truncated at the decision close; the next row does not exist. A contract test perturbs all data after a cut date and asserts no earlier decision changes. |
| Execution timing | Decide at the close of *t*, fill at the **open of t+1** (market-on-open) or the close of t+1 (MOC). Same-bar execution is rejected. Live mode submits Alpaca `opg`/`cls` orders to match. |
| Costs | Adverse slippage in bps on every fill (default 5 bps), plus SEC/FINRA sell-side fees. Alpaca commission is $0. The suite re-runs at 0×/2×/4× costs. |
| Share rounding and cash | Whole shares by default (Alpaca OPG/CLS orders cannot be fractional). Sells fill before buys, and buys are scaled down on gap-ups instead of borrowing. |
| Dividends and splits | Total-return adjusted bars. |
| Idle cash | Earns 0% by default (Alpaca brokerage cash), so strategies hold BIL explicitly to earn T-bill returns. |
| Short ETF histories | Optional pre-inception proxies (e.g. VUSTX before TLT) extend tests through 2000-2002. Proxy exposure is reported and an `etf_era` variant re-runs without it. |
| Survivorship | Universes are ETFs rather than today's index constituents. |
| Rebalance timing luck | The suite re-runs every monthly strategy deciding 5 and 10 sessions early. `execution.tranches: N` splits a strategy into N sub-portfolios rebalancing on staggered days (Hoffstein, Faber & Braun), identically in backtest and live. |
| Data gaps | An order whose symbol has no price on the fill day (a proxy gap or halt) is re-tried on the next sessions instead of silently dropped. |
| Overfitting | Published default parameters, post-publication (out-of-sample) split, a parameter-sensitivity grid, rebalance-timing-luck shifts, bootstrap CIs, and the Probabilistic and Deflated Sharpe Ratios. |

## Adding a strategy

1. Create `src/trader/strategies/my_strategy.py`:

   ```python
   from dataclasses import dataclass
   from trader.strategy import Context, MonthEnd, Reference, Strategy, register

   @register
   class MyStrategy(Strategy):
       name = "my_strategy"
       title = "My strategy"
       description = "One paragraph on what it does."
       references = (Reference("Author (Year), Title, Journal", "https://doi.org/..."),)
       publication_date = "2010-01-01"      # results after this are out-of-sample
       proxies = {"TLT": "VUSTX"}           # optional pre-inception history

       @dataclass(frozen=True)
       class Params:
           lookback: int = 12                # defaults = published values
       param_grid = {"lookback": [6, 9, 12]}  # sensitivity runs

       def universe(self):  return ["SPY", "TLT", "BIL"]
       def warmup(self):    return 260
       def schedule(self):  return MonthEnd()

       def target_weights(self, ctx: Context):
           ...                               # return {"SPY": 0.6, "TLT": 0.4}
   ```

2. Add `configs/strategies/my_strategy.yaml` (see `configs/example.yaml` for every key).
3. Run `just test`. The contract tests pick up the new strategy and check for look-ahead, determinism and valid weights.
4. Run `trader backtest my_strategy --suite`.
