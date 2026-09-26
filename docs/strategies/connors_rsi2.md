# Connors RSI(2) mean reversion (ETF basket)

Registry name `connors_rsi2`, module `src/trader/strategies/connors_rsi2.py`, config `configs/strategies/connors_rsi2.yaml`, results `results/connors_rsi2/`.

## Summary

- Short-term mean reversion from Connors & Alvarez: buy a short, sharp pullback in an uptrend and sell as soon as price recovers.
- Entry: 2-period Wilder RSI closes below 5 while the close is above the 200-day SMA. Exit: the close rises above the 5-day SMA. No stops.
- The book applies the rules to the S&P 500. Here they run on 13 liquid US equity ETFs, with fixed 20% slots (at most five positions). Idle capital goes to T-bills (BIL).
- Evaluated at every close, filled at the next open. Long-only and unlevered.
- Result in this harness: 3.9% CAGR, Sharpe 0.36, max drawdown −14%, 2000-01 → 2026-09. After publication: 3.0% CAGR, Sharpe 0.29. The raw edge is real and matches the dossier's replication, but harness costs take about 45% of it.

## Sources

- Connors, L. & Alvarez, C. (2008). *Short Term Trading Strategies That Work.* TradingMarkets Publishing, ISBN 978-0981923901, ch. 9 (the 2-period RSI). https://www.biblio.com/book/short-term-trading-strategies-work-larry/d/1510291032
- Connors, L. & Alvarez, C. (2009). *High Probability ETF Trading: 7 Professional Strategies to Improve Your ETF Trading.* TradingMarkets, ISBN 978-0615297415. https://www.biblio.com/9780615297415
- StockCharts ChartSchool, "RSI(2)". This is a secondary statement of the chapter 9 rules; the book text itself was not read. https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/rsi-2
- Baltussen, G., van Bekkum, S. & Da, Z. (2019). "Indexing and Stock Market Serial Dependence Around the World." *Journal of Financial Economics* 132(1), 26–48. https://doi.org/10.1016/j.jfineco.2018.07.016 (accepted manuscript: https://www3.nd.edu/~zda/Indexing.pdf)
- Nagel, S. (2012). "Evaporating Liquidity." *Review of Financial Studies* 25(7), 2005–2039. https://academic.oup.com/rfs/article-abstract/25/7/2005/1602153
- **Publication date used for the out-of-sample split: 2008-11-01**, the month *Short Term Trading Strategies That Work* was published.
  - The RSI(2) idea circulated in TradingMarkets articles in the mid-2000s. So part of the 2005–2008 "in-sample" period was arguably already public.
  - The dossier's more conservative out-of-sample start is 2009-01-01. The two dates differ by only two months.

## Rules as implemented

Evaluated at every close (`Daily()` schedule), on total-return-adjusted closes:

| Step | Rule |
|---|---|
| Eligibility | The symbol has a price today and a full `trend_sma` (200) window of non-NaN closes. Symbols not yet listed, or without enough history, never get weight. |
| Entry, symbol not held | close > SMA(200) **and** Wilder RSI(2) < 5 |
| Exit, symbol held | close > SMA(5), where the SMA includes today's close. The exit is filled at the next open. No stops and no time stop. |
| Slots | Each new position gets `slot_weight` = 0.20, so there are at most floor(1/0.20) = 5 positions. With more candidates than free slots, the lowest RSI goes first (ties broken by symbol name). An entry is capped at the unallocated weight if drifted holdings leave less than one slot. |
| Continuing holdings | Keep their **current** weight (`ctx.weights[sym]`), so the planner does not trim winners or top up losers every day. |
| "Held" | `ctx.positions[sym] > 0`. Positions include pending orders, so an entry is never doubled. A pending entry (in `positions` but not yet in `weights`) is counted at `slot_weight`. A position worth under 10% of a slot is treated as dust: it is sold and does not take a slot (see "Implementation notes"). |
| Idle capital | 1 − Σ(risky weights) goes to BIL. |
| Execution | Next-open fills (`next_open`), whole shares, `rebalance_band: 0.02`. Entries and exits always trade; BIL and holdings only trade on moves of more than 2%. |

- **Indicators.** RSI uses `trader.indicators.rsi`: Wilder smoothing, an EWM with α = 1/n. It runs on a trailing window of 100 rows. The seed's residual weight after 100 rows is 2⁻¹⁰⁰, so the value matches a full-history RSI. The SMA window is the last 200 (or 5) closes.
- **Parameters.** These are the published values:

  | Parameter | Value |
  |---|---|
  | `rsi_period` | 2 |
  | `entry_threshold` | 5.0 |
  | `trend_sma` | 200 |
  | `exit_sma` | 5 |
  | `slot_weight` | 0.20 |
  | `cash_asset` | BIL |

