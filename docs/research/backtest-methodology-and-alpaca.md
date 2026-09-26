# Backtesting Methodology & Alpaca Live-Trading Realism — Research Notes

Research date: 2026-09-25. Scope: a daily-bar backtesting harness for liquid US ETFs whose results should track **live** trading on Alpaca (alpaca-py). Every claim is sourced; items that could not be verified are explicitly flagged **[UNVERIFIED]**. Where a number is my own recommendation rather than a sourced figure, it is flagged **[RECOMMENDATION]**.

Conventions: SR = Sharpe ratio. "Per-period" = in the native sampling frequency (daily), *not* annualized. ET = America/New_York.

---

## 0. Executive summary — what changes the harness design

1. **Auction orders (OPG/CLS) are probably not available on a standard Alpaca account.** Alpaca's Learn article states "`OPG` and `CLS` orders are only available to Elite Smart Router users"; the Elite page lists MOO/LOO/MOC/LOC as premium order types; the docs' TIF table marks OPG/CLS "Yes*" with "Please contact the sales team for any TIF marked with a *"; and an Alpaca staff member wrote in June 2026 "MOC orders are not generally supported in live trading unless one has chosen the elite smart router order handling." Elite needs a $30k deposit and charges **$0.0040/share (All-in)** or **$0.0025/share and lower plus pass-through fees (Cost Plus)**. Rules when OPG/CLS are available: OPG is accepted until **9:28 ET** and CLS until **3:50 ET** (rejected between those cutoffs and 7:00 pm; after 7:00 pm they queue for the next session). Both route to the primary exchange auction. **Fractional and notional orders are DAY-only and cannot use OPG/CLS.**
2. **The default (non-Elite) execution is a DAY market order.** One Alpaca doc says market orders are "protected on the primary exchange opening print", and orders received before 9:28 get the Nasdaq Official Opening Price for Nasdaq names. A staff member instead says pre-open market orders fill at the NBBO about 50–500 ms after the open. Model the open fill as the **official open plus a cost** and calibrate that cost from your own fills.
3. **Paper trading does not simulate auctions, fees, dividends, market impact or price improvement.** It fills OPG/CLS like ordinary market orders at the quote, and 10% of fills are randomly partial. Use paper to test the plumbing, not to measure costs.
4. **Fees in force today (Alpaca schedule revised 2026-09-17), with no commission on non-Elite accounts:**
   - SEC Section 31: **$20.60 per $1M of sells**, effective 2026-04-04. It was $0.00 from 2025-05-14 to 2026-04-03 and $27.80 before that.
   - FINRA TAF: **$0.000195/share on sells, capped at $9.79 per trade**, effective 2026-01-01. FINRA set it to **$0.00 for trades from 2026-10-01 to 2026-12-31**; whether Alpaca passes that through is **[UNVERIFIED]**.
   - CAT: **$0.000003/share on buys and sells.**
   - Alpaca sums each fee per account per day and rounds up to the cent.
5. **The PDT rule is gone.** SEC approved on 2026-04-14 and it took effect on 2026-06-04; Alpaca switched the same day. Alpaca has **no cash accounts**: every account is margin, or "limited margin" under $2,000 equity, so trading on unsettled T+1 proceeds is allowed and good-faith violations don't arise in practice.
6. **Data:**
   - Always use `feed=sip`. The Basic (free) plan can pull SIP history as long as the query `end` is at least 15 minutes old; history goes back to 2016.
   - A daily bar's timestamp is **midnight ET**, shown in UTC (e.g., `04:00Z` during daylight time).
   - The daily bar **open is the first valid regular trade, not the opening auction**, and the close is the last eligible trade. Official auction prints come from `GET /v2/stocks/auctions` (SIP only; not wrapped by alpaca-py 0.44.0).
   - Alpaca's adjusted series have had errors (dividend and split adjustment bugs reported on the forum). Store **raw** bars plus corporate actions and build total-return series yourself.
7. **Statistics to include:** PSR and MinTRL (2012), DSR with the effective number of trials (2014), PBO via CSCV (2017), a Harvey–Liu haircut or a t > 3 hurdle, a stationary-bootstrap CI (Politis–White block length), a Ledoit–Wolf test for Sharpe differences, and a rebalance-timing-luck sweep with a tranched benchmark. The formulas below are checked against the papers' own worked examples.
8. **Recommended per-side slippage, before fees [RECOMMENDATION]:**

   | Execution | Tier-1 ETFs | Tier-2 ETFs | Tier-3 ETFs |
   |---|---|---|---|
   | CLS/MOC on Elite, vs official close | 0 bps | 0 bps | 0 bps |
   | DAY market order at the open, vs official open | 2 bps | 4 bps | 6 bps |
   | Mid-morning market order, vs mid | 0.5 bp | 1 bp | 2 bps |

   Tiers are defined in §B8. Run a 2× cost stress. Use live `filled_avg_price` compared with official auction prints to calibrate.

---

# PART A — Backtesting methodology

## A1. Overfitting and multiple testing

### A1.1 Probabilistic Sharpe Ratio (PSR) and Minimum Track Record Length (MinTRL)
Source: Bailey, D.H. & López de Prado, M. (2012), "The Sharpe Ratio Efficient Frontier," *Journal of Risk* 15(2), Winter 2012/13. SSRN 1821643. PDF: https://www.davidhbailey.com/dhbpapers/sharpe-frontier.pdf

**Eq. (11):**

```
PSR(SR*) = Z[ (SR̂ − SR*) · sqrt(n − 1) / sqrt(1 − γ̂3·SR̂ + ((γ̂4 − 1)/4)·SR̂²) ]
```

- Z is the standard normal CDF. n is the number of return observations.
- γ̂3 is skewness. γ̂4 is **raw (non-excess) kurtosis**, E[(r−μ)⁴]/σ⁴, which equals 3 for a normal distribution.
- SR̂ and SR* are in the **original sampling frequency (non-annualized)**. The paper: "All calculations are done in the original frequency of the data, and there is no annualization."

**Eq. (13):**

```
MinTRL = n* = 1 + [1 − γ̂3·SR̂ + ((γ̂4 − 1)/4)·SR̂²] · (Z_α / (SR̂ − SR*))²
```

- MinTRL is a number of observations, not years.
- The paper cautions that the CLT should hold, so the moments need at least about 30 observations.

