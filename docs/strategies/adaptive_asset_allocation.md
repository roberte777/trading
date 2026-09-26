# Adaptive Asset Allocation (top 5, min-variance)

Registry name: `adaptive_asset_allocation`. Code: `src/trader/strategies/adaptive_asset_allocation.py`. Config: `configs/strategies/adaptive_asset_allocation.yaml`. Results: `results/adaptive_asset_allocation/`.

## Summary

Adaptive Asset Allocation (AAA) combines cross-sectional momentum with minimum-variance weighting across ten global asset classes. At each month-end it keeps the five assets with the best six-month (126-session) total return. It then weights them with a long-only minimum-variance portfolio. The covariance matrix combines 126-day correlations with 20-day volatilities. The portfolio is always fully invested: there is no cash or absolute-momentum filter.

## Sources

- Butler, A., Philbrick, M., Gordillo, R. & Varadi, D. "Adaptive Asset Allocation: A Primer." SSRN 2328254, dated 2012-05-31, posted 2013-09-21. <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2328254>
- First public version: GestaltU blog post and whitepaper, May 2012. <https://www.gestaltu.com/2012/05/adaptive-asset-allocation-a-true-revolution-in-portfolio-management.html/>
- 2015 revision (ReSolve Asset Management), which includes the "Managing Expectations" caution. <https://www.investresolve.com/inc/uploads/pdf/Adaptive-Asset-Allocation-Whitepaper.pdf>
- AllocateSmartly, "Adam Butler / GestaltU: Adaptive Asset Allocation". AllocateSmartly says it agreed these rules with the authors, because "complete strategy rules are not precisely stated in the paper". <https://allocatesmartly.com/adam-butler-gestaltu-adaptive-asset-allocation/>
- **Publication date used for the out-of-sample split: 2012-05-01** (the May 2012 GestaltU post). Results after that date are out-of-sample.

## Rules as implemented

The strategy decides at the close of the last session of each month (`MonthEnd()`). Orders fill at the next session's open.

1. **Eligibility.** An asset is eligible if it has a close today and an unbroken history of `max(momentum_days + 1, max(corr_days, vol_days) + 2)` closes. With the defaults that is 128 closes: 127 daily returns (`corr_days + 1`) and at least 127 closes for momentum (`momentum_days + 1`).
   - Isolated vendor gaps inside that window are forward-filled. This matters only for the GC=F gold proxy, which is missing 8 NYSE sessions between 2000 and 2004.
   - Missing data *before* an asset's first bar is never filled, so a young asset is ineligible.
   - An asset with no close today (a vendor gap on the decision day) gets no weight.
2. **Momentum.** `close[t] / close[t − momentum_days] − 1` on total-return-adjusted closes. Keep the top `top_n` (5). Ties keep universe order. If fewer than `top_n` assets are eligible, all eligible assets are kept.
3. **Covariance.** `Σ = D · C · D`, where:
   - `C` is the sample correlation of the last `corr_days` (126) daily returns of the selected assets;
   - `D` is the diagonal of their sample standard deviations over the last `vol_days` (20) daily returns (ddof = 1).
4. **Weights.** The long-only minimum-variance portfolio: minimize `wᵀΣw` subject to `Σw = 1` and `0 ≤ w ≤ 1`.
   - Solved with `scipy.optimize.minimize(method="SLSQP")`, starting from equal weights, with an analytic gradient.
   - Before solving, `Σ` is divided by its mean variance. This does not change the minimizer. It keeps the objective near 1, so SLSQP's absolute tolerance (`ftol = 1e-12`) is meaningful for daily-return variances of about 1e-4.
   - If the solver fails, the strategy falls back to inverse-variance weights. This never happened in the backtest (0 fallbacks in 321 decisions).
   - Check: on all 321 decisions, the SLSQP weights match an exact active-set enumeration of the long-only min-var problem to within 5e-5.
5. **Minimum weight.** Positions under `min_weight` (2%) are dropped, and the remaining weights are renormalized to sum to 1.
6. **Always fully invested.** No cash sleeve and no absolute-momentum filter.

