# Backtest results and recommendation

Twelve published strategies were each implemented on their own branch, backtested in the same harness, and compared with two benchmarks: SPY buy-and-hold and a 60/40 SPY/AGG mix.

| Report | Window | What it answers |
|---|---|---|
| [`reports/comparison.html`](../reports/comparison.html) ([md](../reports/comparison.md)) | 2000-01 → 2026-09 | The main comparison. Each strategy runs exactly as published, deciding on the last session of the month. |
| [`reports/comparison-tranched.html`](../reports/comparison-tranched.html) ([md](../reports/comparison-tranched.md)) | 2000-01 → 2026-09 | The same monthly strategies split into 4 tranches on staggered days, which removes rebalance-timing luck. These are the versions to deploy. |
| [`reports/comparison-etf-era.html`](../reports/comparison-etf-era.html) ([md](../reports/comparison-etf-era.md)) | 2008-07 → 2026-09 | Real ETF prices only, with no pre-inception proxies. This checks the proxy splicing. |

Per-strategy write-ups (sources, rules, deviations, critiques) are in `docs/strategies/`. The research behind the selection is in `docs/research/`.

## How the tests were made realistic

- **No look-ahead.** Decisions use data up to the close; orders fill at the next session's open, as Alpaca market orders queued before the open. A contract test perturbs all future data and checks that no past decision changes.
- **Costs from real market structure.** Slippage on every fill is tiered by liquidity: 2 bps for SPY/TLT/BIL-class ETFs, 4 bps for EFA/EEM/sector ETFs, 6 bps for DBC/GSG/country ETFs. On top of that come Alpaca's pass-through fees (SEC $20.60/M on sales, FINRA TAF, CAT).
- **Robustness checks.** Every strategy was re-run at 0×/2×/4× costs, with next-close and one-day-late fills, with decisions 5 and 10 sessions early, and across its published parameter neighbours.
- **Account mechanics.** Whole shares, a $100k account, no leverage, and idle cash earning nothing (as at Alpaca). Strategies hold BIL explicitly when they want T-bill returns.
- **History and data.** Total-return data from 2000, spanning two 50% bear markets, 2008, COVID, the 2022 stock-and-bond selloff and the 2025 tariff shock. Pre-inception mutual-fund proxies are used where an ETF didn't exist yet, and the ETF-era report shows the result without them.
- **Statistics.** Stationary-bootstrap confidence intervals, the Probabilistic and Deflated Sharpe Ratio across all 175 configurations run (about 77 effective independent trials), and in-sample vs post-publication splits.
- **Backtest/live parity.** The live runner uses the same code path as the backtester. A test drives it through two years of sessions and asserts identical decisions, orders and final equity. On real data, the three recommended containers were run in Docker for the 2026-09-24 signal, and their target weights matched the backtest's to four decimals.

## Headline results (main report, 2000-01 → 2026-09)

| Strategy | CAGR | Vol | Sharpe | Max DD | Post-publication Sharpe | Verdict |
|---|---:|---:|---:|---:|---:|---|
| Adaptive Asset Allocation | 10.7% | 9.5% | 0.91 | −19.2% | 0.83 | **Deploy** |
| Defensive Asset Allocation (Keller) | 9.9% | 10.5% | 0.77 | −18.6% | 0.51 | Watchlist |
| Time-series momentum, long/flat | 5.7% | 5.1% | 0.74 | −10.4% | 0.53 | **Deploy** (diversifier) |
| Equal risk contribution | 6.3% | 6.7% | 0.65 | −19.1% | 0.45 | Watchlist |
| Risk parity + trend (Clare) | 6.2% | 6.7% | 0.65 | −11.3% | 0.59 | Watchlist |
| Faber GTAA-5 | 6.3% | 7.6% | 0.58 | −15.4% | 0.41 | Watchlist |
| Antonacci GEM | 9.7% | 15.1% | 0.56 | −33.7% | 0.41 | Watchlist |
| Volatility-managed SPY | 6.9% | 10.4% | 0.51 | −23.3% | 0.76 | **Deploy** (equity sleeve, see below) |
| Connors RSI(2) basket | 4.7% | 5.8% | 0.49 | −14.1% | 0.41 | Reject |
| *60/40 benchmark* | 6.8% | 11.5% | 0.46 | −35.6% | – | |
| *SPY buy & hold* | 8.4% | 19.0% | 0.42 | −54.6% | – | |
| Sector momentum | 8.1% | 18.2% | 0.41 | −51.3% | 0.41 | Reject |
| Country momentum | 6.2% | 20.5% | 0.30 | −62.8% | 0.50 | Reject |
| Turn of the month | 3.3% | 8.1% | 0.20 | −22.0% | 0.11 | Reject (negative control) |

## What the three reports agree on

1. **AAA is the most robust strategy tested.** It ranks first in all three reports: Sharpe 0.91 in the main report, 0.80 tranched, 0.89 on ETF-era data. Its Sharpe was 0.88 in the 2010s, and its post-publication Sharpe (0.83) holds up. It was the only strategy whose Deflated Sharpe cleared 0.95 in the main report. The bootstrap gives it a 100% chance of beating SPY on Sharpe.
2. **Month-end results include luck.** Tranching lowered most monthly strategies' Sharpe: AAA 0.91 → 0.80, DAA 0.77 → 0.69, and vol-managed SPY 0.51 → 0.45 (its drawdown deepened from −23% to −29%). The month-end run of AAA happened to sidestep COVID (−6.7%), while its tranched version lost 20% there. Plan around the tranched numbers.
3. **The edge came in bear markets.** In the 2010–2019 bull market, SPY returned 13.3% a year and a plain 60/40 had a 1.07 Sharpe. No strategy beat SPY's return after 2010. The strategies earned their long-run advantage in 2000–2009, when SPY lost money.
4. **Several published strategies failed out of sample.** Sector and country momentum showed no momentum premium in ETFs since 2000. Turn-of-the-month disappeared as the literature predicted, which also shows the harness does not invent edges. RSI(2)'s per-trade edge is real but too small after costs.