**Verified test vector** (paper's example: monthly data, n = 24, SR̂ = 0.458, i.e. 1.59 annualized):

| Inputs | PSR(0) in paper | My computation |
|---|---|---|
| γ3 = 0, γ4 = 3 | 0.982 | 0.9812 |
| γ3 = −2.448, γ4 = 10.164 | 0.913 | 0.9127 |

**2025 update.** López de Prado, Lipton & Zoonekynd, "How to Use the Sharpe Ratio" (SSRN 5520741, 2025; the code repo titles it "Sharpe Ratio Inference: A New Standard for Reporting and Decision-Making"). Code: https://github.com/zoonek/2025-sharpe-ratio (`functions.py`). The paper claims a closed-form SR sampling variance for returns that are both non-normal and serially correlated. Their implementation:
- Evaluates the SR variance **under the null (at SR0), divided by T** (not T−1).
- Adds an AR(1) autocorrelation ρ:

```
V[SR] = ( a − b·γ3·SR0 + c·((γ4−1)/4)·SR0² ) / T
a = 1 + 2ρ/(1−ρ);   b = 1 + ρ/(1−ρ) + ρ²/(1−ρ²);   c = 1 + 2ρ²/(1−ρ²)
PSR = Φ( (SR − SR0) / sqrt(V[SR]) )
```

Repo test vectors:
- PSR(SR = 0.036/0.079, SR0 = 0, T = 24, γ3 = −2.448, γ4 = 10.164) = 0.987.
- The same with SR0 = 0.1 gives 0.939.
- MinTRL(SR0 = 0, same moments, α = 0.05) = 13.029.

Recommendation: implement both. Use the 2012/2014 form to reproduce published numbers and the 2025 form, with ρ estimated from daily returns, as the stricter default.

**Lo (2002) autocorrelation adjustment.** Lo, A.W. (2002), "The Statistics of Sharpe Ratios," *Financial Analysts Journal* 58(4). When annualizing a daily SR with q periods under serial correlation ρ_k:

```
SR(q) = η(q)·SR,   η(q) = q / sqrt( q + 2·Σ_{k=1}^{q−1} (q−k)·ρ_k )
```

(Citation from my knowledge; the formula is standard. Verify against the paper if you use it for reporting.)

### A1.2 Deflated Sharpe Ratio (DSR)
Source: Bailey, D.H. & López de Prado, M. (2014), "The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality," *Journal of Portfolio Management* 40(5): 94–107. SSRN 2460551. https://jpm.pm-research.com/content/40/5/94 ; PDF: https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf

**Eq. (1)** gives the expected maximum SR over N independent trials whose SR estimates have mean E[{SR̂n}] and variance V[{SR̂n}]:

```
E[max{SR̂n}] ≈ E[{SR̂n}] + sqrt(V[{SR̂n}]) · ( (1−γ)·Z⁻¹[1 − 1/N] + γ·Z⁻¹[1 − 1/(N·e)] )
```

γ ≈ 0.5772156649 is the Euler–Mascheroni constant, e is Euler's number, and Z⁻¹ is the inverse standard normal CDF.

**Eq. (2)** defines DSR as a PSR whose benchmark SR̂0 is that expected maximum under the null (E[{SR̂n}] = 0):

```
SR̂0  = sqrt(V[{SR̂n}]) · ( (1−γ)·Z⁻¹[1 − 1/N] + γ·Z⁻¹[1 − 1/(N·e)] )
DSR  = PSR(SR̂0) = Z[ (SR̂ − SR̂0)·sqrt(T − 1) / sqrt(1 − γ̂3·SR̂ + ((γ̂4 − 1)/4)·SR̂²) ]
```

- SR̂, γ̂3, γ̂4 and T belong to the selected strategy.
- V[{SR̂n}] is the variance of the trials' SRs, in the same (non-annualized) frequency.
- N is the number of **independent** trials.

**Verified test vectors** from the paper's example: annualized SR 2.5 on 5 years of daily data, so T = 1250 and SR̂ = 2.5/√250 = 0.1581; V = 0.5/250; γ3 = −3; γ4 = 10.

| Case | SR̂0 (per period) | SR̂0 (annualized) | DSR |
|---|---|---|---|
| N = 100 | 0.1132 | 1.79 | **0.9004** |
| N = 46 | — | — | 0.9505 (paper: "0.9505") |
| Normal returns (γ3 = 0, γ4 = 3), N = 88 | — | — | 0.9505 (paper: DSR ≈ 0.95 after N = 88) |

The DSR column is my recomputation using the formula above.

**Effective number of trials** (Appendix A.3). With M correlated trials and average pairwise correlation ρ̂, the implied number of independent trials is **N̂ = ρ̂ + (1 − ρ̂)·M** (Eq. 9). The 2025 paper and its code instead cluster the trial return series and use the **number of clusters** as N (see `number_of_clusters` / `effective_rank` in the repo).

**Practical rule.** The harness must record **every** configuration it evaluates, including abandoned ones, together with its daily return series. Without that, DSR and PBO cannot be computed honestly.

**Stopping rule** (paper, "When should we stop testing?"): the 1/e law. Sample about 37% of the theoretically justified configurations at random, then keep drawing until one beats all previous ones.

### A1.3 Probability of Backtest Overfitting (PBO) via CSCV
Source: Bailey, D.H., Borwein, J., López de Prado, M. & Zhu, Q.J. (2017), "The Probability of Backtest Overfitting," *Journal of Computational Finance* 20(4): 39–69. SSRN 2326253. PDF: https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf

Algorithm 2.3 (CSCV), summarized from the paper:

1. Build M, a T×N matrix of per-period performance, one column per trial configuration, with rows synchronized across trials.
2. Split the rows into an **even** number S of contiguous, equal-size blocks.
3. Form all C(S, S/2) combinations of S/2 blocks. For S = 16 that is C(16,8) = **12,870** (the paper prints "12,780", a typo).
4. For each combination c:
   - The training set J is the chosen blocks, in their original order. The test set J̄ is the complement (T/2 rows).
   - Compute the performance statistic (e.g., SR) for every trial on J and on J̄.
   - n* is the best trial in-sample.
   - ω̄c = rank_OOS(n*)/(N+1), where a higher rank is better.
   - The logit is λc = ln(ω̄c / (1 − ω̄c)).
5. **PBO = φ = ∫_{−∞}^{0} f(λ)dλ**, the fraction of combinations with λc ≤ 0, i.e. where the IS winner lands at or below the OOS median.

The paper suggests rejecting models with PBO > 0.05. Related diagnostics from the same paper:
- Performance degradation: regress OOS performance on IS performance of the selected trials.
- Probability of loss OOS.
- Stochastic dominance of the selection procedure over random selection.

### A1.4 Harvey, Liu & Zhu (2016) — raise the t-hurdle
Source: Harvey, C.R., Liu, Y. & Zhu, H. (2016), "…and the Cross-Section of Expected Returns," *Review of Financial Studies* 29(1): 5–68. https://academic.oup.com/rfs/article-abstract/29/1/5/1843824 ; NBER w20592: https://www.nber.org/papers/w20592

- Abstract: "a newly discovered factor needs to clear a much higher hurdle, with a t-ratio greater than 3.0."
- The paper documents at least 316 factors tested and concludes "most claimed research findings in financial economics are likely false."
- Harness use: t-stat of mean excess return ≈ SR_per_period·√T. Require **t > 3** for a novel signal. With daily data and T = 2,500 (about 10 years), that implies an annualized SR of about 3/√2500·√252 ≈ **0.95**.

### A1.5 Harvey & Liu (2015) "Backtesting" — Sharpe haircuts
Source: Harvey, C.R. & Liu, Y. (2015), "Backtesting," *Journal of Portfolio Management* 42(1): 13–28. PDF: https://people.duke.edu/~charvey/Research/Published_Papers/P120_Backtesting.PDF ; code: https://people.duke.edu/~charvey/backtesting/

Method:
1. Convert SR to a t-ratio (t = SR·√T, per period).
2. Get the single-test p-value p_S.
3. Adjust it for N tests to get p_M.
4. Invert p_M back to a "haircut" SR_H.

Adjustments:
- **Independent tests:** p_M = 1 − (1 − p_S)^N (their Eq. 4).
- **Bonferroni:** p_M = min(N·p_S, 1).
- **Holm:** step-down.
- **BHY (Benjamini–Hochberg–Yekutieli):** FDR step-up, less strict.

The paper's worked example:
- T = 240 monthly observations and an annualized SR of 0.75 give p_S = 0.0008.
- With N = 200, p_M = 0.15, which implies an adjusted SR of 0.32, a haircut of about 60%.

Key finding: the haircut is **nonlinear**. It is "almost always more than and sometimes much larger than 50% when the annualized Sharpe ratio is less than 0.4", and "when the Sharpe ratio is greater than 1.0, the haircut is at most 25%." In their words, the 50% rule of thumb is "too lenient for relatively small Sharpe ratios (< 0.4) and too harsh for large ones (> 1.0)."

### A1.6 Reference implementation (verified against the test vectors above)
```python
import math
import numpy as np
from scipy.stats import norm, skew, kurtosis

EULER_GAMMA = 0.5772156649015329

def psr(sr, sr_star, T, g3, g4):
    """Bailey & Lopez de Prado (2012) Eq. 11. sr, sr_star per-period; g4 = RAW kurtosis."""
    return norm.cdf((sr - sr_star) * math.sqrt(T - 1) /
                    math.sqrt(1 - g3 * sr + (g4 - 1) / 4 * sr ** 2))

def min_trl(sr, sr_star, g3, g4, alpha=0.05):
    """Eq. 13, in number of observations."""
    return 1 + (1 - g3 * sr + (g4 - 1) / 4 * sr ** 2) * (norm.ppf(1 - alpha) / (sr - sr_star)) ** 2

def expected_max_sr(n_trials, var_trial_srs):
    """Bailey & Lopez de Prado (2014) Eq. 1 under H0 (mean 0)."""
    return math.sqrt(var_trial_srs) * ((1 - EULER_GAMMA) * norm.ppf(1 - 1 / n_trials)
                                       + EULER_GAMMA * norm.ppf(1 - 1 / (n_trials * math.e)))

def dsr(returns, trial_srs, n_eff=None):
    """returns: per-period excess returns of the selected strategy.
    trial_srs: per-period SRs of ALL trials tried (same frequency)."""
    r = np.asarray(returns)
    sr = r.mean() / r.std(ddof=1)
    n = n_eff if n_eff is not None else len(trial_srs)
    sr0 = expected_max_sr(n, np.var(trial_srs, ddof=1))
    return psr(sr, sr0, len(r), skew(r), kurtosis(r, fisher=False))

def n_eff_from_avg_corr(m_trials, avg_corr):
    """Bailey & Lopez de Prado (2014) Appendix A.3, Eq. 9."""
    return avg_corr + (1 - avg_corr) * m_trials

# Test vectors: psr(0.458, 0, 24, -2.448, 10.164) ~= 0.913;
# SR=2.5/sqrt(250), V=0.5/250, N=100, T=1250, g3=-3, g4=10 -> DSR ~= 0.9004
```

## A2. Post-publication decay
Source: McLean, R.D. & Pontiff, J. (2016), "Does Academic Research Destroy Stock Return Predictability?" *Journal of Finance* 71(1): 5–32. https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12365 ; SSRN 2156623.

- The study covers **97** cross-sectional predictors.
- Portfolio returns are **26% lower out-of-sample** (after the original sample, before publication) and **58% lower post-publication**.
- The authors attribute about **32% (58% − 26%)** to publication-informed trading. They describe the 26% as an upper bound on data-mining effects.

Harness use: when projecting live expectations for a published effect (momentum, trend, carry, low-vol and so on), haircut the backtested excess return by roughly **half or more** **[RECOMMENDATION, informed by M&P]**. Report both in-sample and post-publication-period results where the publication date is known.

## A3. Bootstrap confidence intervals with autocorrelated returns

### A3.1 Stationary bootstrap
Source: Politis, D.N. & Romano, J.P. (1994), "The Stationary Bootstrap," *JASA* 89(428): 1303–1313. https://www.tandfonline.com/doi/abs/10.1080/01621459.1994.10476870

- Resamples blocks whose lengths are **geometric with mean b = 1/p**, wrapping around the end of the series.
- Unlike fixed-length block methods, the resampled series is stationary.

### A3.2 Block-length selection
- **Politis & White (2004)**, "Automatic Block-Length Selection for the Dependent Bootstrap," *Econometric Reviews* 23(1): 53–70, with the **correction by Patton, Politis & White (2009)**, *Econometric Reviews* 28(4): 372–375. Links: https://public.econ.duke.edu/~ap172/Politis_White_2004.pdf ; https://public.econ.duke.edu/~ap172/Patton_Politis_White_2009.pdf
  - Implemented in Python as `arch.bootstrap.optimal_block_length(x)`, which returns columns `b_sb` (stationary) and `b_cb` (circular). https://arch.readthedocs.io/en/latest/bootstrap/generated/arch.bootstrap.optimal_block_length.html
- **Hall, Horowitz & Jing (1995)**, *Biometrika* 82(3): 561–574: the optimal block length grows as **n^{1/3}** for variance/bias estimation, **n^{1/4}** for a one-sided distribution function, and **n^{1/5}** for a two-sided one. https://academic.oup.com/biomet/article-abstract/82/3/561/260651
  - For T = 2,520 daily returns: n^{1/3} ≈ 13.6 and n^{1/4} ≈ 7.1.
- **[RECOMMENDATION]**
  - For Sharpe CIs, use the Politis–White `b_sb` computed on **squared** or absolute returns as well as raw returns, and take the larger, because volatility clustering is the dominant dependence in daily ETF returns.
  - For **max drawdown**, which is path-dependent and sensitive to regime persistence, report a sensitivity table with mean block lengths of 5, 10, 21 and 63 days.
  - Use at least 5,000 resamples.

### A3.3 Ledoit & Wolf (2008) — testing a difference of two Sharpe ratios
Source: Ledoit, O. & Wolf, M. (2008), "Robust performance hypothesis testing with the Sharpe ratio," *Journal of Empirical Finance* 15(5): 850–859. PDF: http://www.ledoit.net/jef_2008pdf.pdf

- Jobson–Korkie/Memmel tests assume i.i.d. normal returns and are invalid with fat tails or serial dependence.
- Their first alternative is **HAC inference**: the delta method on (μi, μn, E[ri²], E[rn²]), with Ψ estimated by the prewhitened Quadratic-Spectral kernel (Andrews & Monahan). The paper warns HAC is liberal in small samples.
- **Recommended method:** a studentized **circular block bootstrap** confidence interval for Δ = SRi − SRn. They "recommend to always use the bootstrap method for time series data."
- **Block size by calibration (Algorithm 3.1):**
  1. Fit a semi-parametric model: VAR for monthly data, bivariate GARCH suggested for daily.
  2. Simulate K pseudo-series.
  3. For each candidate b, compute the empirical coverage ĝ(b).
  4. Pick the b whose coverage is closest to 1−α.
  - Grid {1, 2, 4, 6, 8, 10} for T = 120. K = 5000 is ample; K = 1000 is the minimum.
  - Their empirical picks were b = 4 (mutual funds) and b = 6 (hedge funds).
- **Bootstrap p-value (Eq. 9):** PV = (#{d̃*,m ≥ d} + 1)/(M + 1), with d = |Δ̂|/s(Δ̂). Their simulations used M = 499.
- Harness use: strategy A vs strategy B, or strategy vs benchmark (e.g., SPY buy-and-hold). Pair the daily excess returns and use the studentized circular block bootstrap. Ready-made implementations exist in R (`PeerPerformance`) and Python (e.g., https://github.com/majkee15/RobustSharpeRatioHAC for HAC; that repo was not audited).

```python
import numpy as np
from arch.bootstrap import StationaryBootstrap, optimal_block_length

def sharpe_ci(daily_excess, reps=5000, alpha=0.05, ann=252, seed=0):
    x = np.asarray(daily_excess)
    b = max(optimal_block_length(x)["b_sb"].iloc[0],
            optimal_block_length(x ** 2)["b_sb"].iloc[0])
    bs = StationaryBootstrap(b, x, seed=seed)
    stat = lambda y: np.array([y.mean() / y.std(ddof=1) * np.sqrt(ann)])
    ci = bs.conf_int(stat, reps=reps, method="percentile", size=1 - alpha)
    return b, ci.ravel()
```

## A4. Rebalance timing luck (RTL)
Sources:
- Hoffstein, C., Sibears, D.J. & Faber, N. (2019), "Rebalance Timing Luck: The Difference between Hired and Fired," *Journal of Beta Investment Strategies / Journal of Index Investing* 10(1): 27. https://jii.pm-research.com/content/10/1/27.abstract (full text not accessed).
- Hoffstein, C., Faber, N. & Braun, S. (2020), "Rebalance Timing Luck: The (Dumb) Luck of Smart Beta," SSRN 3673910. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3673910
- Newfound overview: https://www.thinknewfound.com/rebalance-timing-luck ; https://blog.thinknewfound.com/2019/07/timing-luck-and-systematic-value/

**Definition** (Newfound): "the standard deviation in returns between identically managed investment portfolios that are rebalanced on different dates (sub-indexes)."

**Measurement** (2020 paper):
1. Build one sub-index for each possible rebalance schedule.
2. The **RTL-neutral benchmark** holds all sub-indexes in equal weight ("overlapping portfolios" / "staggered rebalancing" / "tranching").
3. **RTL = annualized volatility of (sub-index return − tranche benchmark return).**

**Ex-ante estimate:** the 2020 paper prints Eq. (1) as **L = (T·f/2)·S**. Newfound's blog defines T as turnover, F as "how many times per year the strategy rebalances", and S as "the volatility of a long/short portfolio capturing the difference between what the strategy is currently invested in versus what it could be invested in".
- **[UNVERIFIED interpretation]:** For the formula to be consistent with the stated direction (more frequent rebalancing means less RTL), f must be the *interval between rebalances in years*, which would make L = T/(2F)·S. I could not access the 2019 paper's full text to confirm. Treat the formula as a rough guide and measure RTL empirically.

**Magnitudes** (2020 paper):
- Factor indices "often exceeding 100 basis points annualized."
- Replicated smart-beta indices: up to **200 bps/yr** in annualized return, and "calendar year return differentials above 40%" for an S&P Enhanced Value replica.
- Option collars: more than 400 bps tracking error (Newfound).

**Mitigation:** equal-weight tranches. Newfound says timing luck falls roughly with the number of tranches ("1/N"); treat this as a rule of thumb.

**Harness test [RECOMMENDATION]:**
1. For a strategy rebalanced every k trading days (monthly ≈ 21), run k variants with offsets 0…k−1, or every trading day of the month.
2. Report the distribution of CAGR, SR and max drawdown across offsets (min, median, max, std) and each variant's tracking error to the tranche-average portfolio.
3. Select parameters on the **tranche-average** result, never on the best offset.
4. For live trading, consider running n tranches (e.g., 4 weekly sub-portfolios each rebalanced monthly). Fractional DAY market orders make small tranche trades cheap on Alpaca.

## A5. Common pitfalls (and harness rules)

General references:
- Luo, Y. et al. (2014), "Seven Sins of Quantitative Investing," Deutsche Bank Markets Research: survivorship bias, look-ahead bias, storytelling, data snooping, turnover/transaction costs, outliers, and asymmetric patterns/shorting costs. https://hudsonthames.org/wp-content/uploads/2022/01/DB-201409-Seven_Sins_of_Quantitative_Investing.pdf
- Palomar, *Portfolio Optimization* (2025), ch. 8, "Seven sins." https://bookdown.org/palomar/portfoliooptimizationbook/8.2-seven-sins.html

1. **Look-ahead bias / trading at the signal bar's close.** A signal computed from bar t's close cannot be filled at that same close unless the order was placed before the close with information available at that time. On Alpaca:
   - CLS orders must be in by **3:50 pm ET**, and only on Elite; see B1.
   - "Signal at close t, fill at close t" is therefore look-ahead.
   - Honest alternatives:
     - (a) Signal at close t, fill at the **open of t+1**: pre-open DAY market order, or OPG on Elite by 9:28.
     - (b) Signal at close t−1, fill by MOC at close t, which adds a day of lag.
     - (c) Signal from data as of about 3:45 pm on day t, fill by MOC or a ~3:55 market order at close t. This needs intraday (minute) data, which Alpaca provides since 2016.
   - The harness should carry explicit `signal_time` and `fill_time` and assert `data_time ≤ signal_time < fill_time`.
2. **Survivorship bias.**
   - Brown, Goetzmann, Ibbotson & Ross (1992), "Survivorship Bias in Performance Studies," *RFS* 5(4): 553–580. https://academic.oup.com/rfs/article-abstract/5/4/553/1590264
   - Shumway (1997), "The Delisting Bias in CRSP Data," *JF* 52: 327–340. https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1540-6261.1997.tb03818.x
   - A stock backtest on today's index constituents drops delisted and bankrupt names and bakes in hindsight about what became large, which biases returns upward.
   - A fixed, pre-specified universe of large, liquid, still-trading asset-class ETFs (SPY, TLT, GLD and so on) avoids constituent survivorship, because the ETF itself is the tradable unit and its underlying index handles constituent changes.
   - Residual risks:
     - ETF *selection* hindsight (choosing asset classes known to have done well).
     - Inception dates (e.g., XLRE launched in 2015 and XLC in 2018, **[from memory; verify with the asset's first bar]**).
     - ETF closures. To mitigate, define the universe by rules fixed in advance and use a start date on which all members trade.
3. **Adjusted vs unadjusted prices.**
   - Use **raw** prices for order sizing (share quantities), limit prices, and anything compared with live quotes.
   - Use **total-return** series (split- and dividend-adjusted) for return computation and signals, *or* raw prices plus explicit cash dividends.
   - Yahoo's adjusted close follows CRSP-style multipliers: split multiplier 1/ratio, dividend multiplier 1 − div/close (https://help.yahoo.com/kb/SLN28256.html). Multiplicative adjustment preserves returns but **changes price levels over time**, so any rule that uses an absolute price level on adjusted data (e.g., "price > $X") is contaminated.
   - Adjusted histories are recomputed as of the query date. Re-downloading can change old values, so snapshot the data with a version or date stamp.
4. **Dividend handling.** Bond and bill ETFs (TLT, IEF, BIL, SHV) earn most of their total return from distributions, so ignoring them severely understates returns. For live parity:
   - Credit cash on the pay date (entitlement is set by the ex-date).
   - Model the ex-date price drop through the raw series.
   - Decide whether to reinvest at the next rebalance.
   - Alpaca **paper does not pay dividends** (docs), so paper equity will drift from a total-return backtest.
5. **Stale or erroneous data (Yahoo/yfinance).**
   - yfinance changed the `auto_adjust` default to `True` in the 0.2.x line (0.2.54). `Adj Close` disappeared and OHLC became adjusted by default. https://github.com/ranaroussi/yfinance/issues/2283
   - Documented Yahoo problems include missing dividends and split/dividend mis-adjustment, e.g., quantmod issue "Yahoo Finance OHLC data are split adjusted, but its dividends data are not": https://github.com/joshuaulrich/quantmod/issues/253
   - Rules:
     - Always pin `auto_adjust` explicitly.
     - Cross-validate two sources (e.g., Alpaca SIP raw plus Alpaca corporate actions against a second vendor).
     - Flag daily returns above 5σ, zero-volume days, and gaps against the trading calendar.
6. **Feed choice.** IEX is a single venue (about 2.5% of volume per Alpaca docs). IEX daily OHLCV differs from consolidated SIP bars; Alpaca's FAQ shows AAPL 2023-09-29 with an IEX close of 171.29 vs a SIP close of 171.21. Use **SIP** for backtests.
7. **Open and close definitions.** Alpaca's daily open is the first valid trade and can differ from the primary-exchange opening auction (B4). Backtesting "fill at open" against first-trade prices mismeasures auction fills. Use the auctions endpoint for official prints.
8. **Calendar.** Use exchange calendars (Alpaca `/v2/calendar`, 1970–2029) to handle holidays and early closes (e.g., a 13:00 close). Never assume 252 fixed days or weekday-only schedules.

---

# PART B — Live-trading realism on Alpaca

## B1. Order types and time in force (docs.alpaca.markets)
Primary sources:
- https://docs.alpaca.markets/docs/orders-at-alpaca (markdown at https://docs.alpaca.markets/us/docs/orders-at-alpaca.md, page `updatedAt: 2026-08-10`)
- https://docs.alpaca.markets/us/reference/postorder
- alpaca-py `TimeInForce` docstring (identical text)

**TIF definitions (verbatim essentials):**
- `day`: RTH only (9:30–16:00 ET) unless `extended_hours=true`. "If unfilled after the closing auction, it is automatically canceled. If submitted after the close, it is queued and submitted the following trading day."
- `opg`: "…submit 'market on open' (MOO) and 'limit on open' (LOO) orders. This order is eligible to execute only in the market opening auction. Any unfilled orders after the open will be cancelled. **OPG orders submitted after 9:28am but before 7:00pm ET will be rejected. OPG orders submitted after 7:00pm will be queued and routed to the following day's opening auction.** On open/on close orders are routed to the primary exchange. Such orders do not necessarily execute exactly at 9:30am / 4:00pm ET but execute per the exchange's auction rules."
- `cls`: "…'market on close' (MOC) and 'limit on close' (LOC)… eligible to execute only in the market closing auction… **CLS orders submitted after 3:50pm but before 7:00pm ET will be rejected. CLS orders submitted after 7:00pm will be queued and routed to the following day's closing auction.**"
- `ioc`: market makers often fill IOC only as principal, so an IOC can be cancelled entirely. `fok`: all-or-nothing.
- `gtc`: auto-cancelled 90 days after creation, at 4:15 pm ET on the `expires_at` date.

**Supported order type × TIF (docs tables):**

| TIF | Whole-share market / limit | Whole-share stop / stop-limit | Fractional (any type) | Extended hours |
|---|---|---|---|---|
| DAY | Yes | Yes | **Yes (DAY only)** | limit only |
| GTC | Yes | Yes | No | limit only |
| IOC / FOK | Yes\* | No | No | No |
| **OPG / CLS** | **Yes\*** | No | **No** | No |

\* "Please contact the sales team for any TIF marked with a *".

**Fractional and notional orders:**
- `notional` is "dollar amount to trade. Cannot work with `qty`. Can only work for market order types and day for time in force."
- The fractional `qty` table allows market, limit, stop and stop-limit, all DAY. The fractional-trading page separately says fractional transactions "can only be bought or sold with market orders during normal market hours". The two pages are inconsistent; assume **market + DAY** is the only safe combination.
- No fractional short sales. Up to 9 decimals. Notional orders cannot be replaced (PATCH); cancel and resubmit.
- Fractional *execution*: per Alpaca staff (Mar 2025), fractional portions are "always filled/executed directly by Alpaca". Orders under 1 share fill at the current NBBO quote. For orders over 1 share, the whole shares go to execution partners and the fraction is matched at the same price. https://forum.alpaca.markets/t/fractional-order-execution/16562
- Sources: https://docs.alpaca.markets/docs/fractional-trading ; https://docs.alpaca.markets/us/reference/postorder

**Auction participation:**
- The docs say OPG/CLS route to the primary exchange auction.
- Live evidence (Jul 2024): an OPG order filled at the **NYSE (primary) auction price**, while the data-vendor "open" was an earlier first print on Nasdaq. Staff: "An Alpaca OPG order will fill at the opening auction price on the primary exchange where the security is listed." https://forum.alpaca.markets/t/opg-orders-not-filled-at-open-price-live-trading/14672

**Availability (important, conflicting sources):**
- Alpaca Learn: "Please note that `OPG` and `CLS` orders are only available to Elite Smart Router users." https://alpaca.markets/learn/13-order-types-you-should-know-about
- Alpaca Elite page: MOO/LOO and MOC/LOC listed among "Advanced Order Types" that come with the Elite Smart Router; "Deposit $30,000 to unlock" the Elite Smart Router. https://alpaca.markets/elite
- Staff, 2026-06-24: "MOC orders are not generally supported in live trading unless one has chosen the elite smart router order handling." https://forum.alpaca.markets/t/paper-moc-orders-partially-fill-remainder-expires-same-setup-on-live-works/19155
- Conclusion: **assume OPG/CLS are unavailable on a standard account.** Before relying on them, verify with a 1-share live order and check the status and reject reason. Build the executor to fall back to DAY market orders.
- One third-party report says auction orders on a non-Elite paper account were *accepted but never filled* (https://github.com/robertsben333-cmyk/claude_research/pull/7). This is anecdotal.

**Elite costs** (Brokerage Fee Schedule, revised 2026-09-17):
- Elite Smart Router trades pay commissions of **All-in $0.0040/share**, or **Cost-Plus $0.0025/share tiered down to $0.0005** plus pass-through exchange fees and rebates and regulatory fees.
- The DMA gateway "only supports market and limit orders and TIF = day. If you wish to use MOO/MOC, gtc, or stop orders, you cannot specify advanced_instructions." https://docs.alpaca.markets/docs/alpaca-elite-smart-router

**Non-auction orders at the open** (docs, "Order Handling Standards at Alpaca Securities LLC"):
- "Market and limit order orders are protected on the primary exchange opening print. We do not necessarily route retail orders to the exchange, but will route orders to market makers who will route orders on your behalf to the primary market opening auction. This protection is subject to exchange time cutoff… if you enter a market order between 9:28:01 and 9:29:59 on a Nasdaq security you would not receive the Nasdaq Official Opening Price (NOOP)… Any market orders received before 9:28 will be filled at the Nasdaq Official Opening Price."
- Contrasting staff statement (Mar 2024): pre-open market orders "are executed at market open at the 'open' price", but "The only thing driving the order fill price is the NBBO quote at the time the order filled (typically 50ms-500ms after open)". https://forum.alpaca.markets/t/frustration-with-the-execution-of-pre-market-orders/13787
- **Harness implication:** model a pre-open DAY market order as filled at the official open plus a cost (B8), and calibrate from live fills.

**Other order rules:**
- **Buying-power check** during the core session uses the far side of the NBBO. Open buy orders reduce available buying power until they fill or are cancelled.
- **Wash-trade protection:** Alpaca "reject[s] any order where there is an existing open order having the opposite side" (staff; message `potential wash trade detected. use complex orders`). https://forum.alpaca.markets/t/apierror-potential-wash-trade-detected-use-complex-orders/13441 ; https://forum.alpaca.markets/t/wash-trade-rules/18200
- **Sub-penny rule:** limit prices ≥ $1.00 allow at most 2 decimals.
- **Extended hours:** limit orders with DAY or GTC only. Sessions are overnight 8pm–4am, pre-market 4–9:30am and after-hours 4–8pm.
- **Early-close CLS cutoff:** not documented by Alpaca **[UNVERIFIED]**. Exchanges typically move MOC cutoffs earlier on half days; check before trading those days.

## B2. Fees

**Commissions:** $0 for US stocks and ETFs on the standard (non-Elite) Trading API. "Alpaca Securities does not charge commissions, except as described below", which covers index options, the Elite Smart Router, and "order flow determined to be non-retail in nature." Source: Brokerage Fee Schedule (revised Sept 17, 2026), https://files.alpaca.markets/disclosures/library/BrokFeeSched.pdf

**Pass-through regulatory fees** (same schedule):

| Fee | Side | Rate (schedule dated 2026-09-17) |
|---|---|---|
| SEC Transaction Fee (Section 31) | Sells only | $0.0000206 × trade value (= **$20.60 per $1M**) |
| FINRA Trading Activity Fee (TAF) | Sells only | **$0.000195/share, max $9.79 per trade** ("capped at 50,205 shares or more") |
| FINRA CAT fee | Buys **and** sells | **$0.000003 per executed equivalent share** (NMS equities: 1 share = 1 equivalent share) |

How Alpaca charges them: "Fees are calculated on the exact executed quantity, including fractional shares… Each fee type is aggregated separately at the daily, per-account level. After aggregation, each fee total is rounded up to the nearest cent ($0.01)."

Regulatory fee history for time-varying backtests:
- **SEC Section 31**, official sources:
  - $27.80/M through 2025-05-13 (in effect from 2024-05-22; see https://cdn.cboe.com/resources/fee_schedule/2024/Regulatory-Transaction-Fee-Adjustment-per-SEC-Section-31-Rate-Change-Effective-May-22-2024.pdf).
  - **$0.00/M from 2025-05-14** (SEC advisory https://www.sec.gov/rules-regulations/fee-rate-advisories/2025-2).
  - **$20.60/M from 2026-04-04**, "until 60 calendar days after legislation is enacted that sets the amount of the Commission's fiscal year 2027 appropriation" (https://www.sec.gov/rules-regulations/fee-rate-advisories/2026-2 ; FINRA Information Notice 2026-03-17).
  - Earlier rates, compiled by a third party (https://traderstatus.com/traders/trader-info/sec-fee-rates/), should be verified against SEC advisories before use: $21.80 (2016-02-16), $23.10 (2017-07-04), $13.00 (2018-05-22), $20.70 (2019-04-16), $22.10 (2020-02-18), $5.10 (2021-02-25), $22.90 (2022-05-14), $8.00 (2023-02-27). The third-party table's "2020-10-01 → $20.70" row looks inconsistent **[UNVERIFIED]**.
- **FINRA TAF** (covered equity sales):
  - $0.000166/share, max $8.30, in effect Jan 1, 2024 through 2025 (FINRA By-Laws Schedule A §1 footnote; SR-FINRA-2024-019).
  - **$0.000195, max $9.79, effective Jan 1, 2026** (SR-FINRA-2024-019 Exhibit 5C; https://www.finra.org/sites/default/files/2024-11/sr-finra-2024-019.pdf).
  - The next scheduled step ($0.000232, max $11.61) was **postponed**: SR-FINRA-2026-020 "maintains TAF rates at their current levels through December 31, 2028."
  - **TAF fee holiday:** SR-FINRA-2026-021 (filed 2026-09-15, effective on filing) sets TAF rates to **$0.00 for transactions from Oct 1 to Dec 31, 2026**, resuming Jan 1, 2027. https://www.sec.gov/files/rules/sro/finra/2026/34-106409.pdf (Federal Register 91 FR 60435). Whether and how Alpaca passes this through is **[UNVERIFIED]**; its 2026-09-17 schedule still lists $0.000195.
- **Other pass-throughs:**
  - ADR fees of $0.01–$0.05/share (not relevant to ETFs).
  - HTB borrow and locate fees for shorts; easy-to-borrow shorts have no fee for Trading API users.
  - Margin interest charged on settled debit balances / 360 per day. The fee schedule says **6.25%** default and 4.75% for Elite 100k; the margin docs page still says 6.50% non-elite and 5.00% elite. The schedule is newer and should win.
- **Paper trading does not charge regulatory fees** (paper docs), so model them in the harness.

```python
import math
def alpaca_fees_for_day(fills, sec_rate_per_dollar=20.60e-6, taf_per_share=0.000195,
                        taf_cap=9.79, cat_per_share=0.000003):
    """fills: list of dicts {side: 'buy'|'sell', qty: float, price: float}; one account, one day.
    Mirrors Alpaca: per-fee daily aggregation, then round UP to the cent."""
    sec = sum(f["qty"] * f["price"] for f in fills if f["side"] == "sell") * sec_rate_per_dollar
    taf = sum(min(f["qty"] * taf_per_share, taf_cap) for f in fills if f["side"] == "sell")
    cat = sum(f["qty"] for f in fills) * cat_per_share
    up = lambda x: math.ceil(round(x * 100, 9)) / 100 if x > 0 else 0.0
    return {"sec": up(sec), "taf": up(taf), "cat": up(cat)}
```

Note: Alpaca's schedule says the TAF cap is "per trade". Whether "trade" means per order or per execution for a multi-fill order is **[UNVERIFIED]**.

## B3. PDT, margin vs cash, settlement

- **PDT rule retired.**
  - SEC approved the FINRA Rule 4210 amendments on **2026-04-14**, effective **2026-06-04**, with an optional phase-in ending **2027-10-20** (FINRA Regulatory Notice 26-10, https://www.finra.org/rules-guidance/notices/26-10; WilmerHale alert https://www.wilmerhale.com/en/insights/client-alerts/20260423-sec-approves-amendments-to-finra-rule-4210-replacing-day-trading-margin-requirements-with-a-modernized-intraday-margin-standard).
  - Alpaca implemented its Intraday Margin Framework on **June 4, 2026**: "no more PDT designation or trade count limits", and the "minimum equity requirement for 4x intraday buying power has been lowered from $25,000 to $2,000."
  - Deprecated API fields (`pattern_day_trader`, `daytrade_count`, `last_daytrade_count`, `last_daytrading_buying_power`, `daytrading_buying_power`) were to be "completely removed from the API by July 6, 2026". Use `buying_power` instead. https://alpaca.markets/blog/finra-retires-the-pdt-rule-introducing-alpacas-new-intraday-margin-framework/
  - alpaca-py 0.44.0 still defines these fields as Optional.
- **Intraday margin mechanics** (Alpaca docs, https://docs.alpaca.markets/us/docs/the-intraday-margin-rule):
  - IML is the Intraday Margin Level; an IMD (deficit) triggers a margin call due within **two business days**.
  - An IMD unmet by the close of the 5th business day brings a **90-day freeze** on new debits and shorts.
  - De minimis: calls are generally not triggered if the unmet deficit is below **$1,000 or 5% of equity**, whichever is lower.
- **Margin basics** (https://docs.alpaca.markets/us/docs/margin-and-short-selling):
  - Margin or shorting requires **$2,000 or more** in equity. Below $2,000 the account is limited to **1x** buying power.
  - Reg T gives 2x overnight and up to 4x intraday.
  - Maintenance for longs above $6 is 30%; 2x leveraged ETFs need 50% and 3x need 75%.
  - `max_margin_multiplier` can be set to "1", "2" or "4" via account configuration, and `no_shorting=true` makes the account long-only. **[RECOMMENDATION]** Set `max_margin_multiplier="1"` and `no_shorting=true` for an unlevered long-only ETF strategy, so the account behaves like cash but settles immediately.
- **Cash accounts and good-faith violations:** "No, we do not offer cash accounts. All accounts are set up as margin accounts." Accounts under $2,000 are "limited margin accounts" that can "trade on unsettled funds" (https://alpaca.markets/support/alpaca-cash-accounts). Unsettled funds cannot be withdrawn or used for crypto (https://alpaca.markets/learn/understanding-unsettled-funds). GFV and free-riding rules therefore do not constrain sell-then-buy rebalancing on Alpaca.
- **Settlement:** T+1 for US stocks and ETFs since May 2024 (Alpaca Learn, same page).

## B4. Market data (alpaca-py `StockHistoricalDataClient`)

Sources: https://docs.alpaca.markets/us/docs/about-market-data-api (updated 2026-07-16); https://docs.alpaca.markets/us/reference/stockbars ; https://docs.alpaca.markets/us/docs/market-data-faq (updated 2026-09-21); https://docs.alpaca.markets/us/docs/historical-stock-data-1

- **Plans (Trading API):**

  | | Basic | Algo Trader Plus |
  |---|---|---|
  | Price | Free | $99/month |
  | Real-time feed | IEX | All US exchanges |
  | Historical data | Since 2016 | Since 2016 |
  | Historical limitation | Excludes the latest 15 minutes | No restriction |
  | Historical API calls | 200/min | 10,000/min |

  FAQ: "For historical queries, the `end` parameter must be at least 15 minutes old to query SIP data without a subscription." A too-recent query returns `{"code":42210000,"message":"subscription does not permit querying recent SIP data"}`.
- **Feeds** (`feed=`): `sip` (all US exchanges, 100% of volume), `iex` (about 2.5%, the only feed usable without a subscription for real-time), `boats` and `overnight`, and `otc`. alpaca-py's `DataFeed` also has `DELAYED_SIP`. "The default value for `feed` is always the 'best' available feed based on the user's subscription", so **always pass `feed=DataFeed.SIP` explicitly.**
- **`adjustment` parameter:** `raw` (default), `split`, `dividend`, `spin-off`, or `all`; values can be combined with commas (e.g., `split,spin-off`). alpaca-py 0.44.0's `Adjustment` enum only has RAW/SPLIT/DIVIDEND/ALL. The docs do not say whether dividend adjustment is multiplicative or subtractive.
- **Known adjustment issues:**
  - A dividend-adjustment anomaly (PFE, 2023): https://forum.alpaca.markets/t/dividend-adjustment-anomaly-in-alpacas-data/12998
  - Split-ratio errors across 22 symbols, fixed by staff in Sept 2025, followed by a new `spin-off` adjustment in Oct 2025: https://forum.alpaca.markets/t/incorrect-historical-data-of-stock-split-ratios/17839
  - Dividend adjustment adjusts price but not volume.
  - **[RECOMMENDATION]** Pull `raw` bars plus corporate actions (`CorporateActionsClient`) and build your own adjustment factors. Compare against `all` as a check.
- **`asof`:** symbol-rename mapping (e.g., FB→META), on by default. Pass `asof="-"` to disable it.
- **Timeframes:** `1Day`, `1Week`, `[1..12]Month`, `[1-59]Min`, `[1-23]Hour`. `limit` defaults to 1000, max 10000; it counts total points across all symbols, so paginate with `next_page_token` (alpaca-py uses page_size 10,000 internally). Results are sorted by symbol, then timestamp.
- **Timestamp convention:** "The (SIP) timestamp of the trade is truncated… to the day (in New York) for daily bars." The FAQ examples show `2023-09-29T04:00:00Z` (EDT). By the same rule, winter bars should be `05:00:00Z` (my inference from the rule). Convert with `tz_convert("America/New_York").normalize()` and key on the ET date.
- **Bar construction** (FAQ, "How are bars aggregated?"):
  - Daily bars use SIP trade conditions. Odd lots (`I`), Average Price (`B`/`W`), Cash (`C`), Next Day (`N`), Contingent (`V`), Qualified Contingent (`7`), Market Center Official Open (`Q`) and Official Close (`M`) do **not** update daily open or close.
  - **Extended-hours trades (`T`) update daily volume but not daily OHLC.**
  - The opening trade (`O`) and closing trade (`6`) do update.
  - A bar is only emitted if none of O/H/L/C/V is 0.
  - Weekly and monthly bars are aggregated from daily bars.
- **Daily open is not the auction open.** Staff: "Alpaca calculates the Open price by filtering for the same trade conditions used to calculate the Close/Last prices then simply takes the first trade of the day." https://forum.alpaca.markets/t/open-close-daily-bar-prices-vs-open-close-auction-prices-on-primary-exchange/14227
- **Official auction prints:** `GET https://data.alpaca.markets/v2/stocks/auctions?symbols=...&start=...&end=...&feed=sip`, where "Only `sip` is valid for auctions."
  - The response is `auctions[symbol] = [{d: date, o: [...], c: [...]}]`, each print being `{t, x (exchange), p (price), s (size), c (condition)}`.
  - Opening prints carry `O` and `Q` (Official Open); closing prints carry `6` and `M` (Official Close), across several exchanges.
  - Take the print from the **primary listing exchange** (find it with `get_asset(symbol).exchange`; map exchange codes with `GET /v2/stocks/meta/exchanges`).
  - alpaca-py 0.44.0 has **no wrapper**; use raw REST (B7). https://docs.alpaca.markets/us/reference/stockauctions-1
- **Data before 2016** is not available from Alpaca. Longer histories need another vendor; cross-validate on the overlapping period.

## B5. Paper trading realism and multi-strategy accounts

Source: https://docs.alpaca.markets/docs/paper-trading

**Fill model and limitations:**
- Fills: "Orders are filled only when they become marketable." Matched against the NBBO. "When orders are eligible to be filled, they will receive partial fills for a random size 10% of the time."
- Not simulated: "Market impact of your orders; Information leakage; Price slippage due to latency; Order queue position (for non-marketable limit orders); Price improvement received; Regulatory fees; Dividends". Borrow fees are marked "Coming Soon".
- **Auctions in paper:** "OPG orders in paper trading are simulated as regular market orders and simply fill at the opening quote. OPG orders will not necessarily fill at the auction price in paper trading" (staff, 2024; forum 14672). For MOC: "Paper trading treats these simply like market orders placed at the close. They will fill at the current bid exactly like any other market order. They will not fill at the actual end of day auction price", and they may expire partially filled (staff, 2026-06-24; forum 19155). A 2021 feature request for accurate paper auction prices is still open (https://forum.alpaca.markets/t/accurate-opg-and-cls-prices-for-paper-trading/3762).

**Accounts:**
- The default paper balance is $100k and cannot be changed without creating a new account.
- Accounts are created from the dashboard, and each new paper account needs **new API keys**.
- Limit: **"Each owner is currently allowed 3 paper accounts and 1 live account"** (staff, 2025-11-07). On 2026-08-14 staff mentioned **sub-accounts in beta** with no public date. https://forum.alpaca.markets/t/feature-request-more-paper-trading-accounts/18125
- The paper API base URL is `https://paper-api.alpaca.markets`, and the API spec is the same as live.

**Multiple strategies in one account:**
- Positions are **per account and per symbol, netted**. There is no per-strategy position, and long and short cannot coexist in one symbol.
- Opposite-side open orders on the same symbol trigger wash-trade **rejection**.
- `close_position` and `close_all_positions` act on the whole account.
- Buying power and margin are shared.
- Alpaca's own guidance: "Unique `client_order_ids` for different strategies is a good way of running parallel algos across the same account." https://docs.alpaca.markets/us/docs/working-with-orders
- **Best practice [RECOMMENDATION]:**
  - Paper: one paper account per strategy, up to 3.
  - Live (one account):
    1. An **order-netting layer**: each strategy outputs target shares, and the aggregator nets them per symbol so only **one order per symbol per side per rebalance** reaches Alpaca.
    2. An internal **strategy ledger** that allocates fills pro rata and books dividends, fees and cash per strategy.
    3. `client_order_id` encodes `{strategy}-{date}-{symbol}-{side}-{seq}`.
    4. Daily reconciliation of the ledger sum against `get_all_positions()` and `get_account()`.
    5. Never call `close_position` or `close_all_positions` in a shared account.

## B6. Clock, calendar, idempotency
- **Clock:**
  - `TradingClient.get_clock()` calls `/v2/clock` and returns `timestamp, is_open, next_open, next_close` (tz-aware).
  - A newer multi-market `/v3/clock` also exists (reference "clock-1", with a `markets` parameter such as `XNYS`) but is not wrapped by alpaca-py `TradingClient` in 0.44.0.
- **Calendar:**
  - `get_calendar(GetCalendarRequest(start, end))` calls `/v2/calendar`, which "serves the full list of market days from 1970 to 2029… taking into account early closures."
  - In alpaca-py the `Calendar.open` and `Calendar.close` datetimes are **naive, in ET**: they are parsed from `"HH:MM"` strings. Localize them to America/New_York.
  - The REST endpoint also returns `session_open`, `session_close` and `settlement_date`, and accepts `date_type=TRADING|SETTLEMENT` (legacy reference). alpaca-py's request model only passes start and end.
  - A `/v3/calendar/{market}` endpoint also exists.
- **`client_order_id` rules:**
  - "A unique identifier for the order. Automatically generated if not sent. (<= 128 characters)" (POST /v2/orders reference).
  - A duplicate gives **HTTP 422 "client_order_id must be unique"**. Alpaca's error guide says it is unique per "active order" (https://alpaca.markets/learn/how-to-fix-common-trading-api-errors-at-alpaca, Mar 2026).
  - Whether filled or cancelled orders' IDs can be reused is **[UNVERIFIED]**. Treat IDs as globally unique.
  - Look orders up with `get_order_by_client_id(id)` (`GET /v2/orders:by_client_order_id`).
- **Retries (alpaca-py):**
  - `RESTClient` retries **any method including POST** on HTTP **429 and 504**: 3 attempts, 3 s apart (`DEFAULT_RETRY_EXCEPTION_CODES = [429, 504]` in `alpaca/common/constants.py`).
  - If a 504'd POST was in fact accepted, the retry returns 422 "client_order_id must be unique". That means **the order exists**; fetch it by client ID rather than treating it as a failure. See https://github.com/tim1016/learn-ai/issues/2304 for an incident write-up.
- **Rate limits:** 200 trading API calls/min on standard accounts, 1000 on Elite (Elite page).

## B7. alpaca-py code snippets (checked against alpaca-py **0.44.0**, released 2026-08-11)
Source: https://github.com/alpacahq/alpaca-py (commit c803f2d, 2026-09-23). I ran the constructors and `to_request_fields()` locally on Python 3.12 without network calls. alpaca-py requires Python ≥ 3.10.

```python
from datetime import datetime, date, timedelta, timezone
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (MarketOrderRequest, LimitOrderRequest, GetOrdersRequest,
                                     GetCalendarRequest, ClosePositionRequest)
from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus
from alpaca.common.exceptions import APIError
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.historical.corporate_actions import CorporateActionsClient  # not re-exported in 0.44.0
from alpaca.data.requests import StockBarsRequest, CorporateActionsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import Adjustment, DataFeed, CorporateActionsType

# NOTE: paper defaults to True in the constructor -> pass paper=False explicitly for live.
trading = TradingClient(api_key=KEY, secret_key=SECRET, paper=True)
data = StockHistoricalDataClient(api_key=KEY, secret_key=SECRET)

# --- Account / positions (all numeric fields are strings) ---
acct = trading.get_account()
equity, cash, bp = float(acct.equity), float(acct.cash), float(acct.buying_power)
positions = {p.symbol: float(p.qty) for p in trading.get_all_positions()}  # also p.market_value, p.avg_entry_price, p.qty_available

# --- Clock / calendar ---
clock = trading.get_clock()            # clock.is_open, clock.next_open, clock.next_close
days = trading.get_calendar(GetCalendarRequest(start=date(2026, 9, 1), end=date(2026, 12, 31)))
# days[i].date, days[i].open / .close are NAIVE datetimes in America/New_York

# --- Daily SIP bars (raw) ---
bars = data.get_stock_bars(StockBarsRequest(
    symbol_or_symbols=["SPY", "TLT"], timeframe=TimeFrame.Day,
    start=datetime(2016, 1, 1, tzinfo=timezone.utc),
    end=datetime.now(timezone.utc) - timedelta(minutes=16),   # Basic plan: >15 min old for SIP
    adjustment=Adjustment.RAW, feed=DataFeed.SIP)).df          # MultiIndex (symbol, timestamp UTC)

# --- Cash dividends for total-return construction ---
ca = CorporateActionsClient(api_key=KEY, secret_key=SECRET).get_corporate_actions(
    CorporateActionsRequest(symbols=["TLT"], types=[CorporateActionsType.CASH_DIVIDEND],
                            start=date(2016, 1, 1), end=date(2026, 9, 24)))

# --- Orders ---
coid = "trend1-20260925-SPY-buy-1"      # <=128 chars, globally unique
moo = MarketOrderRequest(symbol="SPY", qty=10, side=OrderSide.BUY,
                         time_in_force=TimeInForce.OPG, client_order_id=coid)  # whole shares only; Elite likely required
day_frac = MarketOrderRequest(symbol="SPY", notional=1234.56, side=OrderSide.BUY,
                              time_in_force=TimeInForce.DAY, client_order_id=coid + "-n")  # fractional/notional => DAY only
loc = LimitOrderRequest(symbol="SPY", qty=5, side=OrderSide.SELL,
                        time_in_force=TimeInForce.CLS, limit_price=700.00)      # LOC; submit before 15:50 ET

def submit_idempotent(req):
    try:
        return trading.submit_order(order_data=req)
    except APIError as e:
        if "client_order_id must be unique" in str(e):          # e.g. after an SDK auto-retry on 504
            return trading.get_order_by_client_id(req.client_order_id)
        raise

open_orders = trading.get_orders(filter=GetOrdersRequest(
    status=QueryOrderStatus.OPEN, symbols=["SPY", "TLT"], limit=500,   # limit default 50, max 500
    after=datetime(2026, 9, 1, tzinfo=timezone.utc), direction="asc", nested=False))
# Order fields: id, client_order_id, status, filled_qty, filled_avg_price, submitted_at, filled_at

trading.close_position("SPY", close_options=ClosePositionRequest(percentage="50"))  # qty= or percentage= (strings)
# DO NOT use close_position/close_all_positions in a multi-strategy account.

# --- Official auction prints (no alpaca-py wrapper in 0.44.0) ---
import requests
r = requests.get("https://data.alpaca.markets/v2/stocks/auctions",
                 headers={"APCA-API-KEY-ID": KEY, "APCA-API-SECRET-KEY": SECRET},
                 params={"symbols": "SPY,QQQ", "start": "2026-09-01", "end": "2026-09-24", "feed": "sip"})
# r.json()["auctions"]["SPY"] -> [{"d": "...", "o": [{"c":"Q","p":...,"x":"P","t":...}, ...], "c": [{"c":"M",...}, ...]}]
# Paginate via next_page_token. Pick x == primary listing exchange; 'Q' = official open, 'M' = official close.
```

Account configuration (for long-only, unlevered): `trading.set_account_configurations(...)` takes an `AccountConfiguration` whose fields are `max_margin_multiplier` ("1"/"2"/"4"), `no_shorting`, `fractional_trading`, `suspend_trade` and so on. `pdt_check` and `dtbp_check` are deprecated, per the alpaca-py docstring "removed from Alpaca responses on 2026-07-06".

## B8. Transaction-cost estimates for liquid ETFs

### Quoted spreads (normal intraday conditions)

**ETF Research Center** (average NBBO spread from up to 3 months of Nasdaq tick data; page data as of 2026-08-31):

| ETF | Average full spread | Range |
|---|---|---|
| SPY | <1 bp | — |
| QQQ | <1 bp | — |
| GLD | <1 bp | — |
| TLT | 1 bp | — |
| VNQ | 1 bp | <1–1 bp |
| EEM | 2 bp | 1–2 bp |
| XLB | 2 bp | — |
| XLRE | 2 bp | — |
| DBC | 3 bp | 3–4 bp |

Sources: https://www.etfrc.com/SPY , /QQQ , /GLD , /TLT , /VNQ , /EEM , /XLB , /XLRE , /DBC

**Issuer 30-day median bid/ask spreads** (rounded to 0.01%, as of 2026-09-24):

| ETF | Median spread | Source |
|---|---|---|
| SPY | 0.00% | ssga.com |
| IWM | 0.00% | ishares.com |
| EFA | 0.01% | ishares.com |
| EEM | 0.01% | ishares.com |
| TLT | 0.01% | ishares.com |
| IEF | 0.01% | ishares.com |
| SHV | 0.01% | ishares.com |
| BIL | 0.01% | ssga.com |
| XLU | 0.02% | ssga.com |
| VNQ | 0.010% (2026-09-18) | Vanguard, via search result; not fetched directly |

- For most of these funds the spread is effectively **one tick ($0.01)**, so the half-spread ≈ $0.005/price. At the late-Sept-2026 issuer-page prices: SPY ($767) 0.07 bp; IWM ($282) 0.18 bp; EFA ($106) 0.47 bp; EEM ($68) 0.74 bp; TLT ($79) 0.63 bp; IEF ($90) 0.56 bp; SHV ($110) 0.45 bp; BIL ($92) 0.55 bp.
- The issuer numbers are rounded and ETFRC reports whole-bp averages. Neither measures spreads in the first minutes after the open.

### Opening and closing auctions (academic evidence)
- **Closing auctions are cheap; opening auctions are illiquid.** Goyal, Jegadeesh & Wu (2026, *JFQA*), "Price Impact in Closing Auctions, Opening Auctions, and Continuous Markets": "the price impact is lower in closing auctions than in the continuous market for all stocks except Nasdaq microcaps. **Opening auctions are illiquid.**" For large stocks, closing-auction impact is 3.2–10.1 bps vs 6.4–20.2 bps continuous, for trades of 0.5–5% of ADV (as summarized from the article page). https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/price-impact-in-closing-auctions-opening-auctions-and-continuous-markets-a-benchmark-for-cost-of-trading-on-anomalies/0F72910A79C5B42CF6E85F55164CE846
- **Closing price vs pre-close midquote.** Bogousslavsky & Muravyev (2023), "Who Trades at the Close?", *Journal of Financial Markets* 66, 100852:
  - Across stocks, the average |log(p_auction/p_4:00 mid)| is **8.1 bps**, about the average half-spread of 7.6 bps.
  - The closing price equals the pre-close bid or ask in **68.5%** of auctions.
  - "**large ETFs (SPY, QQQ, and S&P sectors)… average deviation of 3.63 bps, and 99th percentile of 16.32 bps**."
  - Deviations "revert quickly and almost completely" by the next morning.
  - Links: https://ideas.repec.org/a/eee/finmar/v66y2023ics1386418123000502.html ; working-paper PDF https://static1.squarespace.com/static/6310c0b9bb63a25599f4418c/t/634ffc92f81e226b2c30654f/1666186387645/who-trades-at-the-close_June2021.pdf
  - **Implication:** a filled MOC order gets exactly the official close, so the slippage vs a backtest priced at the official close is 0. The close itself is noisy relative to the mid by about 3.6 bps for large ETFs, which matters only if the harness benchmarks against midquotes.
- **Spreads at the open are wider.** ETF-issuer trading guidance: "ETF portfolios are often made up of many securities that don't necessarily open the moment the market opens", so wait about 15 minutes after the open. Spreads also widen near the close because "it can be more difficult for market makers to hedge positions going into the market close" (American Century, https://www.americancentury.com/insights/market-orders-vs-limit-orders/). International-equity ETFs (EFA, EEM) and commodity ETFs (DBC) are most exposed to fair-value uncertainty at the US open.

### Recommended per-side cost assumptions **[RECOMMENDATION — calibrate with live fills]**

Tiers used below:
- **Tier 1:** SPY, QQQ, IWM, GLD, TLT, IEF, BIL, SHV.
- **Tier 2:** EFA, EEM, VNQ, large sector SPDRs.
- **Tier 3:** DBC, smaller sector SPDRs (XLB, XLRE, XLU), anything with an ETFRC spread ≥ 2 bp.

| Execution style on Alpaca | Reference price | Tier 1 | Tier 2 | Tier 3 |
|---|---|---|---|---|
| CLS/MOC (Elite only), whole shares | official close (`M` print, primary exchange) | 0 bps + Elite commission $0.004/sh | same | same |
| OPG/MOO (Elite only), whole shares | official open (`Q` print, primary exchange) | 0–1 bp + Elite commission | 0–2 bps | 0–3 bps |
| DAY market order submitted pre-open (standard account; fractional allowed) | official open | **2 bps** | **4 bps** | **6 bps** |
| DAY market order ≥ 15 min after open | NBBO mid at submission | 0.5 bp | 1 bp | 2 bps |
| DAY market order ~15:55 (continuous, not auction) | official close | 1 bp | 2 bps | 3 bps |

Add regulatory fees (B2) on top of these. Stress-test at **2×**.

Elite commission in bps = $0.004/price:
- SPY about 0.05 bp; BIL about 0.44 bp; about 1 bp on a ~$40 ETF.
- This dominates spread costs for tier-1 funds, so the auction route is not free.

**Calibration loop:**
1. Log every fill: `filled_avg_price`, `filled_at`, `client_order_id`.
2. Fetch the same-day official open or close from `/v2/stocks/auctions` for the primary exchange, plus the NBBO at submission.
3. Compute signed slippage in bps (positive = worse).
4. After about 50–100 fills per tier, replace the table above with the empirical mean plus 1 standard deviation.

---

## Source index (primary)

**Alpaca**
- Docs index: https://docs.alpaca.markets/us/llms.txt
- Orders: https://docs.alpaca.markets/docs/orders-at-alpaca
- Fractional trading: https://docs.alpaca.markets/docs/fractional-trading
- POST order reference: https://docs.alpaca.markets/us/reference/postorder
- Working with orders: https://docs.alpaca.markets/us/docs/working-with-orders
- Paper trading: https://docs.alpaca.markets/docs/paper-trading
- Market data API / plans: https://docs.alpaca.markets/us/docs/about-market-data-api
- Market data FAQ: https://docs.alpaca.markets/us/docs/market-data-faq
- Historical bars: https://docs.alpaca.markets/us/reference/stockbars
- Auctions: https://docs.alpaca.markets/us/reference/stockauctions-1
- Margin and short selling: https://docs.alpaca.markets/us/docs/margin-and-short-selling
- Intraday margin rule: https://docs.alpaca.markets/us/docs/the-intraday-margin-rule
- Elite Smart Router: https://docs.alpaca.markets/docs/alpaca-elite-smart-router
- Brokerage fee schedule: https://files.alpaca.markets/disclosures/library/BrokFeeSched.pdf
- Regulatory fees (support): https://alpaca.markets/support/regulatory-fees
- Cash accounts (support): https://alpaca.markets/support/alpaca-cash-accounts
- Elite: https://alpaca.markets/elite
- Order types (Learn): https://alpaca.markets/learn/13-order-types-you-should-know-about
- PDT retirement blog: https://alpaca.markets/blog/finra-retires-the-pdt-rule-introducing-alpacas-new-intraday-margin-framework/
- API error guide: https://alpaca.markets/learn/how-to-fix-common-trading-api-errors-at-alpaca
- alpaca-py: https://github.com/alpacahq/alpaca-py

**Alpaca forum** (staff statements): threads 14672, 19155, 3762, 11664, 13787, 16562, 14227, 14715, 18125, 15071, 12998, 17839, 13441, 18200 at https://forum.alpaca.markets/t/<id>

**Regulators**
- SEC FY2026 fee advisory: https://www.sec.gov/rules-regulations/fee-rate-advisories/2026-2
- SEC FY2025 fee advisory: https://www.sec.gov/rules-regulations/fee-rate-advisories/2025-2
- SR-FINRA-2026-021 (TAF holiday): https://www.sec.gov/files/rules/sro/finra/2026/34-106409.pdf
- SR-FINRA-2024-019 (TAF schedule): https://www.finra.org/sites/default/files/2024-11/sr-finra-2024-019.pdf
- FINRA Regulatory Notice 26-10: https://www.finra.org/rules-guidance/notices/26-10

**Papers**: as cited inline (Bailey & López de Prado 2012 and 2014; Bailey, Borwein, López de Prado & Zhu 2017; Harvey, Liu & Zhu 2016; Harvey & Liu 2015; McLean & Pontiff 2016; Politis & Romano 1994; Politis & White 2004 / Patton, Politis & White 2009; Hall, Horowitz & Jing 1995; Ledoit & Wolf 2008; Hoffstein et al. 2019 and 2020; Bogousslavsky & Muravyev 2023; Goyal, Jegadeesh & Wu 2026; López de Prado, Lipton & Zoonekynd 2025).