| Param | Default (published) | Grid (robustness suite) |
|---|---|---|
| `momentum_days` | 126 | 63, 252 |
| `top_n` | 5 | 3, 4 |
| `vol_days` | 20 | — |
| `corr_days` | 126 | 63, 252 |
| `min_weight` | 0.02 | — |

## ETF mapping and proxies

| Asset class | ETF | Real ETF data from | Pre-inception proxy (from) | First eligible decision |
|---|---|---|---|---|
| US stocks | SPY | 1993-01-29 | VFINX | start |
| European stocks | EZU | 2000-07-31 | VEURX (1990-06) | start |
| Japanese stocks | EWJ | 1996-03-18 | none needed | start |
| Emerging markets | EEM | 2003-04-14 | VEIEX (1994-05) | start |
| US REITs | VNQ | 2004-09-29 | VGSIX (1996-05) | start |
| International REITs | RWX | 2006-12-19 | FIREX (2004-09-09) | 2005-03 |
| Intermediate Treasuries | IEF | 2002-07-30 | VFITX (1991-10) | start |
| Long Treasuries | TLT | 2002-07-30 | VUSTX (1986-05) | start |
| Commodities | DBC | 2006-02-06 | PCRIX (2002-07-01) | 2003-01 |
| Gold | GLD | 2004-11-18 | GC=F front-month futures (2000-08-30) | 2001-03 |

- Proxies are spliced on returns by the harness (`proxies = proxies_for(UNIVERSE)`).
- 15.3% of gross exposure-days over the backtest are held in proxy data.
- The `etf_era` variant starts on 2007-06-29 and holds no proxy data.

**Time-varying universe (flag).** The authors test a fixed 10-asset universe from 1995. Here, eligibility depends on data:

- From 2000-01 until GLD becomes eligible (2001-03), the strategy picks the top 5 of 7 assets.
- It picks the top 5 of 8 until DBC is eligible (2003-01), then the top 5 of 9 until RWX is eligible (2005-03).
- No usable total-return commodity series exists on Yahoo before PCRIX (2002-07). Nothing exists for international REITs before FIREX (2004-09).

## Deviations from the source

- **Covariance windows.** Neither the 2012 post nor the 2015 revision states the covariance windows. This implementation uses the specification AllocateSmartly agreed with the authors: 126-day correlation with 20-day volatility, and a 2% minimum position.
- **Execution.** The source and AllocateSmartly trade at the month-end close. Here, orders fill at the next session's open, with 5 bps slippage, SEC/FINRA fees and whole-share rounding. The `exec_next_close` variant (CAGR 10.28%) shows the timing cost is small.
- **Sample and data.**
  - The authors test from 1995 on indexes and mutual funds. This backtest starts on 2000-01-03, on ETFs spliced with the proxies above.
  - Before about 2003, several sleeves are no-load mutual funds that report NAV only (open = close).
  - International funds' NAVs can be stale relative to the US close. That understates their daily correlation with US assets, and min-var exploits low correlations.
- **Universe size early on.** Before 2005-03 there are fewer than ten candidates (see above).
- **GC=F data gap.** The GC=F gold proxy has no bar on 2004-01-02, the fill day after the 2003-12-31 decision. The harness drops the GLD buy order (64.7% target weight), so the portfolio held about 64% cash through January 2004. The strategy cannot see this in advance; see the harness notes below.
- **No max-weight cap.** None was published, so none is used.

## Known critiques and post-publication evidence

