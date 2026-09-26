# Sector momentum rotation (Moskowitz & Grinblatt 1999)

Strategy `sector_momentum`, module `src/trader/strategies/sector_momentum.py`, config `configs/strategies/sector_momentum.yaml`.

## Summary

At each month-end, rank the Select Sector SPDR ETFs by their trailing 6-month total return. Hold the top 3 equal-weighted for one month, then re-rank. This is the long leg of Moskowitz & Grinblatt's (1999) industry momentum strategy IM(6,6), applied to US sector ETFs. The paper found that the long leg earns most of the strategy's profit. Faber's (2010) trend hedge is available as an option and is off by default: when SPY's month-end close is at or below its 10-month SMA, hold 100% T-bills (BIL).

Over 2000-01 to 2026-09, the strategy roughly matched SPY (7.99% vs 8.31% CAGR) with a similar drawdown (−51%). The industry momentum premium did not show up in the SPDR era. The gross spread between the top-3 and bottom-3 sectors was 0.02% a month (t = 0.07), against 0.43% a month in the paper.

## Sources

- Moskowitz, T.J., Grinblatt, M. (1999). "Do Industries Explain Momentum?" *Journal of Finance* 54(4), 1249–1290. DOI [10.1111/0022-1082.00146](https://doi.org/10.1111/0022-1082.00146). PDF: http://www-stat.wharton.upenn.edu/~steele/Courses/956/Resource/Momentum/MoskowitzGrinblatt99.pdf
- Jegadeesh, N., Titman, S. (1993). "Returns to Buying Winners and Selling Losers: Implications for Stock Market Efficiency." *Journal of Finance* 48(1), 65–91. DOI [10.1111/j.1540-6261.1993.tb04702.x](https://doi.org/10.1111/j.1540-6261.1993.tb04702.x)
- Faber, M. (2010). "Relative Strength Strategies for Investing." SSRN 1585517, https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1585517. This is the source of the optional trend hedge.

**Out-of-sample split:** `publication_date = 1999-08-01`, the issue date of the *Journal of Finance* article. MG's sample ends in July 1995, and the Select Sector SPDRs launched on 1998-12-22. The backtest starts on 2000-01-03, so **the entire backtest is out-of-sample**. There is no in-sample period to compare against.

## Rules as implemented

Schedule: last session of each month (`MonthEnd()`). Decisions are made at that close and filled at the next session's open.

1. Compute month-end closes of total-return-adjusted prices. On the schedule, the last row is the current month-end `t`.
2. A sector is **eligible** if:
   - it has a price today;
   - it has at least `lookback_months + skip_months + 1` non-missing month-end closes (7 by default).
3. Score each eligible sector by its total return from month-end `t − skip − lookback` to month-end `t − skip`. The default is `t−6 → t`, with no skip month.
4. Sort by score, highest first. Ties are broken alphabetically so the result is deterministic.
5. Hold the top `top_n` (default 3) at `1/top_n` each.
   - If fewer than `top_n` sectors are eligible, each unfilled slot goes to BIL.
   - This never happens after mid-1999, because all nine original SPDRs are eligible.
6. Optional trend filter (`trend_filter=True`): if SPY's month-end close is at or below the mean of its last 10 month-end closes (current month included), hold `{BIL: 1.0}`.
   - If SPY has fewer than 10 month-end closes, the filter is not applied.
   - SPY is a signal only and is never held.
7. Holdings that are no longer in the top `top_n` are sold at the next open. Holdings that stay are rebalanced back to `1/top_n`.

| Param | Default (published) | Grid |
|---|---|---|
| `lookback_months` | 6 (MG IM(6,·)) | 3, 9, 12 |
| `skip_months` | 0 (MG: industry momentum is strongest at 1 month) | 1 |
| `top_n` | 3 (MG: top 3 of 20 industries) | 2, 4 |
| `trend_filter` | False | True |

## ETF mapping and proxies

| Role | Symbols | First data |
|---|---|---|
| Sectors (9 originals) | XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY | 1998-12-22 (eligible from 1999-06-30) |
| Real estate | XLRE | 2015-10-08 (eligible from 2016-04-29) |
| Communication services | XLC | 2018-06-19 (eligible from 2018-12-31) |
| Cash (trend filter / unfilled slots) | BIL | 2007-05-30; synthetic T-bill series (`@tbill`, from ^IRX) before that |
| Trend signal (never held) | SPY | 1993; VFINX proxy before then (irrelevant to a 2000 start) |

- No sector proxies are used. XLRE and XLC join the ranking only once they have 7 month-end closes. IYR/VNQ or VOX/IYZ are not substituted, because an investor could not have held a Select Sector SPDR real-estate or communications fund earlier.
- **Proxy exposure in the base run is 0%** (`proxy_share = 0.0`): BIL is never held when the trend filter is off.
- With the trend filter on, BIL holdings before 2007-05-30 use the synthetic T-bill series.
- XLRE was first held in 2016-06 and XLC in 2020-03. The first holding of each happens after it becomes eligible (checked against the weights file).

## Deviations from the source

- **Long-only, top leg only.** MG's IM(6,6) is long the top 3 and short the bottom 3 industries. This is the long leg only, fully invested and unlevered. MG report that most of the profit is on the long side:
  - top 3 minus middle: 0.36% a month;
  - middle minus bottom 3: 0.07% a month.
- **Monthly re-ranking (H = 1) instead of 6 overlapping cohorts.** MG's headline strategy holds each monthly cohort for 6 months, and 6 cohorts are live at once. Re-ranking the whole portfolio each month roughly doubles turnover. It is also more exposed to the particular rebalance date (see the `shift_*` variants).
- **Sector ETFs instead of 20 two-digit-SIC industry portfolios.**
  - The universe is 9–11 GICS sectors, not 20 SIC industries.
  - Top 3 of 9 is roughly the top tercile, whereas MG's top 3 of 20 is the top 15%.
  - The ETFs are cap-weighted. They are capped under the Select Sector index rules, so a single mega-cap cannot dominate.
- **Time-varying universe.** There are 9 sectors from 1999, 10 from 2016-04 and 11 from 2018-12.
- **Execution.**
  - Decisions use the month-end close, and fills happen at the next session's open with 5 bps slippage plus SEC/FINRA fees. MG's returns are close-to-close with no costs.
  - Orders are for whole shares.
  - Idle cash from share rounding earns 0%.
- **First decision.** The backtest trades on its first session, 2000-01-03, which is not a month-end. That decision ranks on the 2000-01-03 close against the 1999-07-30 month-end. All later decisions are made at month-ends.
- **Trend filter** (optional). It comes from Faber (2010), not from MG. It uses SPY rather than the S&P 500 index, and BIL rather than T-bill returns.

## Known critiques and post-publication evidence

- **GICS reclassifications change what the ETFs hold.**
  - In Sep 2016, real estate left Financials: XLF lost its REITs and XLRE became a standalone sector.
  - In Sep 2018, the Communication Services sector was created. It took Alphabet and Meta from XLK and media/internet names such as Netflix and Disney from XLY.
  - Lookback windows that straddle these dates mix two compositions. This implementation accepts that, because it is what an investor would actually have held.
- **Small cross-section.**
  - Top 3 of 9–11 is concentrated and noisy.
  - The strategy held 11 distinct sectors over the period. On average, 0.88 of the 3 names changed each month.
  - Over 320 re-rankings, the count of names replaced was: none in 96 months, 1 in 172 months, 2 in 47 months, and all 3 in 5 months.
- **Momentum crashes in V-shaped rebounds** (Daniel, K., Moskowitz, T.J. (2016), "Momentum crashes," *Journal of Financial Economics* 122(2), 221–247, https://doi.org/10.1016/j.jfineco.2015.12.002). This is visible in the data:
  - From Mar to Dec 2009, the gross top-3 basket gained +38.9%.
  - Over the same months, the bottom-3 basket gained +84.8%, the equal-weight sectors +56.8% and SPY +54.2%.
  - In the backtest, the strategy returned +15.4% in 2009 against +26.4% for SPY.
- **Turnover.** The spec expected about 200% a year, which is MG's figure for (6,6) with overlapping cohorts. The monthly re-ranking here turns over **359% a year**, measured one-sided (the harness's `turnover_annual`). That is about 46 trades a year and a cost drag of 0.38% a year at 5 bps.
- **ETF evidence.** Andreu, L., Swinkels, L., Tjong-A-Tjoe, L. (2013), "Can exchange traded funds be used to exploit industry and country momentum?", *Financial Markets and Portfolio Management* 27(2), 127–148, https://doi.org/10.1007/s11408-013-0207-8. Using ETF prices, they report industry and country momentum earning about 5% a year in excess returns. Faber (2010) suggests 300–600 bp a year of outperformance on French–Fama sectors over 1926–2009. Neither result carries over to 2000–2026 in this backtest (see below).

## Results

Run: `trader backtest configs/strategies/sector_momentum.yaml --suite --offline --workers 2 --out results/sector_momentum`. Window 2000-01-03 → 2026-09-25 (26.7 years). Default costs (5 bps slippage plus SEC/TAF/CAT fees), next-open fills, whole shares. The benchmark is SPY buy-and-hold.

### Headline metrics (`results/sector_momentum/summary.json`)

| Metric | Strategy | SPY |
|---|---|---|
| CAGR | 7.99% | 8.31% |
| Volatility | 18.20% | |
| Sharpe | 0.41 | |
| Sortino | 0.57 | |
| Max drawdown | −51.33% | |
| Calmar | 0.16 | |
| Beta / correlation to SPY | 0.81 / 0.86 | |
| CAPM alpha (annual) | 1.00% | |
| Information ratio vs SPY | −0.05 | |
| Turnover (one-sided, per year) | 3.59× | |
| Trades per year | 46.4 | |
| Cost drag (per year) | 0.38% | |
| Bootstrap 90% CI, Sharpe | 0.17 – 0.70 | |
| P(Sharpe > SPY's), bootstrap | 0.52 | |

**In-sample vs out-of-sample** (`metrics.oos`, split 1999-08-01):

| | Sharpe | CAGR |
|---|---|---|
| In-sample (before 1999-08-01) | n/a: no data (the backtest starts 2000-01-03) | n/a |
| Out-of-sample (2000-01-03 → 2026-09-25) | 0.41 | 7.99% |

Subperiods (strategy vs SPY, computed from `daily.parquet`):

| Period | Strategy CAGR | SPY CAGR |
|---|---|---|
| 2000–2009 | 3.25% | −0.91% |
| 2010–2026-09 | 10.81% | 14.15% |

### Crisis returns

| Episode | Strategy |
|---|---|
| Dot-com bust (2000-03 → 2002-10) | −21.4% |
| GFC (2007-10 → 2009-03) | −50.5% |
| Euro/US downgrade (2011-04 → 2011-10) | −11.6% |
| Q4 2018 selloff | −15.6% |
| COVID crash (2020-02 → 2020-03) | −29.5% |
| 2022 inflation bear | −9.7% |
| 2025 tariff shock (2025-02 → 2025-04) | −20.7% |

### Robustness suite (`results/sector_momentum/variants.json`)

| Variant | CAGR | Vol | Sharpe | Max DD | Turnover |
|---|---|---|---|---|---|
| **base** | 7.99% | 18.20% | 0.41 | −51.3% | 3.59× |
| costs 0× | 8.39% | 18.20% | 0.43 | −51.0% | 3.59× |
| costs 2× | 7.60% | 18.20% | 0.39 | −51.6% | 3.59× |
| costs 4× | 6.81% | 18.20% | 0.35 | −52.2% | 3.59× |
| fill at next close | 7.83% | 18.20% | 0.40 | −51.0% | 3.59× |
| delay 2 sessions | 7.66% | 18.23% | 0.39 | −51.3% | 3.58× |
| decide 5 sessions early | 7.23% | 18.37% | 0.37 | −47.7% | 3.59× |
| decide 10 sessions early | 6.80% | 18.44% | 0.35 | −49.8% | 3.80× |
| lookback 3 | 8.11% | 18.29% | 0.41 | −48.2% | 4.77× |
| lookback 9 | 8.62% | 18.36% | 0.44 | −46.4% | 2.87× |
| lookback 12 | 8.83% | 18.43% | 0.45 | −45.5% | 2.84× |
| skip 1 month | 8.56% | 18.63% | 0.43 | −45.8% | 3.60× |
| top 2 | 7.65% | 19.53% | 0.38 | −49.1% | 4.21× |
| top 4 | 8.50% | 17.73% | 0.44 | −47.5% | 2.94× |
| trend filter (Faber) | 7.77% | 13.45% | 0.48 | −22.8% | 3.97× |
| etf_era (2019-02-15 → 2026-09) | 12.62% | 19.10% | 0.58 | −29.7% | 3.81× |

- The `etf_era` row is not a proxy test for this strategy. The base run holds no proxy data at all. The harness starts this variant at the latest real first date of any universe symbol (XLC, 2018-06), so the row is really a 2019-02 → 2026-09 subperiod. SPY returned 16.1% a year over the same window.
- Across the parameter grid, CAGR stays within 7.6%–8.8% and Sharpe within 0.38–0.45. The defaults are near the middle of that range, not at the top.
- The trend filter halves the drawdown (−22.8% vs −51.3%) and lifts Sharpe to 0.48, at a slightly lower CAGR.

### Comparison with the sources

These figures are computed from month-end closes, gross of costs, with monthly re-ranking, over 2000-01 → 2026-09 (scratch analysis, not part of `results/`):

| | This backtest (SPDRs, 2000–2026) | Source |
|---|---|---|
| Top 3 − bottom 3, per month | +0.02% (t = 0.07) | MG IM(6,6): +0.43% (1963–1995) |
| Top 3 − middle, per month | −0.04% | MG: +0.36% |
| Middle − bottom 3, per month | +0.06% | MG: +0.07% |
| Top 3 vs equal-weight sectors, per year | 8.46% vs 8.60% CAGR | Faber: +300–600 bp vs buy-and-hold; Andreu et al.: ~5% excess |

**Honest read.** Out of sample, sector momentum on the SPDRs has earned essentially no premium. The long-short spread is indistinguishable from zero, and the top-3 basket slightly trails an equal-weight basket of all sectors.

- 2000–2009 (+0.21% a month top − bottom): the strategy beat SPY by about 4 points a year. It rotated out of tech in 2000–2002 and into energy and materials in 2003–2007.
- 2010–2026 (−0.10% a month): mega-cap-heavy SPY beat an equal-weight rotation among sectors, and the 2009 junk rally hurt.

Possible explanations for the gap from the published figures:
- Sector ETFs are a much smaller and more aggregated cross-section than MG's 20 industries.
- Monthly re-ranking replaces MG's 6-month overlapping holding periods.
- The industry-momentum premium itself may have decayed after publication.

The small cost drag (0.38% a year) and the matching gross/net figures (8.46% gross close-to-close vs 7.99% net with next-open fills) show the gap is not an execution artifact. The sanity checks in the spec hold:
- CAGR is within 0.3 points of SPY.
- Max drawdown is −51%.
- Beta is 0.81, a little below the expected 0.9–1.0, because the ranking often rotates into defensive sectors (XLP, XLV, XLU) after selloffs.
