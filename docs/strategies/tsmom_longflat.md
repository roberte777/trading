# Time-series momentum, long/flat (`tsmom_longflat`)

## Summary

This is an unlevered, long-only ETF version of Moskowitz, Ooi & Pedersen's (2012) time-series momentum (TSMOM). The universe is 13 multi-asset ETFs.

- At each month-end, an asset is held if its 12-month total return beat T-bills (BIL) over the same 12 months. Otherwise its slot goes to BIL.
- Each asset's size is its inverse-volatility risk budget, where volatility is the MOP EWMA with a 60-day center of mass. The budget is normalized over **all** eligible assets, not just the ones held. So each asset keeps an equal ex-ante risk slot whether it is long or flat, and gross exposure is 1 by construction.
- A control run with the trend filter switched off (`trend_filter=False`) holds every eligible asset at its inverse-vol budget. It separates the trend signal from plain risk-budgeted diversification.

## Sources

- Moskowitz, T.J., Ooi, Y.H. & Pedersen, L.H. (2012). "Time series momentum." *Journal of Financial Economics* 104(2), 228–250. DOI [10.1016/j.jfineco.2011.11.003](https://doi.org/10.1016/j.jfineco.2011.11.003). PDF: https://w4.stern.nyu.edu/facdir/lpederse/papers/TimeSeriesMomentum.pdf
- Hurst, B., Ooi, Y.H. & Pedersen, L.H. (2017). "A Century of Evidence on Trend-Following Investing." *Journal of Portfolio Management* 44(1), 15–29. DOI [10.3905/jpm.2017.44.1.015](https://doi.org/10.3905/jpm.2017.44.1.015). AQR: https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing
- Critiques:
  - Kim, A.Y., Tse, Y. & Wald, J.K. (2016). "Time series momentum and volatility scaling." *Journal of Financial Markets* 30, 103–124. DOI [10.1016/j.finmar.2016.05.003](https://doi.org/10.1016/j.finmar.2016.05.003)
  - Huang, D., Li, J., Wang, L. & Zhou, G. (2020). "Time series momentum: Is it there?" *JFE* 135(3), 774–794. DOI [10.1016/j.jfineco.2019.08.004](https://doi.org/10.1016/j.jfineco.2019.08.004)
  - Hamill, C., Rattray, S. & Van Hemert, O. (2016). "Trend Following: Equity and Bond Crisis Alpha." SSRN [2831926](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2831926)
- **Publication date used for the out-of-sample split: 2011-12-11.** This is the date the JFE article appeared online. MOP's sample ends in 2009-12, so 2010–2011 is post-sample but still counted as in-sample here.

## Rules as implemented

`src/trader/strategies/tsmom_longflat.py`, class `TimeSeriesMomentum`. The schedule is `MonthEnd()`: decide at the close of the last session of the month and fill at the next session's open.

1. **Eligible set U_t.** A risky asset is eligible if all of the following hold:
   - it has a close today;
   - it has at least `lookback_months + 1` month-end closes (13 for the default; 13 for `blend`);
   - it has at least 120 daily returns;
   - it has a finite, positive volatility estimate.
2. **Excess momentum.** `excess_i = R_i(L) − R_BIL(L)`. Here `R(L)` is the total return from the month-end close L months ago to today's close, computed on total-return-adjusted closes with no skip month. If BIL has no L-month history (only possible with `use_proxies: false`), the harness's compounded T-bill rate (`ctx.data.rf`) is used instead.
3. **Signal.**
   - `signal="12"` (default): `s_i = 1` if `excess_i > 0`, else 0. The name refers to MOP's 12-month signal; the lookback is `lookback_months`.
   - `signal="blend"`: `s_i = (1[R1>rf1] + 1[R3>rf3] + 1[R12>rf12]) / 3`, using BIL returns over the matched horizon (Hurst, Ooi & Pedersen's 1/3/12 blend).
4. **Volatility.** `σ_i = indicators.ewma_vol(close, com=vol_com)`. This is the pandas `ewm(com=60).std()` of daily returns, annualized with √252 and computed through today's close. MOP annualize with 261; the choice cancels in step 5.
5. **Risk budget.** `b_i = (1/σ_i) / Σ_{j∈U_t} (1/σ_j)`.
6. **Weights.** `w_i = s_i · b_i`, and `w_BIL = 1 − Σ w_i`. BIL is never a risky asset.
7. **Control.** With `trend_filter=False`, `s_i ≡ 1`, so BIL gets 0 once any risky asset is eligible.

Implementation details:

- Indicators are computed on the last `max(23·(L+2), 20·vol_com, 240)` sessions, not the whole history. The EWMA weight on anything older is below 1e-8.
- Closes are forward-filled for at most 5 sessions. This bridges holiday gaps in the gold proxy GC=F, which has missing closes on 8 NYSE sessions in 2000–2004, including the month-ends 2002-11-29 and 2003-11-28. Without the bridge, GLD would be sold for a month and bought back for no economic reason. The bridge never back-fills: a symbol is ineligible until its first real (or proxy) close.
- `Params` defaults are the published values: `lookback_months=12`, `vol_com=60`, `signal="12"`, `trend_filter=True`.

## ETF mapping and proxies

| Sleeve | ETF | Pre-inception proxy (`proxies_for`) | Proxy data from | First eligible (13 month-ends) |
|---|---|---|---|---|
| US large cap | SPY | VFINX | 1980 | before 2000 |
| US small cap | IWM | NAESX | 1980 | before 2000 |
| EAFE | EFA | VTMGX | 1999-08-17 | 2000-08 |
| Emerging markets | EEM | VEIEX | 1994 | before 2000 |
| Japan | EWJ | — (ETF since 1996-03-18) | — | before 2000 |
| Europe | VGK | VEURX | 1990 | before 2000 |
| 7–10y Treasuries | IEF | VFITX | 1991 | before 2000 |
| 20+y Treasuries | TLT | VUSTX | 1986 | before 2000 |
| IG corporates | LQD | VFICX | 1993 | before 2000 |
| TIPS | TIP | VIPSX | 2000-06-29 | 2001-06 |
| US REITs | VNQ | VGSIX | 1996 | before 2000 |
| Commodities | DBC | PCRIX | 2002-07-01 | 2003-07 |
| Gold | GLD | GC=F (front-month futures) | 2000-08-30 | 2001-08 |
| Cash | BIL | `@tbill` (synthetic from ^IRX, net of 0.10%) | 1970 | always |

- Proxy data makes up 16.3% of gross exposure-days (`proxy_share`).
- Every symbol has real ETF data from 2007-05-30, when BIL launched. The `etf_era` variant starts on 2008-08-01.

## Deviations from the source

- **Long/flat instead of long/short.** MOP and HOP short every asset with a negative trend. Here those assets go to T-bills instead. This removes the "crisis alpha" that comes from short positions: short equities in late 2008, short bonds in 2022, short commodities in 2014–15 and 2008-H2. In 2022 this version can only sit in cash, while the SG Trend Index made a record +27%.
- **No leverage.** MOP size each position to 40% ex-ante vol (≈5–8× notional in bond futures), and HOP target 10% portfolio vol. Here the inverse-vol budget is normalized to sum to 1, so realized vol is only about 5%. Neither portfolio-level vol targeting (HOP) nor leverage is applied.
- **Bonds held at inverse-vol weight.** Treasuries, TIPS and IG credit have the lowest vol, so they get the largest budgets. Averaged over time, TIP, LQD, IEF and TLT make up about 36% of the portfolio, BIL 34%, and equities, REITs and commodities about 31%. Bond returns therefore dominate the result, and 2000–2020 was a long bond bull market.
- **ETFs instead of futures.**
  - The universe has 13 ETFs instead of 58 futures, with no currencies.
  - Returns are total returns minus BIL, rather than futures excess returns.
  - Pre-inception mutual-fund proxies report NAV only, and foreign-fund NAVs are stale relative to the US close, which understates their daily vol a little before about 2003.
- **Time-varying universe.** Assets enter once they have 13 month-ends and 120 daily returns. This follows MOP, who average over the S_t instruments available at *t*.
- **Execution.** The papers rebalance at the month-end close. Here fills happen at the next session's open with 5 bps slippage, SEC/FINRA fees and whole shares. The `exec_next_close` and `delay_2` variants show the timing barely matters for the 12-month signal.
- **Initial rebalance.** The first decision is on 2000-01-03, which is not a month-end. The harness convention of treating the latest close as the current month's close means that first "12-month" return is measured from 1999-01-29.

## Known critiques and post-publication evidence

- **Kim, Tse & Wald (2016).** MOP's alphas come largely from volatility scaling. Unscaled TSMOM performs about like unscaled buy-and-hold.
- **Huang, Li, Wang & Zhou (2020).** Asset-by-asset tests show little evidence of time-series predictability. A strategy built on historical sample means (i.e. assets' unconditional drift) performs about the same as TSMOM. The `trend_filter=False` control tests this directly for a long-only book: see the results.
- **Hamill, Rattray & Van Hemert (2016).** Trend following behaves like a long straddle, and much of its crisis alpha comes from being able to go short. Restricting it from being long equities or bonds changes its payoff profile. A long-only version gives up the short half of that straddle.
- **Weak 2010s.** HOP report a net Sharpe of 0.41 for 2010–2016, against 0.76 over 1880–2016. Babu et al. (2020) attribute this to muted market moves.
- **Short lookbacks are fragile to delay.** HOP's lagged-signal test cuts the 1- and 3-month Sharpe ratios roughly in half, while 12-month barely changes.

## Results

> **Note:** the numbers in this section come from the strategy's own branch run, which used a flat 5 bps slippage on every fill and an earlier harness version. The final numbers, from the tiered 2/4/6 bps cost model with the harness fixes applied, are in [`reports/comparison.md`](../../reports/comparison.md) and `results/<strategy>/summary.json` on the comparison branch. Conclusions are unchanged unless noted there.

Backtest settings:

- Period: 2000-01-03 → 2026-09-25 (26.7 years).
- `next_open` fills, 5 bps slippage plus fees, whole shares, $100k starting capital.
- Proxies on; idle cash earns 0%.
- Command: `trader backtest configs/strategies/tsmom_longflat.yaml --suite --offline --workers 2 --out results/tsmom_longflat`

### Headline (`results/tsmom_longflat/summary.json`)

| Metric | Full period | In-sample (2000-01-03 → 2011-12-09) | Out-of-sample (2011-12-12 → 2026-09-25) |
|---|---|---|---|
| CAGR | 5.62% | 7.63% | 4.02% |
| Volatility | 5.07% | 5.53% | 4.66% |
| Sharpe (excess of T-bills) | 0.72 | 0.95 | 0.51 |
| Sortino | 1.02 | 1.37 | 0.70 |
| Max drawdown | −10.40% (2020-02-21 → 2020-03-19) | −8.42% | −10.40% |
| Calmar | 0.54 | 0.91 | 0.39 |
| SPY CAGR (benchmark) | 8.31% | 0.47% | 15.08% |

- **Trading:** turnover is 1.37× per year, cost drag 0.15% per year, and about 115 fills per year (14 symbols resized monthly). Average gross exposure is 0.998.
- **Relation to SPY:** beta 0.10, correlation 0.37.
- **Bootstrap 90% CI:** Sharpe 0.42–1.05, CAGR 4.1–7.3%, max drawdown −15.7% to −7.4%.
- **Significance:** Deflated Sharpe 0.999 over 16 trials.

### Crisis returns

| Episode | Return |
|---|---|
| Dot-com bust (2000-03 → 2002-10) | +15.9% |
| GFC (2007-10 → 2009-03) | +4.9% |
| Euro / US downgrade (2011-04 → 2011-10) | −3.0% |
| Q4 2018 selloff | −2.7% |
| COVID crash (2020-02 → 2020-03) | −7.0% |
| 2022 inflation bear | −4.2% |
| 2025 tariff shock (2025-02 → 2025-04) | −4.0% |

Positioning in stress periods:

- **2008.** At end-September 2008 the book was 39% BIL, 51% TIP/IEF/TLT and 11% DBC/GLD, with no equities. At end-October 2008 it was 62% BIL, 23% IEF and 15% TLT. At end-December 2008 it was 48% BIL, with IEF, TLT, LQD and GLD.
- **2022.** At end-June 2022 it was 86% BIL, with GLD and DBC. The average BIL target over 2022 was 80%.

### Robustness suite (`variants.json`)

| Variant | Description | CAGR | Vol | Sharpe | Max DD | Turnover |
|---|---|---|---|---|---|---|
| base | published parameters | 5.62% | 5.07% | 0.72 | −10.4% | 1.37× |
| costs_0x | all trading costs ×0 | 5.76% | 5.07% | 0.75 | −10.4% | 1.37× |
| costs_2x | all trading costs ×2 | 5.47% | 5.07% | 0.70 | −10.4% | 1.37× |
| costs_4x | all trading costs ×4 | 5.17% | 5.07% | 0.64 | −10.5% | 1.37× |
| exec_next_close | fill at next close | 5.57% | 5.07% | 0.71 | −10.0% | 1.37× |
| delay_2 | one extra session before the fill | 5.62% | 5.08% | 0.72 | −9.9% | 1.37× |
| shift_5 | decide 5 sessions before month-end | 5.30% | 5.27% | 0.64 | −16.7% | 1.42× |
| shift_10 | decide 10 sessions before month-end | 5.13% | 5.22% | 0.62 | −16.1% | 1.34× |
| lookback_months=3 | | 5.07% | 4.87% | 0.65 | −9.2% | 2.77× |
| lookback_months=6 | | 5.26% | 4.94% | 0.67 | −10.4% | 1.93× |
| lookback_months=9 | | 5.15% | 5.22% | 0.62 | −16.1% | 1.75× |
| vol_com=20 | | 5.61% | 5.05% | 0.73 | −10.1% | 1.62× |
| vol_com=120 | | 5.59% | 5.07% | 0.72 | −10.2% | 1.29× |
| signal=blend | HOP 1/3/12 blend | 5.04% | 4.43% | 0.70 | −7.9% | 2.55× |
| **trend_filter=False** | **control: inverse-vol, always long** | **6.25%** | **7.56%** | **0.59** | **−23.8%** | **0.32×** |
| etf_era | start 2008-08-01, no proxy data held | 4.18% | 5.06% | 0.56 | −10.4% | 1.44× |

In-sample vs out-of-sample for the two most informative variants, split at 2011-12-11 and computed from `variant_returns.parquet`:

| Variant | IS CAGR | IS Sharpe | IS MaxDD | OOS CAGR | OOS Sharpe | OOS MaxDD |
|---|---|---|---|---|---|---|
| base (trend, 12-month) | 7.63% | 0.95 | −8.4% | 4.02% | 0.51 | −10.4% |
| control (`trend_filter=False`) | 7.84% | 0.72 | −23.8% | 4.97% | 0.47 | −21.3% |
| blend (1/3/12) | 7.20% | 1.04 | −6.6% | 3.33% | 0.40 | −7.9% |

### Comparison with the source and honest reading

- **Versus HOP, by sub-period.** HOP's net-of-2/20-fee Sharpe is 0.61 for 2000–2009 and 0.41 for 2010–2016. Before fees their figures are 9.9% / 10.3% vol (≈0.96) and 6.2% / 8.1% vol (≈0.77). This backtest gives:
  - 2000–2009: Sharpe 0.96, CAGR 7.7%, vol 5.1%.
  - 2010–2016: Sharpe 0.72, CAGR 3.8%.
  - 2017–2026: Sharpe 0.48, CAGR 4.8%.

  The Sharpe ratios are close to HOP's gross-of-fee numbers, but the similarity is partly a coincidence. This book has half HOP's volatility, no short leg, and gets much of its return from a long-duration bond sleeve during the 2000–2020 fall in rates.
- **Versus MOP (Sharpe > 1 gross, 1985–2009, levered long/short futures).** This version does not come close over the full period (0.72), and it is not designed to.
- **Versus the spec's expectations.** CAGR (5.6%) and the late-2008 bond/BIL positioning match. Volatility (5.1%) and max drawdown (−10.4%) are lower than the 6–9% and −15% to −25% expected. The inverse-vol budget puts roughly 70% in bonds plus BIL, and BIL absorbs every flat slot.
- **What the trend filter adds.** Against the control, the trend filter:
  - raises the full-period Sharpe from 0.59 to 0.72;
  - cuts the max drawdown from −23.8% to −10.4%, the dot-com and GFC periods being where it earns its keep;
  - lowers CAGR from 6.25% to 5.62%.

  Out-of-sample, the Sharpe advantage almost disappears (0.51 vs 0.47), while the drawdown protection remains (−10.4% vs −21.3%). This fits Huang et al.: in a long-only book most of the return is the assets' drift, and the trend overlay mostly works as a drawdown control.
- **Post-publication decay.** It is clear: OOS CAGR is 4.0% versus 7.6% IS, and Sharpe 0.51 versus 0.95. The ETF-only era (2008-08 onward) gives Sharpe 0.56.
- **Timing luck.** It matters for the tail. Deciding 5–10 sessions before month-end turns the COVID drawdown from −10.4% into about −16.5%, because the book was still long equities and REITs for the first weeks of March 2020. The 9-month lookback hits the same −16%. The −10.4% headline drawdown should therefore be read as roughly −10% to −17%.
- **Sanity checks performed.**
  - Recomputed the targets independently, with full-history plain pandas, on 10 dates (2000-01-03, 2001-06-29, 2003-07-31, 2008-09/10/12, 2013-06, 2020-03, 2022-06, 2026-08). They match to 1e-10. The one exception is 7e-5 on 2003-07-31, caused by the GLD-proxy holiday bridge.
  - No asset is held before its data exists. First targets: EFA 2000-08, TIP 2001-06, GLD 2001-09, DBC 2003-07.
  - The largest daily return is 2.5% (2011-08-09); there are no suspicious jumps.
  - On 2004-01-02 the engine dropped a GLD order because GC=F has no bar that day. GLD kept its prior size for one month. The effect is negligible.

**Assessment.** This is a low-volatility (≈5%), low-beta (0.10) defensive allocation with a good record of limiting drawdowns. It is not a return engine: out-of-sample it earned about 2.4% per year over T-bills. It is a reasonable live candidate only as a conservative or diversifying sleeve. Be aware that its edge over a plain inverse-vol portfolio is mainly drawdown control, that the drawdown depends on rebalance timing, and that a big part of its historical return came from bonds in a falling-rate era that is unlikely to repeat.
