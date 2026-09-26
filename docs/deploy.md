# Running strategies live

Each strategy runs in its own container built from the same image. A container reads one strategy config, wakes on every NYSE session, and when the strategy's schedule says so it submits orders to Alpaca. The code path is the same one the backtester uses. `tests/test_live.py::test_live_runner_matches_backtest_exactly` steps the runner through two years of sessions and asserts the same decisions, the same orders and the same final equity as the backtest.

## Quick start (paper)

```sh
docker build -t trader .
cp deploy/env/example.env deploy/env/sixty-forty.env     # paper API keys go here
docker compose -f deploy/docker-compose.yml up -d
docker compose -f deploy/docker-compose.yml logs -f sixty-forty
```

Without Alpaca keys, `TRADER_BROKER=local` runs against a file-backed simulated account. It fills at the next open with the backtest cost model, which is useful for forward-testing a strategy on live data:

```sh
docker run -d --name gtaa-forward -e TRADER_STRATEGY=faber_gtaa -e TRADER_BROKER=local \
  -v gtaa-forward:/state trader
```

Useful one-offs (they work the same outside Docker in the nix devshell):

```sh
trader live run faber_gtaa --once --dry-run      # what would it trade today?
trader live run faber_gtaa --once --force        # rebalance now, schedule or not
trader live status faber_gtaa --broker           # state, ledger, account positions
trader live health faber_gtaa                    # used by the Docker HEALTHCHECK
```

## Adding and removing strategies

1. The strategy needs a file in `src/trader/strategies/` and a config in `configs/strategies/<name>.yaml`. The config drives both backtests and live runs.
2. Add a service to `deploy/docker-compose.yml`. Copy an existing block and change the service name, `TRADER_STRATEGY`, the env file and the volume.
3. `docker compose up -d --build`. To remove a strategy, delete its block and run `docker compose up -d --remove-orphans`. Its state volume stays until you delete it.

## When things happen

| `execution.mode` | Runner wakes (NY time) | Orders | Mirrors backtest |
|---|---|---|---|
| `next_open` (default) | 08:45 on each session | `day` market orders queued for the open, or `opg` with `order_style: auction` | signal at close of t, fill at open of t+1 |
| `next_close` | 25 min before the close (12:35 on half-days) | `cls` with `order_style: auction` | signal at close of t, fill at close of t+1 |

The runner processes each session once. It records the session in `/state/<instance>/state.json` and writes a full report (targets, orders, account snapshot) to `/state/<instance>/runs/<date>.json`.

## Accounts: dedicated vs shared

Alpaca allows up to three paper accounts and one live account per user. Positions are account-level, so strategies must not trample each other.

* **`account_mode: dedicated`** (default): the strategy treats the whole account (× `capital_fraction`) as its own. Use one paper account per strategy.
* **`account_mode: shared`**: several containers share one account. Each container keeps a **ledger** of its own shares and cash. It rebuilds the ledger from its own fills (matched by client order id prefix) and the dividends paid on its shares, and it never sells shares it did not buy. Set `TRADER_ALLOCATION` (dollars) per container, and keep allocations summed below the account's equity. Caveats:
  * Two containers trading the same symbol in opposite directions at the same time trip Alpaca's wash-trade protection. The runner retries rejected orders as market orders a few minutes after the open (`retry_after_open_minutes`).
  * Dividends are credited using the ledger's shares on the pay date. This is a close approximation of the record-date holding.
  * Give each deployment a unique `instance_id` (default: the strategy name) if you run one strategy twice.

## Order style and the opening auction

Alpaca's `opg`/`cls` auction orders are documented as account-tier dependent. Standard accounts should use the default `order_style: market`, which sends `day` market orders before the open that execute when trading starts. The backtest's default 5 bps of slippage against the official open is sized for this. With `order_style: auction`, the runner falls back to market orders automatically if Alpaca refuses an auction order. Fractional shares require `order_style: market`.

## Safety rails

* **Paper by default.** Real money needs `ALPACA_PAPER=false` *and* `TRADER_ALLOW_LIVE=yes`.
* **Dry run:** `TRADER_DRY_RUN=true` plans and logs orders but sends nothing.
* **Kill switch:** `TRADER_HALT=1`, or create `/state/<instance>/HALT`. Existing positions are left alone.
* **Stale data guard:** the runner refuses to trade if any symbol's latest bar is not the signal session.
* **Turnover guard:** a rebalance that would trade more than `max_turnover` × equity is aborted.
* **Idempotency:** client order ids are `<instance>-<signal date>-<symbol>-<b|s>`, so a restarted container cannot double-submit.
* **Health check:** `trader live health` fails if the loop has not written a heartbeat in 10 minutes.

## Where live results will differ from the backtest

* **Fill prices.** Queued market orders fill near, not at, the official open. The backtest charges 5 bps per fill; compare `runs/*.json` fill prices with the backtest's `signal_price` to calibrate.
* **Paper trading is not the real market.** Alpaca paper fills at the quote, charges no regulatory fees, pays no dividends, and randomly partially fills about 10% of orders.
* **Data.** Live signals default to Yahoo total-return bars, the same data as the backtest. `data_provider: alpaca` is available, but its adjusted history has had corporate-action errors.
