# trader

A daily-bar algorithmic trading harness. It backtests strategies realistically, compares them side by side, and runs each strategy as its own container against Alpaca.

## Quick start

```sh
nix develop            # or `direnv allow` once; pins Python 3.12, uv, ruff, just and syncs .venv
trader list -v         # registered strategies, their universe, schedule and sources
trader backtest sixty_forty --suite          # base run + robustness suite -> results/sixty_forty
trader backtest configs/strategies/buy_and_hold.yaml --start 2005-01-03
just test              # unit + contract tests
```

The first backtest downloads daily bars from Yahoo Finance into `~/.cache/trader` (override with `TRADER_CACHE_DIR`). Every worktree on the machine shares this cache. No API keys are needed for backtesting.

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
