# Equal risk contribution (MRT 2010): `risk_parity_erc`

## Summary

- Long-only, fully invested, unlevered risk parity over nine asset-class ETFs: SPY, EFA, EEM, IEF, TLT, TIP, GLD, DBC, VNQ.
- At each month-end, the strategy estimates the covariance of the last 252 daily returns and holds the portfolio in which every asset contributes the same share of portfolio variance (the ERC portfolio of Maillard, Roncalli & Teiletche).
- There is no return forecast, cash leg or leverage. The result is a bond-heavy portfolio (IEF+TLT+TIP average 56% of capital, range 40–71%) with about 7% volatility.
- Module: `src/trader/strategies/risk_parity_erc.py` (class `EqualRiskContribution`). Config: `configs/strategies/risk_parity_erc.yaml`. Results: `results/risk_parity_erc/`.

## Sources

- Maillard, S., Roncalli, T., Teiletche, J. (2010). "The Properties of Equally Weighted Risk Contribution Portfolios." *Journal of Portfolio Management* 36(4), 60–70. DOI [10.3905/jpm.2010.36.4.060](https://doi.org/10.3905/jpm.2010.36.4.060). Working paper: http://www.thierry-roncalli.com/download/erc.pdf. SSRN 1271972: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1271972.
- Asness, C., Frazzini, A., Pedersen, L. H. (2012). "Leverage Aversion and Risk Parity." *Financial Analysts Journal* 68(1), 47–59. DOI [10.2469/faj.v68.n1.1](https://doi.org/10.2469/faj.v68.n1.1). PDF: https://www.aqr.com/-/media/AQR/Documents/Insights/Journal-Article/Leverage-Aversion-and-Risk-Parity.pdf.
- Griveau-Billion, T., Richard, J.-C., Roncalli, T. (2013). "A Fast Algorithm for Computing High-dimensional Risk Parity Portfolios." https://arxiv.org/abs/1311.4057. Background for the solver.
- Critiques:
  - Chaves, D., Hsu, J., Li, F., Shakernia, O. (2011). "Risk Parity Portfolio vs. Other Asset Allocation Heuristic Portfolios." *Journal of Investing* 20(1), 108–118. DOI [10.3905/joi.2011.20.1.108](https://doi.org/10.3905/joi.2011.20.1.108). SSRN: https://www.ssrn.com/abstract=1917064.
  - Anderson, R., Bianchi, S., Goldberg, L. (2012). "Will My Risk Parity Strategy Outperform?" *Financial Analysts Journal* 68(6), 75–93. SSRN: https://www.ssrn.com/abstract=2101898.
- **Publication date used for the out-of-sample split: 2008-06-01.** The working paper says "First version: June 2008", and SSRN 1271972 was posted in September 2008. Returns from 2008-06-02 onward are out-of-sample.

## Rules as implemented

1. **Schedule.** Decide at the close of the last NYSE session of each month (`MonthEnd()`). Orders fill at the next session's open (`next_open`). The first backtest session (2000-01-03) also trades, because `initial_rebalance` is on.
2. **Price window.** Take the last `cov_days + 1 + 5` total-return-adjusted closes. Forward-fill them, then keep the last `cov_days + 1` rows (253 for the default). Forward-filling only bridges single missing days inside a proxy series (see the deviations section).
3. **Eligibility.** An asset is eligible when all of the following hold:
   - it has a close in every one of the `cov_days + 1` rows, which means at least `cov_days` daily returns;
   - it has a real (not forward-filled) close within the last 5 sessions;
   - its returns in the window have non-zero variance.

   Assets without enough history never get weight. They join at the first month-end after they reach 252 returns.
4. **Covariance.**
   - `return_freq="daily"` (default): the sample covariance (ddof = 1) of the `cov_days` simple daily returns.
   - `return_freq="weekly"`: the sample covariance of non-overlapping 5-session returns ending at the decision close, over the same window. With 252 days that is 50 weekly returns.
5. **ERC weights.** Solve MRT's convex problem `min_y ½ yᵀΣy − (1/n) Σ ln y_i`, y > 0, then set `x = y / Σy`.
   - The solver is Newton's method, started from inverse-vol weights and run on Σ divided by its mean variance (ERC weights do not depend on the scale of Σ).
   - Far from the optimum, an Armijo backtracking line search damps the steps and keeps y > 0. Once the Newton decrement drops below 1e-10, the solver takes full steps: near the optimum, changes in the objective fall below floating-point noise, and a line search would stall. On every decision date in the backtest it converged in 5 steps.
   - After solving, the code checks that every risk contribution `x_i (Σx)_i` equals their mean to within 1e-6 relative. If not, it raises an error.
   - The unit tests cross-check the solver against `scipy.optimize.minimize` (L-BFGS-B, bounds [1e-10, ∞)), the formulation named in the spec. On 9 sample decision dates (2000–2026), the backtest targets agreed with an independent scipy solve to within 4e-8. Across all 321 decision dates, the largest relative gap between risk contributions was 3e-12.
   - With one eligible asset the weight is 100%. With none, the strategy returns an empty target (never happened in the backtest).
6. **Fully invested.** Weights sum to 1. There is no cash leg, no leverage and no weight cap.
7. **Params.** Defaults are the published values: `cov_days = 252` (MRT §4.2, "rolling one-year window" of daily returns) and `return_freq = "daily"`. `param_grid = {cov_days: [126, 504], return_freq: ["weekly"]}`.

## ETF mapping and proxies

Proxies come from `proxies_for(UNIVERSE)`. The "eligible from" column is the first month-end with 252 daily returns, including proxy history.

| Asset class | ETF | Real ETF data from | Proxy (from) | Eligible from |
|---|---|---|---|---|
| US equity | SPY | 1993-01-29 | VFINX (1980) | start (2000-01-03) |
| Developed ex-US equity | EFA | 2001-08-27 | VTMGX (1999-08-17) | 2000-08-31 |
| Emerging equity | EEM | 2003-04-14 | VEIEX (1994) | start |
| Intermediate Treasuries | IEF | 2002-07-30 | VFITX (1991) | start |
| Long Treasuries | TLT | 2002-07-30 | VUSTX (1986) | start |
| TIPS | TIP | 2003-12-05 | VIPSX (2000-06-29) | 2001-06-29 |
| Gold | GLD | 2004-11-18 | GC=F front-month futures (2000-08-30) | 2001-08-31 |
| Commodities | DBC | 2006-02-06 | PCRIX (2002-07-01) | 2003-07-31 |
| US REITs | VNQ | 2004-09-29 | VGSIX (1996) | start |

**Partial early universe:**

| Period | Assets held |
|---|---|
| 2000-01 → 2000-07 | 5: SPY, EEM, IEF, TLT, VNQ |
| 2000-08 → 2001-05 | 6: adds EFA |
| 2001-06 → 2001-07 | 7: adds TIP |
| 2001-08 → 2003-06 | 8: adds GLD |
| From 2003-07-31 | all 9: adds DBC |

- 12.5% of gross exposure-days are held in proxy data (`proxy_share`).
- The `etf_era` variant starts on 2007-02-28 and holds no proxy data.

## Deviations from the source

- **Different universe.** MRT's "global diversified" example used 13 indices: S&P 500, Russell 2000, Euro Stoxx 50, FTSE 100, Topix, MSCI LatAm, MSCI EM Europe, MSCI Asia ex-Japan, JPM Euro and US government bonds, ML US High Yield, EMBI and S&P GSCI. This implementation uses the dossier's practitioner 9-ETF set. The differences:
  - there is no credit (HY, EM debt);
  - there are three US Treasury/TIPS funds and no euro government bonds;
  - gold and US REITs are added;
  - the equity sleeves are regional ETFs instead of single-country indices.
- **Time-varying universe.** Assets join once they have 252 daily returns, so 2000–2003 runs with 5–8 assets. MRT's sample started in 1995 with all 13 assets available.
- **Execution.** The paper rebalances at the month-end close. Here the signal is computed at that close and fills at the next session's open, with whole shares, 5 bp slippage and SEC/FINRA fees.
- **Risk-free rate.** Sharpe ratios use T-bills (^IRX accrual). MRT used Fed funds.
- **Proxy gaps.** GC=F (the gold proxy) has 8 missing closes between 2000 and 2004 (holiday-adjacent sessions). Two of them fall on month-ends (2002-11-29 and 2003-11-28).
  - For the covariance, missing closes are forward-filled (a 0 return, then a 2-day return).
  - A symbol stays tradable if it has a real close within the last 5 sessions. This departs from a plain `ctx.is_tradable()` check. Without it, gold would be sold and bought back around those dates.
  - When a fill-session open is missing, the harness drops that order and logs a warning (GLD on 2004-01-02 in the base run). The GLD position then drifts for one month.
- **Daily covariance on proxy-era data.** Mutual-fund NAVs and futures settlement times bias daily correlations toward zero (dossier §1.3). The `weekly` variant tests this.
- **Solver.** The spec prefers L-BFGS-B and lists Newton as an alternative. This implementation uses Newton, which is exact and fast for 9 assets; L-BFGS-B is used as the reference in the tests.

## Known critiques and post-publication evidence

- **ERC vs inverse-vol.**
  - ERC equals inverse-vol when all correlations are equal (MRT), and always for two assets. With nine assets the two differ only through the correlation structure.
  - Here the differences are small. In an approximate side calculation (close-to-close, no costs, same eligibility), inverse-vol and ERC had almost the same Sharpe: 0.67 vs 0.69, CAGR 6.63% vs 6.59%, max drawdown −20.3% vs −18.9%.
  - The average one-way weight difference between them was about 7% of capital. ERC moves weight from EFA, EEM, VNQ and TIP into IEF, TLT and DBC.
  - One might expect naive inverse-vol to over-concentrate risk in the correlated bond cluster. In this universe it does the opposite. Bonds are negatively correlated with equities, so under inverse-vol they carry only about 28% of risk. The correlated equity/REIT cluster carries about 52%. ERC corrects that toward 1/9 each.
  - Chaves et al. (2011) find that risk parity does not consistently beat 1/N or 60/40 on a risk-adjusted basis. It does beat min-variance and mean-variance.
- **Unlevered risk parity is bond-heavy and low-return, and it was helped by 1981–2020 falling yields.**
  - Unlevered, this portfolio earns roughly a bond-plus return. CAGR is 6.3% against 8.3% for SPY, and beta to SPY is 0.19.
  - Its best period (2000–2007: 10.5% CAGR, Sharpe 1.20) coincides with falling yields and a commodity/EM boom.
  - Inker (2010, GMO), as cited in Clare et al. (2016), argues that the 1981+ bond bull flattered risk parity backtests. AFP (2012) reply that 1926–2010 includes a near-complete round trip in yields.
- **2022.**
  - Stocks and bonds fell together. The strategy returned −13.8% in calendar 2022 and −17.9% over the 2022-01-03 → 2022-10-12 window.
  - That makes 2021-11 → 2022-10 its maximum drawdown (−19.1%), deeper than its GFC drawdown (−17.0% within 2008–2009).
  - For comparison: SPY −18.2%, AOR (60/40) −15.6%. RPAR, a levered risk parity ETF, returned −22.8%.
  - This unlevered version lost less than RPAR but more than a 60/40 fund would suggest for a portfolio with 7% volatility. The diversification that justifies the bond weight disappeared.
- **Leverage costs** (Anderson, Bianchi & Goldberg 2012):
  - Risk parity's case rests on levering the low-risk portfolio to equity-like volatility (AFP 2012). Financing costs and turnover can reverse its advantage over 60/40, and results depend heavily on start and end dates.
  - **This implementation is unlevered.** It does not claim equity-like returns. It is a low-volatility balanced portfolio, and the leverage question is not tested here.

## Results

> **Note:** the numbers in this section come from the strategy's own branch run, which used a flat 5 bps slippage on every fill and an earlier harness version. The final numbers, from the tiered 2/4/6 bps cost model with the harness fixes applied, are in [`reports/comparison.md`](../../reports/comparison.md) and `results/<strategy>/summary.json` on the comparison branch. Conclusions are unchanged unless noted there.

Run: `trader backtest configs/strategies/risk_parity_erc.yaml --suite --offline --workers 2 --out results/risk_parity_erc` (data through 2026-09-25).

### Headline (2000-01-03 → 2026-09-25, 26.7 years)

| Metric | Value |
|---|---|
| CAGR | 6.28% |
| Volatility | 6.73% |
| Sharpe (vs T-bills) | 0.65 |
| Sortino | 0.93 |
| Max drawdown | −19.1% (2021-11-09 → 2022-10-20) |
| Calmar | 0.33 |
| Turnover (one-way, annual) | 0.26× |
| Cost drag | 0.02% / yr |
| Trades per year | 102 (nine small monthly adjustments) |
| Beta / correlation to SPY | 0.19 / 0.54 |
| SPY CAGR, same period | 8.31% |
| Bootstrap 90% CI, Sharpe | 0.33 – 1.00 |
| Deflated Sharpe (12 local trials) | 0.998 |

### In-sample vs out-of-sample (split 2008-06-01)

| Period | CAGR | Vol | Sharpe | Max DD | SPY CAGR |
|---|---|---|---|---|---|
| In-sample 2000-01-03 → 2008-05-30 | 10.47% | 5.83% | 1.21 | −9.2% | 1.05% |
| Out-of-sample 2008-06-02 → 2026-09-25 | 4.40% | 7.10% | 0.45 | −19.1% | 11.80% |

### Sub-periods (dossier §8)

| Period | CAGR | Vol | Sharpe | Max DD |
|---|---|---|---|---|
| 2000–2007 | 10.51% | 5.81% | 1.20 | −9.2% |
| 2008–2009 | 1.48% | 9.65% | 0.12 | −17.0% |
| 2010–2021 | 5.37% | 6.00% | 0.82 | −14.8% |
| 2022–2026-09 | 3.67% | 8.23% | 0.00 | −18.4% |

### Crisis returns

| Window | ERC | SPY |
|---|---|---|
| Dot-com bust (2000-03 → 2002-10) | +12.6% | −47.2% |
| GFC (2007-10 → 2009-03) | −5.5% | −54.8% |
| Euro/US downgrade (2011-04 → 2011-10) | +0.9% | −18.4% |
| Q4 2018 selloff | −2.6% | −18.7% |
| COVID crash (2020-02 → 2020-03) | −11.1% | −33.4% |
| 2022 inflation bear | −17.9% | −24.1% |
| 2025 tariff shock (2025-02 → 2025-04) | −4.9% | −18.6% |

Calendar-year returns (ERC / SPY):

| Years | ERC / SPY |
|---|---|
| 2000–2004 | 2000 +9.4/−9.7, 2001 +2.7/−11.8, 2002 +8.5/−21.6, 2003 +19.2/+28.2, 2004 +12.0/+10.7 |
| 2005–2009 | 2005 +10.1/+4.8, 2006 +10.4/+15.8, 2007 +12.0/+5.1, 2008 −0.5/−36.8, 2009 +3.4/+26.4 |
| 2010–2014 | 2010 +11.7/+15.1, 2011 +10.0/+1.9, 2012 +7.8/+16.0, 2013 −3.2/+32.3, 2014 +3.8/+13.5 |
| 2015–2019 | 2015 −4.4/+1.2, 2016 +5.7/+12.0, 2017 +10.4/+21.7, 2018 −2.6/−4.6, 2019 +14.4/+31.2 |
| 2020–2024 | 2020 +6.8/+18.3, 2021 +5.8/+28.7, 2022 −13.8/−18.2, 2023 +7.6/+26.2, 2024 +6.1/+24.9 |
| 2025–2026 | 2025 +14.0/+17.7, 2026 YTD +5.7/+14.0 |

### Robustness suite (`variants.json`)

| Variant | Description | Start | CAGR | Vol | Sharpe | Sortino | Max DD | Calmar | Turnover | Cost drag |
|---|---|---|---|---|---|---|---|---|---|---|
| base | published params | 2000-01-03 | 6.28% | 6.73% | 0.65 | 0.93 | −19.1% | 0.33 | 0.26x | 0.024% |
| costs_0x | all trading costs x0 | 2000-01-03 | 6.31% | 6.73% | 0.66 | 0.93 | −19.1% | 0.33 | 0.26x | 0.000% |
| costs_2x | all trading costs x2 | 2000-01-03 | 6.25% | 6.73% | 0.65 | 0.92 | −19.1% | 0.33 | 0.26x | 0.049% |
| costs_4x | all trading costs x4 | 2000-01-03 | 6.19% | 6.73% | 0.64 | 0.91 | −19.2% | 0.32 | 0.26x | 0.097% |
| exec_next_close | fill at next close instead of next open | 2000-01-03 | 6.31% | 6.73% | 0.66 | 0.94 | −19.1% | 0.33 | 0.26x | 0.024% |
| delay_2 | fills one extra session after the signal | 2000-01-03 | 6.34% | 6.73% | 0.66 | 0.94 | −19.0% | 0.33 | 0.26x | 0.024% |
| shift_5 | decide 5 sessions before month-end | 2000-01-03 | 6.19% | 6.78% | 0.64 | 0.91 | −19.3% | 0.32 | 0.26x | 0.025% |
| shift_10 | decide 10 sessions before month-end | 2000-01-03 | 6.15% | 6.74% | 0.63 | 0.90 | −19.3% | 0.32 | 0.26x | 0.025% |
| param_cov_days=126 | 6-month covariance window | 2000-01-03 | 6.48% | 6.64% | 0.69 | 0.98 | −19.2% | 0.34 | 0.39x | 0.037% |
| param_cov_days=504 | 2-year covariance window | 2000-01-03 | 6.44% | 6.76% | 0.67 | 0.96 | −19.0% | 0.34 | 0.20x | 0.018% |
| param_return_freq=weekly | non-overlapping 5-session returns | 2000-01-03 | 6.16% | 6.76% | 0.63 | 0.90 | −19.4% | 0.32 | 0.61x | 0.062% |
| etf_era | start 2007-02-28, no proxy data held | 2007-02-28 | 4.82% | 7.01% | 0.49 | 0.69 | −19.1% | 0.25 | 0.25x | 0.025% |

- The strategy is insensitive to costs, execution timing, rebalance-day timing luck, the covariance window and the return frequency. Every variant except `etf_era` lands at Sharpe 0.63–0.69.
- The one big difference is the `etf_era` variant (Sharpe 0.49). It starts in 2007-02, so it drops the strong 2000–2006 stretch and is almost entirely the out-of-sample era (Sharpe 0.45). That points to the period, not to a proxy artifact.

### Comparison with the source

| | MRT global diversified, 1995–2008 | This backtest, 2000–2008 | This backtest, full period |
|---|---|---|---|
| ERC return | 7.58% | 9.23% | 6.28% |
| ERC vol | 4.92% | 6.44% | 6.73% |
| ERC Sharpe | 0.67 (vs Fed funds) | 0.94 | 0.65 |
| ERC max DD | −22.7% | −17.0% | −19.1% |
| 1/N vol / max DD | 10.87% / −45.3% | — | ≈10.6% / ≈−34% (approximate side calculation) |

- **Consistent with the paper:**
  - ERC roughly halves 1/N's volatility and drawdown.
  - The vol ordering σ_ERC < σ_1/N holds.
  - Over 2000–2008 the Sharpe is in the same range as, or above, MRT's 0.67.
- **Vol about 1.5–2 points higher than MRT's 4.92%.** Likely causes:
  - This universe holds long-duration TLT (about 12% of capital) and no euro government bonds or credit.
  - It has fewer, broader equity sleeves: three equity ETFs plus REITs, versus MRT's eight equity indices, which split equity risk into more pieces and so push more weight into bonds.
- **Capital in bonds is about 56% on average,** at the low end of the spec's 60–80% expectation. With 3 of 9 assets being bonds, each asset gets 1/9 of the risk, so bonds carry one third of the risk. Gold and commodities also have low correlation to equities and absorb capital.
- **2000–2008 looks better than MRT's 1995–2008 sample.** Ours begins in 2000, so it skips the late-1990s equity bubble (when a low-equity portfolio lagged) and includes the 2000–2007 bond, commodity and EM rally.
- **The out-of-sample Sharpe of 0.45 is well below the in-sample 1.21.** The OOS period contains the rise in inflation, the 2022 stock–bond sell-off and a decade of near-zero yields. The OOS results do not show that the paper's claim failed; its claim was about risk (lower vol and drawdown than 1/N), and that held. But the absolute return after 2008 is modest.

## Assessment

- Implementation checks:
  - Weights match an independent scipy solve on 9 checked dates.
  - No asset is held before it has 252 returns.
  - Turnover and costs are negligible.
  - There were no suspicious return jumps; the largest daily move was 3.5%, in March 2020.
- As a live candidate, it is a low-maintenance defensive balanced portfolio. It is not a return engine:
  - Out-of-sample Sharpe is about 0.45 and CAGR 4.4%, with a beta to SPY of 0.19.
  - Its drawdown protection in equity crises is excellent, but it is exposed to inflationary stock–bond sell-offs (2022).
  - It is reasonable as a low-risk sleeve or a benchmark for other risk-based strategies. The leverage that would make it compete with equities is outside this harness's ≤1× gross constraint, and Anderson et al. warn that leverage costs can erase the advantage.
