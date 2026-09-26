# Country equity momentum (AMP 2013, top tercile)

Strategy name: `country_momentum`. Code: `src/trader/strategies/country_momentum.py`. Config: `configs/strategies/country_momentum.yaml`.

## Summary

This is the long-only version of the country-equity momentum leg in Asness, Moskowitz & Pedersen's "Value and Momentum Everywhere" (AMP).

- At every month-end the strategy ranks AMP's developed equity markets on MOM2–12. MOM2–12 is the 12-month total return that skips the most recent month.
- It holds the top third of the markets, equal-weighted. This is AMP's "P3" tercile portfolio.
- The markets are traded through US-listed, USD-unhedged ETFs: SPY plus iShares MSCI country funds.
- An optional absolute filter (off by default) moves a selected country's slot into T-bills (BIL) when its momentum does not beat BIL's.

## Sources

- Asness, C.S., Moskowitz, T.J., Pedersen, L.H. (2013). "Value and Momentum Everywhere." *Journal of Finance* 68(3), 929–985. DOI [10.1111/jofi.12021](https://doi.org/10.1111/jofi.12021). PDF: <https://pages.stern.nyu.edu/~lpederse/papers/ValMomEverywhere.pdf>. First posted on SSRN (abstract 1363476) on **2009-03-20**; the final sample ends July 2011.
- Daniel, K., Moskowitz, T.J. (2016). "Momentum Crashes." *Journal of Financial Economics* 122(2), 221–247. <https://doi.org/10.1016/j.jfineco.2015.12.002>. This paper is a critique.
- McLean, R.D., Pontiff, J. (2016). "Does Academic Research Destroy Stock Return Predictability?" *Journal of Finance* 71(1), 5–32. <https://doi.org/10.1111/jofi.12365>. This paper provides post-publication decay evidence.

**Out-of-sample split:** `publication_date = "2009-03-20"`, the first SSRN posting. Results after this date count as out-of-sample. The split happens to fall at the bottom of the 2009 bear market, which flatters the OOS numbers. The Results section therefore also gives a split at AMP's sample end (2011-08).

## Rules as implemented

Decisions are made at the close of the last NYSE session of each month (`MonthEnd()`). Orders fill at the next session's open.

1. **Month-end closes.** The strategy takes the total-return-adjusted closes over the last `(lookback + skip + 1) × 23` sessions and keeps the last close of each calendar month. The last row is the decision close.
2. **Signal.** `MOM = close[m − skip] / close[m − skip − lookback] − 1`, computed on those month-end closes (`indicators.trailing_return`). Defaults are `lookback = 12` and `skip = 1`, which gives MOM2–12.
3. **Eligibility.** A country is eligible only when all three conditions hold:
   - all of its last `lookback + skip + 1` month-end closes (14 by default) are present;
   - its signal is finite;
   - it has a close on the decision day (`ctx.is_tradable`).

   So a new listing such as EDEN (first bar 2012-01-26) first becomes eligible at end-February 2013.
4. **Selection.** Eligible countries are sorted by MOM, highest first. Ties are broken by ticker so the result is deterministic. The strategy holds the top `n = max(1, floor(N_eligible × top_fraction + 0.5))`, which is round-half-up. That gives 5 of 15 markets before 2013 and 6 of 17 from 2013-02 onward.
5. **Weights.** Each holding gets `1/n`. Anything not selected is sold.
6. **Absolute filter** (`abs_filter=True`, off by default). A selected country keeps its slot only if its MOM is strictly greater than BIL's return over the same window (`lookback`, `skip`). Otherwise its `1/n` goes to BIL. If BIL has no finite signal, the hurdle is 0.
7. **No eligible country.** The whole portfolio goes to BIL. This never happens in the 2000+ backtest.

| Param | Default (published) | Sensitivity grid |
|---|---|---|
| `lookback_months` | 12 | 6 |
| `skip_months` | 1 | 0 (MOM1–12) |
| `top_fraction` | 0.3333333333 (tercile) | 0.2, 0.5 |
| `abs_filter` | False | True |

## ETF mapping and proxies

The universe is AMP's 18 developed markets. Portugal is missing: PGAL is delisted and not on Yahoo.

| Market | ETF | First real bar |
|---|---|---|
| United States | SPY | 1993-01-29 |
| Australia, Austria, Belgium, Canada, France, Germany, Hong Kong, Italy, Japan, Netherlands, Spain, Sweden, Switzerland, UK | EWA, EWO, EWK, EWC, EWQ, EWG, EWH, EWI, EWJ, EWN, EWP, EWD, EWL, EWU | 1996-03-18 |
| Denmark | EDEN | 2012-01-26 |
| Norway | ENOR | 2012-01-24 |
| Portugal | none | — |
| Cash (absolute filter only) | BIL | 2007-05-30 |

**Proxies.** The strategy uses `proxies_for(universe)`, which gives SPY ← VFINX and BIL ← `@tbill`. The `@tbill` series is synthetic, accrued from ^IRX net of 0.10%.

- Neither proxy is ever held in the base run: `proxy_share = 0.0`. SPY has real data from 1993, and BIL is not held without the absolute filter.
- The country ETFs have no proxies. Denmark and Norway simply join the cross-section once they have 14 month-end closes.

**Data check.** No country ETF has a missing session after its first bar.

- Early iShares ("WEBS") funds traded thinly. From 1996 to 2001, 5–50% of days had an unchanged close; EWO and EWK were the worst.
- By the 2000 start every fund already had about 45 month-end closes.

## Deviations from the source

- **ETFs instead of futures.** AMP use country equity index futures and report excess returns. The ETFs are funded (fully invested), so the returns here are total returns, not excess returns over cash.
- **USD-unhedged.** AMP's futures are effectively local-currency. The iShares country funds are unhedged in USD, so currency moves enter both the ranking and the P&L.
- **Long-only top tercile.** This replaces the long-short rank-weighted factor and P3−P1. The strategy keeps the market's equity beta (about 0.9 vs SPY) and all equity drawdowns.
- **Smaller, time-varying cross-section.** The universe has 15 markets through 2013-01, then 17. Portugal is absent throughout. Denmark and Norway are added when their ETFs have enough history.
- **Thin early history.** The first two years of iShares history (1996–1998) were thinly traded, with stale closes, high fees and tracking error. The 2000 start means signals already use post-1998 data, but 2000–2002 closes are still noisier than a futures series.
- **Timing and costs.** Fills are at the next session's open instead of a same-day close. The run charges 5 bp slippage plus SEC/FINRA fees and uses whole shares.
- **Round-half-up.** The tercile count uses round-half-up. This only matters for `top_fraction = 0.5` with 15 markets (7.5 → 8).
- **Absolute filter.** The filter is our addition from the research dossier. It is not in AMP.

## Known critiques and post-publication evidence

- **Momentum crashes (Daniel & Moskowitz 2016).** Momentum returns are negatively skewed. Crashes cluster in "panic states": after market declines, when volatility is high, and at the rebound. The long-only top bucket loses less than long-short in a short squeeze. However, it still lags in V-shaped recoveries: in April 2009 it held the "least bad" markets with MOM around −35% to −44%.
- **Post-publication decay (McLean & Pontiff 2016).** Across 97 anomalies, returns fall 26% out-of-sample and 58% post-publication.
- **Weak country momentum since 2000.** The paper's 8.7% P3−P1 spread is an average over 1978–2011. In this ETF universe the spread is essentially zero after 2000, as the next section shows.
- **Small cross-section and timing luck.** With about 15–17 markets and 5–6 holdings, results depend on a few names and on the rebalance day. Terciles rather than deciles are the right sort for a universe this small.

## Results

Base run: `trader backtest configs/strategies/country_momentum.yaml --suite --offline --workers 2`, from 2000-01-03 to 2026-09-25 (26.7 years). Source: `results/country_momentum/summary.json`.

### Headline

| Metric | Value |
|---|---|
| CAGR | 6.21% (SPY 8.31%) |
| Volatility | 20.52% |
| Sharpe | 0.30 |
| Sortino | 0.42 |
| Max drawdown | −62.80% |
| Calmar | 0.10 |
| Turnover | 2.28× equity per year (about 77 trades per year) |
| Cost drag | 0.23% per year |
| Beta / correlation vs SPY | 0.89 / 0.83 |
| Probabilistic Sharpe Ratio vs 0 | 0.94 |
| Deflated Sharpe Ratio (14 trials) | 0.88 |
| Bootstrap Sharpe 90% CI | 0.02 – 0.61 |
| Bootstrap P(Sharpe > SPY) | 0.15 |

### In-sample vs out-of-sample (`metrics.oos`, split 2009-03-20)

| Period | CAGR | Vol | Sharpe | Max DD | SPY CAGR |
|---|---|---|---|---|---|
| In-sample, 2000-01-03 → 2009-03-20 | −0.16% | 22.8% | −0.02 | −62.8% | −5.19% |
| Out-of-sample, 2009-03-23 → 2026-09-25 | 9.72% | 19.2% | 0.51 | −34.7% | 16.16% |

The same run split at AMP's sample end instead:

| Period | CAGR | Vol | Sharpe | Max DD | SPY CAGR |
|---|---|---|---|---|---|
| 2000-01-03 → 2011-07-31 (overlaps AMP's sample) | 4.64% | 23.3% | 0.21 | −62.8% | 0.66% |
| 2011-08-01 → 2026-09-25 (after AMP's sample) | 7.43% | 18.2% | 0.40 | −33.4% | 14.53% |

### Crisis returns

| Episode | Return |
|---|---|
| Dot-com bust (2000-03 → 2002-10) | −48.1% |
| GFC (2007-10 → 2009-03) | −60.5% |
| Euro/US downgrade (2011-04 → 2011-10) | −34.6% |
| Q4 2018 selloff | −17.3% |
| COVID crash (2020-02 → 2020-03) | −32.9% |
| 2022 inflation bear | −30.8% |
| 2025 tariff shock (2025-02 → 2025-04) | −12.0% |

### Robustness suite (`variants.json`)

| Variant | CAGR | Vol | Sharpe | Sortino | Max DD | Calmar | Turnover | Cost drag |
|---|---|---|---|---|---|---|---|---|
| **base** | 6.21% | 20.52% | 0.30 | 0.42 | −62.80% | 0.10 | 2.28× | 0.23% |
| costs 0× | 6.46% | 20.52% | 0.31 | 0.43 | −62.73% | 0.10 | 2.28× | 0.00% |
| costs 2× | 5.96% | 20.52% | 0.29 | 0.40 | −62.87% | 0.09 | 2.28× | 0.47% |
| costs 4× | 5.47% | 20.52% | 0.27 | 0.37 | −63.02% | 0.09 | 2.28× | 0.94% |
| fill next close | 6.28% | 20.51% | 0.31 | 0.42 | −62.45% | 0.10 | 2.28× | 0.23% |
| delay 2 sessions | 6.24% | 20.51% | 0.30 | 0.42 | −62.45% | 0.10 | 2.27× | 0.23% |
| decide 5 sessions early | 6.65% | 20.45% | 0.32 | 0.45 | −63.76% | 0.10 | 2.28× | 0.23% |
| decide 10 sessions early | 6.77% | 20.46% | 0.33 | 0.45 | −61.64% | 0.11 | 2.27× | 0.23% |
| `skip_months=0` (MOM1–12) | 6.56% | 20.19% | 0.32 | 0.44 | −60.89% | 0.11 | 2.26× | 0.23% |
| `lookback_months=6` | 4.96% | 20.38% | 0.25 | 0.34 | −67.66% | 0.07 | 3.36× | 0.34% |
| `top_fraction=0.2` | 6.39% | 20.83% | 0.31 | 0.43 | −63.79% | 0.10 | 2.81× | 0.28% |
| `top_fraction=0.5` | 6.34% | 20.36% | 0.31 | 0.43 | −61.80% | 0.10 | 1.81× | 0.18% |
| `abs_filter=True` | 5.75% | 16.52% | 0.30 | 0.42 | −38.51% | 0.15 | 2.66× | 0.27% |
| ETF era (from 2013-05-02) | 8.11% | 17.12% | 0.44 | 0.60 | −33.42% | 0.24 | 2.19× | 0.23% |

The "ETF era" variant starts in 2013 because the harness waits for the latest-listed universe member (EDEN, 2012-01-26) plus warm-up. The base run holds no proxy data, so this variant is simply a post-2013 subperiod.

### Comparison with the source

AMP Table I (country index futures, 1978–2011, excess returns) reports:

- P3: 11.0% per year, Sharpe 0.65
- P1: 2.3% per year
- P3−P1: 8.7% per year, Sharpe 0.73

The ETF implementation shows no comparable momentum premium. The figures below are gross, monthly and cost-free. They were computed separately from the backtest, on the same cached data and universe, using the month-end signal and the next month's return:

| Period | P3 CAGR | P1 CAGR | P3−P1 mean | t-stat |
|---|---|---|---|---|
| 2000-02 → 2011-07 | 5.4% | 5.2% | −0.3% per year | −0.1 |
| 2011-08 → 2026-08 | 8.0% | 8.5% | −0.7% per year | −0.3 |

The equal-weighted basket of all available countries earned 7.0% CAGR over 2000-02 → 2026-08, against 6.4% for the strategy. Both had 18% monthly vol.

Why the gap to AMP is so large:

1. **Sample period.** AMP's 1978–2011 average contains the strong 1980s–1990s country momentum. Over the 2000–2011 overlap, this ETF version's top and bottom terciles earned the same.
2. **Unhedged USD returns.** Currency moves enter the ranking. That is a different, noisier signal than local-currency futures returns.
3. **Smaller universe.** The universe has 15–17 markets instead of 18, and 5–6 holdings.
4. **Funded, long-only returns.** The strategy's 20% volatility and −63% drawdown are equity-market figures. They match the spec's expectation of 18–22% vol and −50% to −60% in 2008. AMP's long-short P3−P1 Sharpe does not apply to a long-only portfolio.

The better out-of-sample Sharpe (0.51 vs −0.02) comes from where the split falls, at the 2009 bottom, not from momentum. SPY returned 16.2% per year over the same window, and the strategy trailed the equal-weight country basket both before and after publication.

### Sanity checks performed

- **Selections.** Hand-computed MOM2–12 top-tercile selections matched the engine's targets on six dates: 2003-06, 2008-06, 2009-04, 2015-12, 2020-03 and 2026-08.
- **Holdings count.** The strategy held 5 names at 158 decisions and 6 names at 163. Targets always sum to 1.
- **BIL.** BIL is never held in the base run.
- **New listings.** EDEN is first targeted on 2013-02-28, which is its 14th month-end, and first held on 2013-03-01. ENOR is first targeted on 2016-10-31. Neither is ever held before its data exists.
- **Trading activity.** The strategy makes 62–89 trades per year: monthly drift rebalances plus about one swap per month.
- **Daily moves.** No daily portfolio move exceeds 15%. The largest are +14.6% on 2008-10-13 and −11% in March 2020, both real market events.