- **Robustness grid.** `entry_threshold` ∈ {10, 15}, `exit_sma` ∈ {3, 10}, `trend_sma` ∈ {150}, `slot_weight` ∈ {0.10, 0.33}.
- **Verification.** The backtest's 2,217 entry and exit fills match, one for one, an independent reference loop that computes full-history indicators separately for each symbol.

## ETF mapping and proxies

| Role | Symbols | Real data from | Proxy before inception |
|---|---|---|---|
| Broad index | SPY | 1993-01-29 | VFINX (not needed after 2000) |
| | QQQ | 1999-03-10 | RYOCX (Rydex OTC; NAV only) |
| | IWM | 2000-05-26 | NAESX (Vanguard Small-Cap Index; NAV only) |
| | DIA | 1998-01-20 | none |
| Sectors | XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY | 1998-12-22 | none |
| Cash | BIL | 2007-05-30 | `@tbill`: synthetic 3-month T-bill index from ^IRX, net of a 0.10% fee |

- The proxies come from `proxies_for(...)`. DIA and the sector SPDRs are fully warmed up for the 200-day SMA before the 2000-01-03 start.
- Proxy data makes up 24.8% of exposure-days. Almost all of it is the synthetic T-bill series before 2007, because BIL is the largest holding most of the time.
- The `etf_era` variant starts on 2008-04-01, so it holds no proxy data.

## Deviations from the source

- **Next-open instead of same-close fills.** Connors buys and sells on the close that produces the signal. Daily bars can't do that, so this implementation decides at the close and fills at the next open.
  - The dossier's SPY replication keeps about 85–105% of the book's return with next-open fills.
  - Here, filling at the next close costs about 0.35 pp of CAGR, and a two-session delay costs about 0.5 pp.
- **Basket of 13 ETFs instead of the S&P 500 alone.** Each position has a fixed 20% slot instead of 100%. This raises the trade count from about 3–5 a year (SPY alone) to about 41 round trips a year. It also concentrates risk when many ETFs signal together (see the critiques).
- **T-bills instead of uninvested cash.** BIL holds idle capital, so the strategy earns the T-bill rate.
  - The price is turnover: every entry and exit also trades BIL, which doubles traded notional.
  - BIL fills account for **49% of all trading costs**.
- **Long-only.** The book's short-side mirror (RSI(2) > 95 below the 200-day SMA) is not implemented.
- **Time-varying universe.** Only symbols with a full 200-day history are eligible. In the proxy era, QQQ (before 1999-03) and IWM (2000-01 → 2000-05) trade on mutual-fund NAVs. Their "open" equals the NAV, so a next-open fill there is really a next-close fill.
- **Harness realism the book lacks.** Fills are in whole shares, with 5 bps adverse slippage on every fill (ETFs and BIL alike) plus SEC/FINRA/CAT fees. Buys are scaled down when cash is short.
- **Dust guard.** This is a defensive addition, not part of the published rules (see "Implementation notes"). It never triggers in the base run.

## Known critiques and post-publication evidence

- **No peer-reviewed out-of-sample test of the exact rules.**
  - All published evidence comes from practitioner backtests, often with same-close fills and only 1990s-onward ETF data.
  - The "83.6% win rate" quoted from the book is unverified. The dossier's SPY replication for 1993–2008 gives 83.7% on 49 trades.
  - The robustness grid in this harness counts as another 13 trials. The local Deflated Sharpe probability is 0.36.
- **Index-level reversal is a post-1999 regime** (Baltussen, van Bekkum & Da 2019).
  - The S&P 500's daily AR(1) was +0.103 before 1999-03 and −0.076 after. The authors tie the change to the growth of index futures and ETFs.
  - Before the 1990s, index returns trended. The effect could reverse again if that mechanism changes.
  - With a one-day lag the post-1999 coefficient stays negative, which supports next-open fills.
- **Tail risk in crashes that begin above the 200-day SMA.** The strategy has no stops and buys falling markets. Signals across equity ETFs are highly correlated, so all five slots tend to fill on the same day. At those moments the basket is 100% long equities.
  - **2011-07-28:** IWM, DIA, XLB, XLP and XLV all entered together. The August 2011 selloff produced the strategy's maximum drawdown (−14.2%, peak 2011-05-31 → trough 2011-08-08) and three of its four worst trades (−8.5% to −12.6%).
  - **2020-02-24/25:** XLI, then SPY, DIA, XLF and XLY, entered as the COVID crash started, all still above their 200-day SMAs. The book exit got the strategy out by 2020-03-05, for −5.7% over the crash window.
  - With `exit_sma = 10` the positions were held into March 2020, for a −36% drawdown.
  - Nagel (2012): short-term reversal profits are payment for providing liquidity. They are largest when volatility is high, which is also when drawdown risk is highest.