- **No absolute filter.** AAA ranks assets only against each other, so it is always 100% invested even when every asset is falling.
  - In 2022, IEF made the top 5 in most months despite losing about 10%, because everything else was worse.
  - IEF + TLT made up 47–100% of target weight from 2022-04 through 2022-11.
  - The strategy lost 9.4% in calendar 2022 (−10.7% over the harness's "2022 inflation bear" window). Its maximum drawdown, −19.3% (2022-03 → 2023-10), is entirely out-of-sample.
- **Min-var concentration.** With only five candidates, long-only min-var often hits corner solutions.
  - The median holding count is 3; five assets were held in only 11 of 321 months.
  - Twelve months were 100% in a single asset: 11 times SPY (2009–2013) and once IEF (2022-11).
  - The largest position averaged 67% of the portfolio, and was at least 50% in 84% of decisions.
  - IEF + TLT averaged 36% of target weight. That is hidden duration exposure, which hurt in 2022.
  - The concentration also makes rebalance timing matter a lot. Deciding 10 sessions early (`shift_10`) put 100% in RWX on 2020-02-13, just before COVID: max drawdown −39% versus −19% for the base run. The Sharpe falls from 0.91 to 0.75 (`shift_5`) and 0.59 (`shift_10`).
- **Short covariance windows drive turnover.** The 20-day volatility estimate changes a lot from month to month.
  - Turnover is 5.3× equity per year, with about 48 trades per year and 0.58%/yr cost drag at base costs.
  - At 4× costs, CAGR falls from 10.5% to 8.7%.
- **The authors' own caution.** The 2015 revision's "Managing Expectations" section warns that "returns in the future may not live up to what we have observed in testing".
  - Consistent with that and with McLean & Pontiff (2016), out-of-sample Sharpe is 0.81 versus 1.01 in-sample, and CAGR is 9.0% versus 12.3%.
  - Out-of-sample, AAA trailed SPY by 5.5 points a year (9.0% vs 14.5% CAGR), with a much shallower drawdown.
- No peer-reviewed critique specific to AAA was found. The momentum-crash evidence (Daniel & Moskowitz 2016) also applies to its relative-momentum leg.

## Results

Source: `results/adaptive_asset_allocation/summary.json`. Full period 2000-01-03 → 2026-09-25 (26.7 years), next-open fills, base costs. "Sharpe" is the excess-return Sharpe ratio (over T-bills).

| Metric | Full period | In-sample (2000-01 → 2012-05-01) | Out-of-sample (2012-05-02 → 2026-09) |
|---|---|---|---|
| CAGR | 10.54% | 12.34% | 9.01% |
| Volatility | 9.43% | 9.85% | 9.06% |
| Sharpe | 0.91 | 1.01 | 0.81 |
| Sortino | 1.28 | 1.43 | 1.14 |
| Max drawdown | −19.31% | −15.83% | −19.31% |
| Calmar | 0.55 | 0.78 | 0.47 |
| SPY CAGR (same window) | 8.31% | 1.45% | 14.55% |
| Turnover (× equity / yr) | 5.34 | | |
| Cost drag (per yr) | 0.58% | | |

Other full-period statistics:

- Beta to SPY 0.19; down-capture 0.15.
- 66% of months positive; worst month −11.6% (2004-04: 62% VNQ + 38% DBC in the REIT sell-off).
- Bootstrap 90% confidence intervals: Sharpe 0.61–1.23, CAGR 7.5%–13.8%.
- Deflated Sharpe ratio 0.9998 over 15 trials.

**Crisis returns**

| Episode | Return |
|---|---|
| Dot-com bust (2000-03 → 2002-10) | +29.0% |
| GFC (2007-10 → 2009-03) | +6.8% |
| Euro/US downgrade (2011-04 → 2011-10) | +4.8% |
| Q4 2018 selloff | −0.2% |
| COVID crash (2020-02 → 2020-03) | −6.8% |
| 2022 inflation bear | −10.7% |
| 2025 tariff shock (2025-02 → 2025-04) | −6.3% |

**Robustness suite** (`variants.json`)

| Variant | CAGR | Vol | Sharpe | Sortino | Max DD | Calmar | Turnover | Cost drag |
|---|---|---|---|---|---|---|---|---|
| base | 10.54% | 9.43% | 0.91 | 1.28 | −19.3% | 0.55 | 5.34 | 0.58% |
| costs ×0 | 11.14% | 9.44% | 0.96 | 1.36 | −19.0% | 0.59 | 5.34 | 0.00% |
| costs ×2 | 9.94% | 9.43% | 0.85 | 1.19 | −20.0% | 0.50 | 5.33 | 1.15% |
| costs ×4 | 8.74% | 9.43% | 0.73 | 1.02 | −21.2% | 0.41 | 5.33 | 2.28% |
| fill at next close | 10.28% | 9.45% | 0.88 | 1.24 | −20.0% | 0.51 | 5.33 | 0.58% |
| delay 2 sessions | 10.20% | 9.49% | 0.87 | 1.22 | −19.2% | 0.53 | 5.35 | 0.58% |
| decide 5 sessions early | 9.45% | 10.09% | 0.75 | 1.05 | −20.8% | 0.45 | 5.28 | 0.58% |
| decide 10 sessions early | 7.83% | 10.45% | 0.59 | 0.79 | −39.2% | 0.20 | 5.57 | 0.59% |
| momentum_days = 63 | 7.15% | 9.72% | 0.56 | 0.78 | −30.4% | 0.24 | 6.27 | 0.67% |
| momentum_days = 252 | 10.82% | 9.91% | 0.89 | 1.24 | −18.9% | 0.57 | 4.54 | 0.48% |
| top_n = 3 | 10.63% | 12.47% | 0.72 | 1.01 | −22.6% | 0.47 | 6.09 | 0.63% |
| top_n = 4 | 9.98% | 10.94% | 0.75 | 1.05 | −24.2% | 0.41 | 5.90 | 0.62% |
| corr_days = 63 | 10.71% | 9.44% | 0.92 | 1.30 | −20.2% | 0.53 | 5.35 | 0.58% |
| corr_days = 252 | 10.32% | 9.42% | 0.89 | 1.25 | −19.2% | 0.54 | 5.38 | 0.59% |
| ETF era only (from 2007-06-29) | 10.23% | 9.60% | 0.91 | 1.28 | −19.3% | 0.53 | 5.37 | 0.58% |

### Comparison with the source

The authors report "Sharpe" as return / volatility, not excess return / volatility, so the comparison below uses return / vol.

| | Period | CAGR | Vol | Return / vol | Max DD |
|---|---|---|---|---|---|
| 2015 revision, top-5 min-var | 1995-01 → 2014-11 | 15.0% | 9.4% | 1.60 | −8.8% |
| 2012 post, top-5 min-var | 1995 → 2012-05 | 15.4% | — | 1.71 | < 16% |
| This backtest | 2000-01 → 2014-11 | 12.0% | 9.6% | 1.25 | −15.8% |
| This backtest | 2000-01 → 2012-05 | 12.3% | 9.8% | 1.25 | −15.8% |

- **Volatility matches** the 2015 revision (9.6% vs 9.4%).
- **Max drawdown matches the 2012 post** ("< 16%"), but not the 2015 revision's −8.8%. The 2015 revision probably used a different, unpublished covariance specification. Our −15.8% in-sample trough came in May–June 2006, when a portfolio concentrated in RWX/EZU/GLD fell together.
- **CAGR is about 3 points lower** than the source. Likely reasons:
  1. The source window includes 1995–1999, a very strong period for the momentum leaders. Our window starts at the dot-com peak.
  2. The source fills at the same close as the signal; here fills are at the next open, with costs (about 0.6%/yr drag).
  3. Early on our universe has 7–9 assets instead of 10, and the proxies differ.
  4. The source's covariance specification differs, as noted above.

  None of these points to an implementation error. Every decision's weights were checked against an independent exact min-var computation.
- **Post-publication decay is clear.** Out-of-sample Sharpe fell from 1.01 to 0.81 and CAGR from 12.3% to 9.0%. The worst drawdown (−19.3%) is out-of-sample, driven by bond concentration in 2022, as the spec anticipated.

### Harness notes

- **Missing GC=F proxy bars.** The GC=F proxy (gold before GLD) is missing 8 NYSE sessions: 2000-11-24, 2001-11-23, 2001-12-24, 2002-07-05, 2002-11-29, 2003-11-28, 2003-12-26 and 2004-01-02.
  - The loader leaves these as NaN.
  - The engine drops any order whose fill price is NaN (`src/trader/backtest/engine.py`, `ref_for` in `_execute`: "no next_open price ... order dropped").
  - On 2004-01-02 this dropped a 64.7% GLD buy, so the base run sat about 64% in cash for January 2004. The `shift_5`/`shift_10` variants hit other gaps.
  - The effect on the headline numbers is small (one month), but proxy gaps could be forward-filled in the loader, or unfilled orders carried to the next session.