### Sub-periods (tranched versions; "blend" = equal thirds of the three recommended strategies, reset monthly)

CAGR / Sharpe / max drawdown:

| | 2000–09 | 2010–19 | 2020–26 | 2016–26 |
|---|---|---|---|---|
| AAA ×4 | 11.0% / 0.89 / −15% | 7.4% / 0.88 / −10% | 9.9% / 0.64 / −23% | 8.7% / 0.66 / −23% |
| TSMOM ×4 | 7.5% / 0.92 / −8% | 4.3% / 0.80 / −6% | 4.1% / 0.24 / −14% | 4.1% / 0.37 / −14% |
| Vol-managed SPY ×4 | 1.8% / −0.04 / −29% | 9.2% / 0.81 / −14% | 8.6% / 0.54 / −20% | 9.6% / 0.71 / −20% |
| **Blend** | **6.8% / 0.63 / −9%** | **7.1% / 0.93 / −7%** | **7.6% / 0.58 / −18%** | **7.5% / 0.70 / −18%** |
| 60/40 | 2.2% / 0.03 / −36% | 9.7% / 1.07 / −11% | 9.6% / 0.56 / −22% | 9.8% / 0.70 / −22% |
| SPY | −0.8% / −0.05 / −55% | 13.3% / 0.90 / −19% | 15.5% / 0.68 / −34% | 15.0% / 0.75 / −34% |

**Full period:**

| | CAGR | Vol | Sharpe | Max DD | Beta |
|---|---:|---:|---:|---:|---:|
| Blend | 7.1% | 7.2% | 0.72 | −18.1% | 0.25 |
| SPY | 8.3% | 19.2% | 0.41 | −55.2% | 1.00 |

Stress periods for the blend: −3.2% in the GFC, −17.1% in the COVID crash, −8.5% in 2022, −8.1% in the 2025 tariff shock.

**Choosing the third strategy.** The trio was picked for consistency across regimes: the highest worst-sub-period Sharpe (0.58) and the lowest drawdown of the combinations tried.

| Trio (all ×4) | Full-period CAGR | Sharpe | Max DD | 2016–26 Sharpe |
|---|---:|---:|---:|---:|
| AAA + TSMOM + vol-managed SPY (recommended) | 7.1% | 0.72 | −18% | 0.70 |
| AAA + TSMOM + DAA | 7.9% | 0.80 | −19% | 0.61 |
| AAA + TSMOM + GEM | 8.4% | 0.77 | −22% | 0.63 |
| AAA + vol-managed SPY + GEM | 8.7% | 0.69 | −24% | 0.70 |

The DAA trio had the best full-period Sharpe, but a 0.48 Sharpe in 2020–26. The GEM trios earn more but draw down deeper. This choice was made after seeing the results, which is itself a form of selection, so expect some shrinkage.

## Recommendation

Run these three as separate containers, on **paper accounts first**. `deploy/docker-compose.yml` is already set up for them.

| Container | Config | Role |
|---|---|---|
| `aaa` | `configs/tranched/adaptive_asset_allocation_x4.yaml` | Core. Best risk-adjusted return across every view. |
| `tsmom` | `configs/tranched/tsmom_longflat_x4.yaml` | Crisis diversifier. Lowest volatility and drawdown; made money in 2000–02 and 2008. |
| `volspy` | `configs/tranched/vol_managed_spy_x4.yaml` | Equity sleeve. Stays mostly in SPY in calm markets and cuts exposure after turbulent months. Weak on its own over the full period (Sharpe 0.45), but it keeps the blend participating in bull markets. |

Over 2000–2026 the blend's Sharpe was 0.72, against 0.46 for 60/40 and 0.41 for SPY. It ran at about 60% of 60/40's volatility and half its worst drawdown. Over the last decade (2016–26) its Sharpe equalled 60/40's (0.70), so most of the long-run advantage came from 2000–2009. Expect them to trail SPY's raw return in strong bull markets, as they did every year since 2010. If beating SPY's raw return is the goal, none of these strategies did that after 2010.

Before committing real capital:

1. **Paper trade for at least 3 months.** Compare each run report's fill prices (`/state/<instance>/runs/*.json`) with the backtest's assumed 2–6 bps slippage.
2. **One live account.** Alpaca gives one live account per user, so switch to `account_mode: shared` with an `allocation` per container. Each container then trades its own ledger.
3. **Re-run the comparison periodically** with `just compare-all` as new data arrives. Watch the post-publication and rolling-Sharpe views for decay.

## Known limitations

- Pre-2004–2007 results partly use mutual-fund proxies. These report NAV only, so fills in those years are effectively next-close. The "Proxy data" column and the ETF-era report show how much depends on this.
- Yahoo's early SPY history contains a few bad prints (found by the vol-managed agent). They moved Sharpe by less than 0.01.
- Paper trading at Alpaca charges no fees and pays no dividends. The backtest charges fees and credits dividends through total-return prices.
- The Deflated Sharpe counts the configurations run in each report. Across all three reports, more configurations were examined in total, so treat significance as approximate.
