# Volatility-managed SPY (Moreira & Muir 2017), unlevered

Registry name `vol_managed_spy`, class `VolatilityManagedSPY` in `src/trader/strategies/vol_managed_spy.py`. Config: `configs/strategies/vol_managed_spy.yaml`. Results: `results/vol_managed_spy/`.

## Summary

At each month-end the strategy holds SPY at weight `w = min(1, c_t / RV_t)` and puts the rest in T-bills (BIL). `RV_t` is the realized variance of the month that just ended, computed from daily SPY excess returns. `c_t` is a scale constant, re-estimated every month from all earlier months, chosen so that the *uncapped* rule would have had the same volatility as buy-and-hold. After calm months the strategy is fully invested. After turbulent months it cuts equity exposure roughly in proportion to 1/variance.

This is the "No Leverage" row of Moreira & Muir's Tables 4–5, made real-time. Treat it as a **risk-reduction overlay, not an alpha source**. Over 2000–2026 it roughly halves SPY's volatility and drawdowns for about 1.5 points of CAGR. After publication its Sharpe ratio is the same as SPY's.

## Sources

- Moreira, A. & Muir, T. (2017). "Volatility-Managed Portfolios." *Journal of Finance* 72(4), 1611–1644. DOI [10.1111/jofi.12513](https://doi.org/10.1111/jofi.12513). NBER Working Paper 22208 (April 2016): <https://www.nber.org/papers/w22208>. SSRN 2659431: <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2659431>.
- **Publication date used for the out-of-sample split: 2015-09-12** (the SSRN 2659431 "date written"). Everything after 2015-09-12 is out-of-sample.
- Cederburg, S., O'Doherty, M. S., Wang, F. & Yan, X. (2020). "On the performance of volatility-managed portfolios." *Journal of Financial Economics* 138(1), 95–117. DOI [10.1016/j.jfineco.2020.04.015](https://doi.org/10.1016/j.jfineco.2020.04.015). Author PDF: <https://www.lehigh.edu/~xuy219/research/COWY.pdf>.
- Bongaerts, D., Kang, X. & van Dijk, M. (2020). "Conditional Volatility Targeting." *Financial Analysts Journal* 76(4), 54–71. DOI [10.1080/0015198X.2020.1790853](https://doi.org/10.1080/0015198X.2020.1790853). PDF: <https://repub.eur.nl/pub/130215/Bongaerts-Kang-van-Dijk-Conditional-volatility-targeting-2020-FAJ.pdf>.
- Barroso, P. & Detzel, A. (2021). "Do limits to arbitrage explain the benefits of volatility-managed portfolios?" *Journal of Financial Economics* 140(3), 744–767. SSRN: <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3088828>.
- Liu, F., Tang, X. & Zhou, G. (2019). "Volatility-Managed Portfolio: Does It Really Work?" *Journal of Portfolio Management* 46(1), 38–51. <https://jpm.pm-research.com/content/46/1/38>.
- Harvey, C., Hoyle, E., Korgaonkar, R., Rattray, S., Sargaison, M. & Van Hemert, O. (2018). "The Impact of Volatility Targeting." *Journal of Portfolio Management* 45(1), 14–33. <https://people.duke.edu/~charvey/Research/Published_Papers/P135_The_impact_of.pdf>.
- DeMiguel, V., Martín-Utrera, A. & Uppal, R. (2024). "A Multifactor Perspective on Volatility-Managed Portfolios." *Journal of Finance* 79(6), 3859–3891. DOI [10.1111/jofi.13395](https://doi.org/10.1111/jofi.13395).

## Rules as implemented

The decision is made at the close of the last session of each month (`MonthEnd()`). Orders fill at the next session's open.

1. **Daily excess returns.** `f_d = r_SPY,d − rf_d`, where `r_SPY` is the total return from adjusted closes and `rf_d` is the harness's daily T-bill accrual (`ctx.data.rf`, from ^IRX lagged one session). A missing close after SPY's first bar is forward-filled.
2. **Realized variance of month t.** `RV_t = Σ_{d in month t} (f_d − mean_t(f))²`. This is the sum over the month's actual trading days of squared deviations from that month's mean. It is not annualized and not averaged. A month is used only if every one of its sessions has a return, so the month of SPY's first bar is dropped.
3. **Monthly excess return.** `F_m = Π(1 + r_d) − Π(1 + rf_d)` over month m.
4. **Calibration (`calibration="expanding"`, default).** Build pairs `(RV_m, F_{m+1})` in which **both months are strictly before month t**, and compute `c_t = std(F_{m+1}) / std(F_{m+1} / RV_m)` (ddof 1). This is the value that gives the uncapped managed series `c·F/RV` the same standard deviation as buy-and-hold over the calibration window. It is Moreira & Muir's choice of c, estimated on an expanding window instead of the full sample.
5. **Warm-up.** At least `min_calibration_months = 120` pairs are required. Until then the strategy holds 100% SPY. Because VFINX starts on 1980-01-02 (first complete month Feb-1980), the rule becomes active at the end of March 1990. The backtest starts in 2000, so it is always calibrated. By 2000 it has about 240 pairs, and by 2026 about 560.
6. **Weight.** `w = min(cap, c_t / RV_t)` with `cap = 1.0`. SPY gets `w` and BIL gets `1 − w`. If SPY has no price yet, everything goes to BIL. If BIL has no price, the remainder stays in cash.
7. **Alternatives (robustness grid).**
   - `calibration="mean_rv"`: `c_t` is the mean of `RV_m` over all months before t, so `w = 1` when the month's variance equals its long-run average (Bongaerts et al. style).
   - `scaling="vol"`: replace `RV` by `sqrt(RV)` everywhere, both in the weight and in the calibration.
8. **Decisions off a month-end.** This covers the first session of the backtest (2000-01-03) and the suite's `shift_5`/`shift_10` timing-luck variants. On those dates the current calendar month is incomplete, so `RV_t` uses the trailing 21 sessions instead. The calibration still uses only calendar months before the current one.

Parameters (defaults are the published values): `cap=1.0`, `calibration="expanding"`, `scaling="variance"`, `min_calibration_months=120`. `param_grid = {"calibration": ["mean_rv"], "scaling": ["vol"]}`.

## ETF mapping and proxies

| Role | Paper | Here | Pre-inception proxy |
|---|---|---|---|
| Market | CRSP value-weighted market (Ken French Mkt), daily | SPY | VFINX (Vanguard 500 Index) before 1993-01-29; monthly corr 0.998, TE 0.8% |
| Risk-free / cash | 1-month T-bill | BIL | `@tbill` (^IRX accrual minus 0.10% fee) before 2007-05-30 |
| rf in excess returns | 1-month T-bill | ^IRX 13-week yield, lagged one session | – |

The backtest window is 2000-01-03 → 2026-09-25. In it, SPY is always the real ETF and BIL is synthetic until 2007-05-30. The proxy share of held weight is 9.2%. Calibration uses VFINX data from 1980–1993.

## Deviations from the source

- **Real-time c instead of full-sample c.** Moreira & Muir choose c over the whole 1926–2015 sample, which is look-ahead. Here c is re-estimated each month from strictly earlier months, as in Cederburg et al.'s real-time test. It is stable: 0.00106–0.00131 across 1990–2026 (for comparison, a typical month's RV is about 0.0014). The latest complete pair `(RV_{t−1}, F_t)` is excluded even though it is known at the decision close. This is a conservative one-month lag with negligible effect.
- **Unlevered.** Only the cap-1.0 "No Leverage" version is implemented. The paper's headline uncapped version reaches weights of 6.4x at P99 and is not implementable in this long-only, ≤1x harness.
- **Execution.** The paper earns month t+1's return at the month-t close. Here orders fill at the next session's open, with whole shares, 5 bp slippage and SEC/FINRA fees. `exec_next_close` and `delay_2` are in the suite.
- **Instrument.** The paper uses the CRSP market and 1-month bills. Here SPY/VFINX and ^IRX/BIL stand in for them. The monthly mean in `RV` is the actual `sum/N`, not the paper's fixed `sum/22`.
- **Monthly schedule only.** The initial rebalance and the timing-luck variants use a trailing 21-session window (see rule 8).
- **Data quality.** Yahoo's SPY closes before about 2008 are noisier than the index. Daily correlation with VFINX's 4pm NAV is 0.93–0.98, against 0.999 after 2009. Median monthly RV is 12–28% higher in 1993–1998. There are a few outright bad prints, such as 2000-01-06/07 (SPY −1.6% then +5.8%, while the index moved +0.1% then +2.7%) and 2000-12-08/11. One effect is that the Jan-2000 RV is 75% too high, giving a Feb-2000 weight of 0.13 instead of 0.21. A diagnostic re-run with VFINX-derived prices through 2008 changed the headline numbers only slightly: Sharpe 0.500 → 0.495, CAGR 6.81% → 6.68%, MDD −23.5% → −25.4%. The strategy therefore keeps SPY as the spec requires.

## Known critiques and post-publication evidence

- **The in-sample c problem.** Both Moreira & Muir's c and the ex-post scale in Harvey et al. (2018) are chosen with hindsight. Liu, Tang & Zhou (2019) argue that the typical application "suffers from look-ahead bias" and that corrected, levered versions have 68–93% drawdowns. The expanding-window c used here removes the look-ahead. The 1.0 cap removes the leverage that causes those drawdowns.
- **Weak statistical evidence.** Cederburg et al. (2020) test 103 strategies. For the market over 1926–2016, the Sharpe ratio rises from 0.42 to 0.51 (p = 0.30). Their real-time out-of-sample version earns 0.46 against 0.42 for the plain market. The gain is concentrated around the Great Depression, and volatility-managed portfolios "do not systematically outperform".
- **Costs.** Barroso & Detzel (2021) find that the managed *market* survives transaction costs, unlike other managed factors, but that its benefits show up only when sentiment is high. Moreira & Muir give a break-even cost of 110 bp for the capped version.
- **Crash lag.** Monthly RV reacts only after a turbulent month has ended. A crash that starts in a calm month is met fully invested, as in Oct-1987 and Feb-2020. The rebound after a crash is then met under-invested (2020 below).
- **Real-time variants.** Bongaerts et al. (2020) find conventional vol targeting inconsistent across 10 markets: it raised max drawdown in 4 and expected shortfall in 8. Their conditional version scales only in extreme-vol quintiles. Harvey et al. (2018) find a Sharpe improvement for equities (0.40 → about 0.50) and none for bonds, FX or commodities.
- **Where it still works.** DeMiguel et al. (2024) find that a conditional *multifactor* volatility-managed portfolio outperforms out-of-sample. That result is factor-level and cannot be implemented with ETFs.

## Results

> **Note:** the numbers in this section come from the strategy's own branch run, which used a flat 5 bps slippage on every fill and an earlier harness version. The final numbers, from the tiered 2/4/6 bps cost model with the harness fixes applied, are in [`reports/comparison.md`](../../reports/comparison.md) and `results/<strategy>/summary.json` on the comparison branch. Conclusions are unchanged unless noted there.

Backtest: 2000-01-03 → 2026-09-25 (26.7 years), next-open fills, 5 bp slippage, whole shares. Benchmark: buy-and-hold SPY through the same engine.

### Headline (`summary.json`)

| Metric | vol_managed_spy | SPY buy & hold |
|---|---|---|
| CAGR | 6.81% | 8.31% |
| Volatility | 10.42% | 19.25% |
| Sharpe | 0.50 | 0.41 |
| Sortino | 0.69 | 0.58 |
| Max drawdown | −23.5% | −55.2% |
| Calmar | 0.29 | 0.15 |
| Turnover (one-way, per year) | 2.19x | – |
| Cost drag (per year) | 0.24% | – |
| Trades per year | 17.8 | – |
| Beta / alpha to SPY | 0.42 / +1.87% | – |
| Average SPY weight | 0.70 (median month-end target 0.79; at the 1.0 cap in 42% of months) | 1.00 |
| Mean \|Δw\| per month | 0.18 | – |

Bootstrap 90% CI of the Sharpe ratio is 0.23–0.78. For Sharpe minus SPY's the median is +0.08, the CI is −0.08 to +0.28, and P(better) is 0.79. PSR vs 0 is 0.995 and the deflated Sharpe (11 trials) is 0.977.

### In-sample vs out-of-sample (split 2015-09-12)

| Period | CAGR | Vol | Sharpe | Max DD | SPY CAGR | SPY Sharpe | SPY Max DD |
|---|---|---|---|---|---|---|---|
| In-sample 2000-01 → 2015-09 | 4.70% | 10.44% | 0.33 | −23.5% | 3.76% | 0.20 | −55.2% |
| Out-of-sample 2015-09 → 2026-09 | 9.88% | 10.39% | **0.75** | −15.9% | 15.12% | **0.76** | −33.7% |

### Crisis returns

| Window | vol_managed_spy | SPY |
|---|---|---|
| Dot-com bust (2000-03 → 2002-10) | −19.2% | −47.2% |
| GFC (2007-10 → 2009-03) | −17.1% | −54.8% |
| Euro/US downgrade (2011-04 → 2011-10) | −8.9% | −18.4% |
| Q4 2018 selloff | −11.3% | −18.7% |
| COVID crash (2020-02 → 2020-03) | −15.5% | −33.4% |
| 2022 inflation bear | −8.0% | −24.1% |
| 2025 tariff shock (2025-02 → 2025-04) | −10.6% | −18.6% |

Weights behave as the spec expects:
- **After the Oct-2008 crash:** SPY weight 0.07 set at end-Sep-2008, then 0.02 and 0.03 for Nov and Dec.
- **COVID:** 0.90 at end-Jan-2020, so February started nearly fully invested. The weight was 0.24 at end-Feb and 0.02 at end-Mar.
- **The cost:** in 2020 the strategy stayed under-invested through the V-shaped rebound (weight 0.08 at end-Apr, 0.28 at end-May, 0.16 at end-Jun). It returned −2.6% for the year against SPY's +18.3%.

### Robustness suite (`variants.json`)

| Variant | Start | CAGR | Vol | Sharpe | Sortino | Max DD | Calmar | Turnover | Cost drag |
|---|---|---|---|---|---|---|---|---|---|
| **base** | 2000-01-03 | 6.81% | 10.42% | 0.50 | 0.69 | −23.5% | 0.29 | 2.19 | 0.24% |
| costs 0x | 2000-01-03 | 7.05% | 10.42% | 0.52 | 0.72 | −23.1% | 0.31 | 2.19 | 0.00% |
| costs 2x | 2000-01-03 | 6.57% | 10.42% | 0.48 | 0.66 | −24.0% | 0.27 | 2.19 | 0.47% |
| costs 4x | 2000-01-03 | 6.10% | 10.42% | 0.44 | 0.60 | −24.9% | 0.24 | 2.18 | 0.94% |
| exec next close | 2000-01-03 | 6.98% | 10.43% | 0.52 | 0.71 | −24.9% | 0.28 | 2.18 | 0.24% |
| delay 2 | 2000-01-03 | 7.07% | 10.45% | 0.52 | 0.72 | −23.7% | 0.30 | 2.18 | 0.24% |
| shift 5 (timing luck) | 2000-01-03 | 6.05% | 10.86% | 0.42 | 0.57 | −28.2% | 0.21 | 2.15 | 0.24% |
| shift 10 (timing luck) | 2000-01-03 | 5.47% | 11.03% | 0.36 | 0.49 | −33.4% | 0.16 | 2.22 | 0.24% |
| calibration = mean_rv | 2000-01-03 | 8.17% | 13.88% | 0.50 | 0.69 | −39.4% | 0.21 | 1.35 | 0.11% |
| scaling = vol | 2000-01-03 | 8.02% | 13.74% | 0.49 | 0.68 | −36.7% | 0.22 | 1.19 | 0.11% |
| etf_era | 2017-12-06 | 9.17% | 10.69% | 0.63 | 0.85 | −15.9% | 0.58 | 2.70 | 0.27% |

What the suite shows:
- **Costs and execution lag are harmless.** At 4x costs (about 20 bp per side) the Sharpe is still 0.44, above SPY's 0.41.
- **Timing luck is not harmless.**
  - Deciding 5 or 10 sessions before month-end lowers the Sharpe from 0.50 to 0.42 and 0.36, and deepens the drawdown from −23.5% to −28% and −33%.
  - Most of the gap comes from COVID (−24.6% and −22.6% vs −15.5%). A Feb-13 decision saw a calm window and stayed at 0.76 SPY into the crash, while the Feb-28 decision had already seen the first week of it.
  - The dot-com bust contributes too (−26% and −31% vs −19%).
  - Part of the base run's drawdown protection is therefore luck of the calendar alignment.
- **The two grid alternatives sit at a different point on the same line.** `mean_rv` and `vol` de-risk less (higher exposure), so they have higher CAGR, vol and drawdown at essentially the same Sharpe.
- **The etf_era variant starts only in 2017-12.** The harness starts it 1.5 × `warmup()` calendar days after BIL's inception, and `warmup()` covers the 120-month calibration. Its signals still use the proxy history.

### Comparison with the source

- **Sharpe.**
  - Moreira & Muir report 0.52 for the No-Leverage market over 1926–2015. That equals their uncapped managed market (0.52). Buy-and-hold is about 0.42 over the same period (Cederburg et al., Table 1).
  - Here the Sharpe is 0.50 against SPY's 0.41 over 2000–2026, a +0.09 gain. That is the same size as Cederburg et al.'s full-sample gain (0.42 → 0.51) and larger than their real-time one (0.42 → 0.46).
  - A paper-style, in-sample, same-close monthly calculation on this Yahoo data gives Sharpe 0.42 for the market, 0.54 uncapped managed and 0.45 capped (1980–2015). For 1990–2026 it gives 0.61, 0.64 and 0.72.
- **Return and exposure.**
  - The paper's capped E[R] is 5.61% excess. Here the arithmetic excess return is about 5.2% (Sharpe × vol), against about 7.9% for SPY.
  - The average SPY weight of 0.70 sits at the bottom of the expected 70–85% band.
  - Mean \|Δw\| is 0.18 per month against the paper's 0.16.
- **Out-of-sample: no Sharpe improvement.** After 2015-09 the Sharpe is 0.75 against SPY's 0.76. The whole full-sample Sharpe gain comes from 2000–2015 (0.33 vs 0.20), which contains two deep, slow bear markets where monthly RV had time to react. After publication the strategy still halves volatility and drawdown (−15.9% vs −33.7%), but gives up about 5 points of CAGR a year in a strong bull market with sharp V-shaped recoveries (2020, 2025).

### Assessment

A plausible, faithful and cheap-to-run risk-reduction overlay. It cuts SPY's volatility and max drawdown roughly in half at a Sharpe ratio similar to or slightly better than SPY's. There is no evidence of alpha: the Sharpe gain is not significant, it disappears out-of-sample, and it is sensitive to which day of the month the rebalance happens. Consider it a live candidate only as a lower-risk equity sleeve, not as a return enhancer.