- **The per-trade edge roughly halved after 2009.**
  - Dossier, SPY with next-open fills and zero costs: +112 bp per trade before 2009, +49 bp after.
  - Here, across the basket and after slippage: +52 bp per round trip for entries before 2009 (315 trades, 69.5% winners) and +33 bp after (793 trades, 67.6% winners).
  - The strategy's out-of-sample Sharpe is half its in-sample Sharpe.

## Results

The base run covers 2000-01-03 → 2026-09-25 with published defaults, next-open fills, 5 bps slippage and a 0.02 band. Source: `results/connors_rsi2/summary.json`.

| Metric | Full period | In-sample (2000-01 → 2008-10) | Out-of-sample (2008-11 → 2026-09) |
|---|---|---|---|
| CAGR | 3.92% | 5.70% | 3.05% |
| Volatility | 5.83% | 4.59% | 6.35% |
| Sharpe (excess of T-bills) | 0.36 | 0.57 | 0.29 |
| Sortino | 0.51 | 0.85 | 0.40 |
| Max drawdown | −14.2% | −4.8% | −14.2% |
| Calmar | 0.28 | 1.19 | 0.21 |
| Mean T-bill rate | 1.92% | 3.02% | 1.38% |
| SPY buy-and-hold CAGR | 8.31% | −3.05% | 14.39% |

- **Turnover and costs:**

  | Measure | Value |
  |---|---|
  | Turnover | 16.3× equity a year, one-way |
  | Cost drag | 1.73% a year |
  | Fills a year | 130 in total: 83 in ETFs, 47 in BIL |

- **Trade statistics** (reconstructed from `trades.parquet`):

  | Measure | Value |
  |---|---|
  | Round trips | 1,108, about 41.5 a year |
  | Winners | 68.1% |
  | Average trade | +38.8 bp after slippage |
  | Holding time | median 3 sessions, mean 3.7 |
  | Average risky weight | 11.9% |
  | Time with any ETF held | 26.4% of days |

- **Market exposure:** beta to SPY is 0.11, with correlation 0.36.
- **Significance:**
  - Probabilistic Sharpe vs 0 is 0.97.
  - The local Deflated Sharpe is 0.36, over 14 trials.
  - The bootstrap 90% interval for Sharpe is [0.12, 0.62], and for CAGR [2.5%, 5.3%].
  - The probability of beating SPY's Sharpe is 0.38.
- **Worst periods:**
  - Worst calendar years: 2011 (−5.6%), 2018 (−5.0%), 2022 (−2.7%) and 2008 (−2.5%).
  - Worst month: −8.2%. The longest time under water was 804 sessions.

### Crisis returns

| Window | Strategy return |
|---|---|
| Dot-com bust (2000-03 → 2002-10) | +19.1% |
| GFC (2007-10 → 2009-03) | +1.7% |
| Euro/US downgrade (2011-04 → 2011-10) | −8.0% |
| Q4 2018 selloff | −3.8% |
| COVID crash (2020-02 → 2020-03) | −5.7% |
| 2022 inflation bear | −4.2% |
| 2025 tariff shock (2025-02 → 2025-04) | −1.5% |

### Robustness suite (`variants.json`)

| Variant | CAGR | Vol | Sharpe | Sortino | Max DD | Calmar | Turnover | Cost drag |
|---|---|---|---|---|---|---|---|---|
| **base** | 3.92% | 5.83% | 0.36 | 0.51 | −14.2% | 0.28 | 16.3× | 1.73% |
| costs ×0 | 5.67% | 5.83% | 0.65 | 0.93 | −13.9% | 0.41 | 16.3× | 0.00% |
| costs ×2 | 2.20% | 5.83% | 0.07 | 0.10 | −14.7% | 0.15 | 16.3× | 3.40% |
| costs ×4 | −1.17% | 5.88% | −0.50 | −0.67 | −42.2% | −0.03 | 16.3× | 6.59% |
| fill at next close | 3.57% | 5.71% | 0.31 | 0.44 | −14.8% | 0.24 | 16.3× | 1.72% |
| delay 2 sessions | 3.45% | 5.65% | 0.29 | 0.41 | −13.9% | 0.25 | 16.3× | 1.72% |
| entry_threshold = 10 | 3.64% | 7.59% | 0.26 | 0.36 | −15.7% | 0.23 | 28.4× | 3.01% |
| entry_threshold = 15 | 2.83% | 8.57% | 0.14 | 0.20 | −16.5% | 0.17 | 37.5× | 3.94% |
| exit_sma = 3 | 2.27% | 4.90% | 0.09 | 0.12 | −15.4% | 0.15 | 16.9× | 1.76% |
| exit_sma = 10 | 4.01% | 8.80% | 0.27 | 0.37 | −36.4% | 0.11 | 15.0× | 1.59% |
| trend_sma = 150 | 3.54% | 5.57% | 0.31 | 0.43 | −13.1% | 0.27 | 15.3× | 1.62% |
| slot_weight = 0.10 | 2.90% | 4.24% | 0.24 | 0.34 | −14.3% | 0.20 | 9.8× | 1.03% |
| slot_weight = 0.33 | 4.23% | 7.25% | 0.34 | 0.49 | −16.6% | 0.25 | 21.0× | 2.23% |
| ETF era only (from 2008-04-01) | 3.00% | 6.26% | 0.28 | 0.40 | −14.2% | 0.21 | 16.9× | 1.78% |

The costs ×4 row falls to −42% because costs bleed away returns steadily from 2006 to 2023, not because of a single crash. The exit_sma = 10 drawdown runs from 2018-10 to 2020-03.

### Comparison with the source and the dossier's replication

The dossier replicated SPY alone at 100% of capital, with 0% cash, 1 bp a side and next-open fills. It found 3.4% CAGR, Sharpe 0.70 and max drawdown −8% for 1993–2008, and 2.1%, 0.41 and −15.5% for 2009–2026.

- **The edge before costs is there, and larger than in the single-ETF version.**
  - At zero cost the basket earns Sharpe 0.89 in-sample and 0.57 out-of-sample, against the replication's 0.70 and 0.41.
  - Trading 13 ETFs instead of one raises the trade count about tenfold, and the diversification improves the Sharpe.
  - Win rates (68%) and average trades (+39 bp net) are a little below the SPY-only figures (74–78%, +50–110 bp gross). Some ETFs have weak edges: XLU averages −4 bp, XLV +14 bp and DIA +15 bp.
- **Costs are the big gap.** The spec expected the costs ×2 variant to "barely move". Instead the Sharpe falls from 0.36 to 0.07. There are three reasons:
  1. The harness charges a flat 5 bps on every fill. The dossier's replication assumed 1 bp, and its own cost table suggests 0.5–3 bp for these ETFs after 2009.
  2. Every entry and exit also trades BIL, so each round trip in one slot costs about 20 bp of the slot: 10 bp on the ETF and 10 bp on BIL.
  3. The net edge per trade is only about 40–60 bp.

  Together, costs consume about 1.7 pp of the roughly 3.7 pp a year of gross excess return. The harness's 5 bps is a deliberately conservative placeholder. The true cost of this strategy depends on actual opening-auction prices for SPY, the sector SPDRs and BIL, and has not been validated.
- **Exposure is at the low end of the spec's 20–50% range:**
  - 26% of days hold at least one ETF.
  - The average invested weight is only 12%.
  - Most of the CAGR is T-bill carry. Excess return over T-bills is about 2% a year net, or 3.7% before costs.
- **Looser entry thresholds did not help here,** unlike the dossier's zero-cost SPY sensitivity (RSI < 10–15 improved Sharpe). Here they raise turnover to 28–38× and cost drag to 3.0–3.9% a year, and volatility and drawdown both rise.
- **Honest assessment.**
  - The implementation matches the rules exactly, and the gross edge is consistent with the literature.
  - Net of this harness's costs, the strategy is a low-return, low-beta sleeve: Sharpe 0.29 after publication, well below SPY's 0.75 over the same period. Its Sharpe is not robust to doubled costs.
  - It is not a standalone live candidate at these cost assumptions.
  - It could be worth revisiting as a diversifying overlay only if measured open-auction costs are near 1–2 bp and the BIL churn is removed (for example, idle cash held as an overlay on a T-bill or equity core). Both would be design changes beyond the published rules.

## Implementation notes

- **Performance.** Each call reads only the last 205 closes (`ctx.history("close", warmup)`), and computes the RSI over the last 101 of them. A full run of 6,700 sessions plus the 13-variant suite takes about 100 seconds with 2 workers.
- **Dust guard: a harness quirk that only appears with `delay ≥ 2`.** The engine projects `positions` as current holdings plus pending orders. The problem shows up in this sequence:
  1. The strategy decides an exit while its entry is still pending.
  2. The queued sell is sized to the full pending buy.
  3. The buy then fills slightly smaller (it was scaled down for cash), and the sell is capped at the shares actually held.

  At the next decision the projected position is therefore negative (e.g. −2 shares). The planner answers with a "covering" buy of 2 shares, which leaves a few stray shares.

  In the `delay_2` variant, those stray shares were once read as a held pending entry and assigned a 20% slot. That produced a 1.2 gross target, which `validate_weights` scaled down (2017-08-11 and 2021-02-23).

  The strategy now ignores projected positions worth under 10% of a slot. It sells them, and they take no slot. The base run is unchanged by this; `delay_2` moved from Sharpe 0.28 to 0.29.
