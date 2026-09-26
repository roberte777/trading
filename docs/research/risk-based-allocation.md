# Risk-Based and Volatility-Based Allocation Strategies: Research Dossier

Research date: 2026-09-25. Aimed at a daily-bar, long-only, ≤1x gross, ETF-on-Alpaca backtest harness (decide at close, fill at next open or next close).

---

## 0. How to read this document / verification notes

- **What was verified against the original papers.** I downloaded and read the full text (PDF) of: Moreira & Muir (NBER w22208 version), Harvey et al. (2018, JPM, Duke-hosted published PDF), Cederburg et al. (2020, JFE published PDF), Asness-Frazzini-Pedersen (2012, FAJ, AQR-hosted), Maillard-Roncalli-Teiletche (2008/2009 working-paper PDF from Roncalli's site), Qian (2005 PanAgora white paper), Clarke-de Silva-Thorley (2011, which restates the 2006 method), Frazzini-Pedersen (NBER 2010 and published JFE 2014), Ang-Hodrick-Xing-Zhang (2006, the Columbia-hosted copy), DeMiguel-Garlappi-Uppal (June 2006 NBER Summer Institute draft), Clare-Seaton-Smith-Thomas (2016, published JBEF PDF), Bongaerts-Kang-van Dijk (2020, FAJ), and Asness-Frazzini-Pedersen (2014, FAJ). Anything taken from these is stated as fact, with the section or table given.
- **What was NOT verified.** SSRN pages returned HTTP 403 (a Cloudflare challenge), so I could not read SSRN posting dates directly. Those dates come from search-engine snippets, NBER issue dates, or dates printed inside the PDFs, and each one is flagged. I could not get the full text of Clarke-de Silva-Thorley (2006), Liu-Tang-Zhou (2019), Kirby-Ostdiek (2012), Chaves et al. (2011), Anderson-Bianchi-Goldberg (2012) or Fleming-Kirby-Ostdiek (2001). For those I used only the abstract or a secondary source, and I say so.
- **ETF and proxy dates.** Each ticker's inception date comes from Yahoo `meta.firstTradeDate`. For mutual funds and indices I also pulled the full daily history and recorded the first non-null bar (§1). I computed the fit statistics between each proxy and its ETF myself from Yahoo adjusted closes (§1.3).
- **"OOS start".** This is the first month after the earliest public date I could establish. Treat data after it as out-of-sample.

### 0.1 Summary table

| # | Strategy (source) | Earliest public date → OOS start | Leverage in paper? | ETF faithfulness | Realistic backtest start with Yahoo proxies |
|---|---|---|---|---|---|
| 1a | Volatility-managed market (Moreira & Muir 2017) | SSRN 2659431, "date written" 2015-09-12 (snippet); NBER w22208 Apr-2016 → **2015-10** | Yes, uncapped (P99 weight 6.4x). Capped 1.0 and 1.5 versions are in the paper | High for the market factor (SPY plus T-bills). Low for the other factors | 1980+ (VFINX) for calibration; 2000+ trivially |
| 1b | Volatility targeting (Harvey et al. 2018) | SSRN 3175538, reported 2018-06-25 (snippet) → **2018-07** | Yes (10% target, no cap, unfunded futures) | High for SPY. Leverage cap needed | 2000+ |
| 1c | Conditional vol targeting (Bongaerts, Kang, van Dijk 2020) | SSRN 3636727 (2020) → **2020-07** | Up to 2.0x in low-vol states | High for SPY | 2000+ (uses a ≥10y expanding target; VFINX from 1980) |
| 2a | Inverse-vol risk parity (Asness, Frazzini, Pedersen 2012) | FAJ Jan/Feb 2012; SSRN 1990493 → **2012-02** | Both unlevered and levered (vol-matched) | High for stock/bond. Medium for broad (credit and commodity mapping) | Stock/bond 1994+; broad about 2005+ |
| 2b | ERC (Maillard, Roncalli, Teiletche 2010) | First version June 2008 (printed on paper); SSRN 1271972 posted 2008-09-22 (snippet) → **2008-07** | No (fully invested) | High (the paper uses index-level assets and sectors) | Sectors 2000+; multi-asset 2003+ |
| 3a | Minimum variance, 1,000 US stocks (Clarke, de Silva, Thorley 2006) | JPM published 2006-10-31 (Crossref) → **2006-11** | No (long-only) | **Low** at ETF level (the effect is stock-level) | n/a (needs stock universe) |
| 3b | Betting Against Beta (Frazzini & Pedersen 2014) | NBER w16601 Dec-2010 → **2011-01** | Yes, long-short and levered | **Not implementable** long-only | n/a |
| 3c | Idiosyncratic volatility (Ang et al. 2006) | NBER w10852 Oct-2004 → **2004-11** | Long-short | **Not implementable** at ETF level | n/a |
| 3d | Sector minimum variance (DeMiguel et al. "min-c" on S&P sectors; MRT sector example) | Mar-2005 draft / Jun-2008 → 2005-04 / 2008-07 | No | High relative to *those* papers | 2000+ |
| 4a | 60/40 (monthly rebalance, as in AFP 2012) | Convention, not a strategy paper | No | Exact | 1991+ |
| 4b | Permanent Portfolio (Browne 1987/1999) | Book, 1987 → effectively all OOS | No | Exact | **2000-09** (gold via GC=F) |
| 4c | 1/N (DeMiguel, Garlappi, Uppal 2009) | First draft March 2005 (conference circulation); CEPR DP / SSRN 785164 July 2005 → **2005-04** | No | High (S&P sectors dataset) | 2000+ |
| 5 | Risk parity plus 10-month trend filter (Clare, Seaton, Smith, Thomas 2016) | SSRN 2126478 (2012); JBEF online 2016-01-15 → **2012-09** (concept) / **2016-01** (published spec) | No | Medium (global indices mapped to US ETFs) | about 2003+ (commodity proxy) |

---

## 1. Universe, inception dates, and pre-inception proxies (shared by all strategies)

### 1.1 ETF inception (Yahoo `firstTradeDate`, verified 2026-09-25)

| Role | ETF | Inception | Notes |
|---|---|---|---|
| US equity | SPY | 1993-01-29 | IVV 2000-05-19, VTI 2001-06-15, VOO 2010-09-09 |
| Dev ex-US equity | EFA | 2001-08-27 | VEA 2007-07-26 |
| EM equity | EEM | 2003-04-14 | VWO 2005-03-10 |
| Global equity | ACWI 2008-03-28, VT 2008-06-26, URTH 2012-01-12 | | |
| Long Treasury | TLT | 2002-07-30 | SPTL 2007-05-30, VGLT 2010-01-04, EDV 2008-01-29 |
| Intermediate Treasury | IEF | 2002-07-30 | GOVT 2012-02-24 |
| Short Treasury | SHY | 2002-07-30 | |
| T-bills (cash) | BIL | 2007-05-30 | SHV 2007-01-11, SGOV 2020-06-01 |
| TIPS | TIP | 2003-12-05 | SCHP 2010-08-05, VTIP 2012-10-16 |
| Aggregate bonds | AGG | 2003-09-29 | BND 2007-04-10 |
| IG credit | LQD | 2002-07-30 | HYG 2007-04-11, JNK 2007-12-04, EMB 2007-12-19 |
| Gold | GLD | 2004-11-18 | IAU 2005-01-28, GLDM 2018-06-26 |
| Commodities | DBC | 2006-02-06 | GSG 2006-07-21 (S&P GSCI TR), DJP 2006-10-30 (BCOM TR, an ETN), BCI 2017-03-31, CMDY 2018-04-05 |
| US REITs | VNQ | 2004-09-29 | IYR 2000-06-19 |
| Global REITs | RWO 2008-05-22, VNQI 2010-11-01, REET 2014-07-10 | | |
| Intl govt bonds | BWX 2007-10-11, BNDX 2013-06-04 | | |
| Sector SPDRs | XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY | 1998-12-22 (all nine) | XLRE 2015-10-08, XLC 2018-06-19 |
| Low-vol products | SPLV 2011-05-05, USMV / EFAV / EEMV / ACWV 2011-10-20 | | SPHB (high beta) 2011-05-05 |
| Balanced / RP products (benchmarks only) | AOR 2008-11-19, RPAR 2019-12-13, NTSX 2018-08-02 | | |
| Embedded leverage | SSO 2006-06-21, UPRO 2009-06-25, UBT 2010-01-21, TMF 2009-04-16, UGL 2008-12-03 | | Daily-reset products |

### 1.2 Pre-inception proxies on Yahoo (first daily bar verified from a full-history pull)

| Proxy for | Yahoo ticker | First bar | Comment |
|---|---|---|---|
| SPY | VFINX | 1980-01-02 | Vanguard 500 Index. Also ^SP500TR from 1988-01-04 (an index, not tradeable) |
| VTI | VTSMX | 1992-04-27 | |
| EFA | VTMGX | 1999-08-17 | Vanguard Developed Markets Index (Admiral). For pre-1999 data, blend VEURX + VPACX (both 1990-06-18), or use VGTSX (1996-04-29; total international, so it includes EM) |
| EEM | VEIEX | 1994-05-04 | |
| TLT | VUSTX | 1986-05-19 | Shorter duration than TLT (vol 11.9% vs 13.4%) |
| IEF | VFITX | 1991-10-28 | Shorter duration than IEF (vol 4.7% vs 6.6%). Scale it or accept the mismatch |
| SHY | VFISX | 1991-10-28 | |
| AGG | VBMFX | 1986-12-11 | |
| TIP | VIPSX | 2000-06-29 | |
| VNQ | VGSIX | 1996-05-13 | Same Vanguard fund, investor share class |
| LQD | VWESX (1980-01-02, long IG), VFICX (1993-10-29, intermediate IG) | | Duration differs from LQD. Treat as approximate |
| GLD | GC=F | 2000-08-30 | Front-month COMEX continuous series with 83 null closes (forward-fill). No gold series exists on Yahoo before Aug-2000. VGPMX (Vanguard Precious Metals) is now "Global Capital Cycles" and should not be used. Miner funds (FSAGX, INIVX, USAGX, OPGSX) are equity-like and are **not** gold proxies |
| DBC / DJP | PCRIX | 2002-07-01 | PIMCO CommodityRealReturn (BCOM exposure collateralized with actively managed TIPS) |
| GSG | ^SPGSCI | 1984-01-03 | **Spot index only (no roll yield). Do not use as a total-return proxy** (see §1.3) |
| Cash / T-bills | ^IRX | 1970-01-02 (daily) | 13-week T-bill discount yield in %. Accrue as `r_d = (IRX_{d-1}/100) × days/360`. Yahoo has no usable money-market NAV history (VMMXX and VUSXX are flat) |
| 60/40 sanity check | VBINX | 1992-09-28 | Vanguard Balanced Index (60% total stock / 40% total bond) |
| Permanent Portfolio fund | PRPFX | 1982-11-30 | A different mix (silver, Swiss franc, etc.). **Not** Browne's 25×4 |
| Sector funds (pre-1999) | Fidelity Select: FSPTX, FSENX, FSUTX, FSPHX, FSRBX, FDFAX, FSDPX, FSCPX | 1981–1990 | Actively managed. Poor proxies. Sector SPDRs already cover 1999+ |

### 1.3 Proxy fit (my own computation from Yahoo adjusted closes, overlap to 2026-09-25)

| ETF vs proxy | Overlap start | Monthly corr | Daily corr | ETF CAGR / proxy CAGR | Tracking error (ann., monthly) |
|---|---|---|---|---|---|
| SPY vs VFINX | 1993-03 | 0.998 | 0.985 | 10.86% / 10.85% | 0.84% |
| EFA vs VTMGX | 2001-09 | 0.994 | 0.966 | 7.20% / 7.70% | 1.79% |
| EFA vs VGTSX | 2001-09 | 0.984 | 0.961 | 7.20% / 7.73% | 2.96% |
| EEM vs VEIEX | 2003-05 | 0.978 | 0.937 | 9.74% / 9.52% | 4.34% |
| TLT vs VUSTX | 2002-08 | 0.992 | 0.982 | 3.13% / 3.25% | 2.24% |
| IEF vs VFITX | 2002-08 | 0.982 | 0.945 | 3.27% / 3.00% | 2.23% |
| SHY vs VFISX | 2002-08 | 0.963 | 0.811 | 1.93% / 2.09% | 0.54% |
| TIP vs VIPSX | 2004-01 | 0.993 | 0.945 | 3.38% / 3.25% | 0.66% |
| GLD vs GC=F | 2004-12 | 0.992 | 0.888 | 10.55% / 11.04% | 2.18% |
| DBC vs PCRIX | 2006-03 | 0.907 | 0.847 | 2.93% / 2.54% | 8.13% |
| DJP vs PCRIX | 2006-11 | 0.962 | n/a | 0.42% / 2.24% | 5.20% |
| GSG vs ^SPGSCI | 2006-08 | 0.978 | 0.940 | **−1.48% / +2.16%** | 4.86% |
| VNQ vs VGSIX | 2004-10 | 0.999 | 0.994 | 7.02% / 6.89% | 0.77% |
| AGG vs VBMFX | 2003-10 | 0.978 | 0.788 | 2.96% / 2.95% | 0.95% |
| BIL vs ^IRX accrual | 2007-05 | n/a | n/a | 1.39% / 1.50% | n/a (gap ≈ expense ratio) |
| SHV vs ^IRX accrual | 2007-01 | n/a | n/a | 1.60% / 1.57% | n/a |

Takeaways:
- ^SPGSCI overstates commodity returns by about 3.6%/yr against the investable GSG because it omits roll yield. It is unusable for return backtests. It is acceptable for **volatility or trend signals** only if clearly flagged.
- PCRIX earns about 1.8%/yr more than DJP because of its TIPS collateral and active management. It is the best available commodity return proxy on Yahoo, and it only starts in 2002-07.
- Daily correlation is materially lower than monthly for the international funds (stale NAV and fair-value pricing), for GC=F (it settles at 1:30pm ET) and for AGG/VBMFX. **Covariance estimated from daily proxy returns is biased toward lower correlation.** Prefer weekly or monthly returns, or overlapping 3-day returns as in Frazzini-Pedersen (2014), when estimating covariance on proxy data.

### 1.4 Cross-cutting proxy pitfalls
1. **Mutual-fund proxies have open = close (NAV only).** A "next open" fill cannot be simulated before ETF inception. Run the proxy era with fills at next close (close-to-close returns), or with one extra day of lag, and document the switch.
2. **Splice returns, not prices.** Chain daily total returns: proxy adjusted-close returns up to the ETF's first day plus a few days, then ETF returns. Do not rescale price levels.
3. **Yahoo adjusted close for mutual funds** reinvests capital-gain distributions. Spot-check large December distributions for errors (not verified fund-by-fund here).
4. **Warm-up.** A 36-month lookback starting 2000-01 needs data from 1997-01. Gold (Aug-2000) and investable commodities (Jul-2002) cannot support that, so multi-asset strategies that include them realistically start around 2003–2005.
5. **Cash.** BIL from 2007-05-30. Before that, use ^IRX accrual, which matches BIL within its fee. SGOV has lower cost from 2020.

---

## 2. Volatility-managed portfolios / volatility targeting

### 2.1 Moreira & Muir (2017), "Volatility-Managed Portfolios"
- **Citation:** Alan Moreira and Tyler Muir, *Journal of Finance* 72(4), 1611–1644, Aug 2017. DOI 10.1111/jofi.12513 (https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12513). SSRN: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2659431. NBER WP 22208 (April 2016, revised June 2016): https://www.nber.org/papers/w22208.
- **First public date:** A search snippet of the SSRN page shows **2015-09-12** (not directly verified because SSRN blocked me). A Nov-1-2015 seminar draft is hosted at NYU Stern. NBER issued it in April 2016. **OOS start: 2015-10.**
- **Exact rule (NBER text §2.2, eqs. 1–2; Table 1 notes):**
  - Managed excess return: `f^σ_{t+1} = (c / σ̂²_t(f)) · f_{t+1}`. Here `f` is the factor **excess** return (for the market, Mkt−RF from Ken French's data, i.e. over the 1-month T-bill).
  - Conditional variance proxy is the **previous calendar month's realized variance** from daily returns: `RV²_t = Σ_{d=1/22}^{1} ( f_{t+d} − Σ_{d} f_{t+d}/22 )²`. This is a **sum** of squared **demeaned** daily returns over the month, with the mean taken as sum/22. It is not annualized and not averaged.
  - **Rebalance monthly.** The weight for month t+1 uses only month-t daily data.
  - `c` is chosen **over the full sample** so that the managed portfolio has the same unconditional standard deviation as buy-and-hold (footnote 5: c does not affect the Sharpe ratio). **This is in-sample and not known in real time.**
  - Alternatives in the paper (Tables 4–5): scale by 1/RV (volatility instead of variance); scale by the AR(1) forecast of log variance; **cap at 1 ("No Leverage") or 1.5 ("50% Leverage", "consistent with a standard margin requirement")**, i.e. `min(c/RV², 1)` and `min(c/RV², 1.5)` with the same c.
- **Sample and results (market factor, 1926–2015, monthly):**
  - Alpha 4.86% p.a. (s.e. 1.56), β 0.61, appraisal ratio 0.34, Sharpe 0.52.
  - $1 grows to about $20,000 versus about $4,000 for buy-and-hold.
  - Uncapped weights: P50 0.93, P75 1.59, P90 2.64, **P99 6.39**. Mean |Δw| per month 0.73.
  - **No-leverage cap (1.0):** α 2.12% (0.71), Sharpe 0.52, E[R] 5.61%, |Δw| 0.16, break-even trading cost 110 bp.
  - **1.5 cap:** α 3.10% (0.98), Sharpe 0.53, E[R] 7.18%, break-even cost 161 bp.
  - Uncapped break-even cost 56 bp.
  - Scaling by 1/RV (volatility): α 3.30–3.85%, similar Sharpe, P99 weight 3.36.
  - 20 OECD indices: managed Sharpe on average 0.15 higher, and higher in 80% of countries (Appendix A.2).
- **Other factors:** In JF Table 1 (NBER version), large alphas appear for momentum (12.5%), ROE and carry. SMB is negative. These factors are not ETF-implementable.

### 2.2 Harvey, Hoyle, Korgaonkar, Rattray, Sargaison, Van Hemert (2018), "The Impact of Volatility Targeting" (Man Group)
- **Citation:** *Journal of Portfolio Management* 45(1), 14–33, Fall 2018. DOI 10.3905/jpm.2018.45.1.014 (Crossref-verified). https://jpm.pm-research.com/content/45/1/14. SSRN 3175538: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3175538. Published PDF: https://people.duke.edu/~charvey/Research/Published_Papers/P135_The_impact_of.pdf.
- **First public date:** SSRN, reported as 2018-06-25 (snippet, unverified). **OOS start: 2018-07.**
- **Exact rule (paper pp. 16–17, footnote 8):**
  - `r_scaled_t = k · (σ_target / σ̂_{t−1}) · r_t`. The volatility estimate is "known a full 24 hours ahead of time, using returns up to t−2", i.e. one extra day of lag.
  - `σ̂` is the **exponentially weighted standard deviation of daily returns with zero mean** (squared returns). Half-lives tested: **10, 20, 40, 60, 90 days** (decoded from Exhibit 5). **20 days** is the headline choice.
  - At least 270 trading days of warm-up. Target **10% annualized**. `k ≈ 1` is set ex post so the full-sample realized vol is exactly 10% (again an in-sample constant).
  - **Daily rebalancing, no leverage cap.** Returns are excess over T-bills or unfunded futures.
  - Results were similar with equal-weight rolling windows and with 3- or 5-day overlapping returns.
- **Results:**
  - US equities 1927–2017: Sharpe **0.40 → 0.48 / 0.49 / 0.50 / 0.51 / 0.51** (HL 10/20/40/60/90). Vol-of-vol 4.6% → about 1.7–2.2%. Annual notional turnover 4.66 (HL 10) down to 0.56 (HL 90). Mean exposure about 70% at the 10% target.
  - S&P 500 futures 1988–2017: 0.50 → 0.57–0.60 (daily volatility), 0.60–0.63 (5-minute intraday volatility).
  - **Bonds, FX and commodities: negligible Sharpe effect.** Improvements are confined to "risk assets" (equity, credit), which the authors link to the leverage effect. Left tails shrink across all asset classes.
  - 60/40 (in risk terms, S&P and 10y futures) 1988–2017: Sharpe 0.80 unscaled → 0.87 with asset-level scaling → **0.91 with asset-level plus portfolio-level scaling**. Similar results for a 25×4 equity/bond/credit/commodity risk-parity portfolio (online supplement, not read).

### 2.3 Critiques and post-publication evidence
- **Cederburg, O'Doherty, Wang & Yan (2020), "On the performance of volatility-managed portfolios"**
  - *JFE* 138(1), 95–117. DOI 10.1016/j.jfineco.2020.04.015. SSRN 3357038 (posted about Mar-2019; presented 2017). Author PDF: https://www.lehigh.edu/~xuy219/research/COWY.pdf.
  - Uses 103 equity strategies. Volatility-managed versions "do not systematically outperform" in direct Sharpe comparisons.
  - MKT, 1926–2016: Sharpe 0.42 → 0.51, difference 0.09, **p = 0.30** (Table 1).
  - Spanning-regression alphas require the in-sample combination weight and c.
  - The real-time OOS combination strategy for MKT (expanding window, 120-month training, |y| ≤ 5 leverage) earns **Sharpe 0.42 vs 0.46** for the plain market, and CER 1.56% vs 1.75% (Table 5).
  - The MKT gain is concentrated around the Great Depression, and the underperformance stems from "structural instability" in the spanning regressions.
- **Liu, Tang & Zhou (2019), "Volatility-Managed Portfolio: Does It Really Work?"**
  - *JPM* 46(1), 38–51. DOI 10.3905/jpm.2019.1.107. SSRN 3283395.
  - Abstract only (full text not read): the typical application "suffers from look-ahead bias". After correction, maximum drawdowns are **68%–93%** "in almost all cases", and outperformance is confined to the financial-crisis period.
  - It is not verified whether their implementation caps leverage. The drawdowns almost certainly reflect uncapped leverage.
- **Barroso & Detzel (2021), "Do limits to arbitrage explain the benefits of volatility-managed portfolios?"**
  - *JFE* 140(3), 744–767. SSRN 3088828.
  - Abstract (via RePEc): after transaction costs, volatility management of factors **other than the market** generally produces zero abnormal returns and lower Sharpe ratios. **The volatility-managed market's abnormal returns are robust to transaction costs** but show up only when sentiment is high.
- **Bongaerts, Kang & van Dijk (2020), "Conditional Volatility Targeting"**
  - *FAJ* 76(4), 54–71. DOI 10.1080/0015198X.2020.1790853. SSRN 3636727. PDF: https://repub.eur.nl/pub/130215/Bongaerts-Kang-van-Dijk-Conditional-volatility-targeting-2020-FAJ.pdf.
  - Real-time design: `σ_target` = **long-term realized vol from all daily returns up to month t−1 (expanding, at least 10 years)**. `σ̂` = previous month's equal-weight daily-return std, **excluding the month's last trading day** so it is known one day ahead. Costs 3–5 bp.
  - Conventional vol targeting for the US, 1982–2019: Sharpe +0.15 (5% significance). Across 10 markets it is inconsistent, raised max drawdown in 4 markets and raised expected shortfall in 8 of 10. Realized/target vol was 1.16 in the US (overshoot).
  - **Conditional** version: scale only when last month's vol is in the top or bottom **quintile** of all prior months, otherwise hold weight 1. Leverage cap `L_max` = 200%. US: Sharpe +0.16, MDD −8.3 pts, turnover 1.6 vs 2.4.
- **DeMiguel, Martín-Utrera & Uppal (2024), "A Multifactor Perspective on Volatility-Managed Portfolios"**
  - *JF* 79(6), 3859–3891. DOI 10.1111/jofi.13395. SSRN 3982504.
  - A conditional **multifactor** volatility-managed portfolio outperforms out-of-sample and net of costs (a partial rebuttal of Cederburg et al.). This is a factor-level result and is not ETF-implementable.
- Moreira & Muir's own follow-up: "Should long-term investors time volatility?", *JFE* 131(3), 507–527, 2019. DOI 10.1016/j.jfineco.2018.09.011 (verified via Crossref). SSRN 2879234. I have not read its content.

### 2.4 Proposed implementations (ETF-faithful)

**Common:** Risky asset SPY (VFINX before 1993-02; calibration can use 1980+). Cash is BIL (^IRX accrual before 2007-05-30). Use adjusted closes. `rf_d` is daily ^IRX accrual. The strategy weight `w` applies to SPY and `1 − w` goes to cash. This matches Moreira & Muir's excess-return scaling: `w·(r − rf) + rf`.

**VM-1: Moreira & Muir, unlevered (faithful to the "No Leverage" row of Tables 4–5)**
1. On the last trading day of month t, after the close, compute daily SPY excess returns `f_d` for every trading day in calendar month t.
2. Compute `RV_t = Σ_d (f_d − f̄)²` (sum over the actual trading days, with f̄ the month mean).
3. Target `w_{t+1} = min(1, c_t / RV_t)`. Fill at the next open (the first trading day of t+1) or the next close, and hold for the month.
4. **Resolving c in real time** (the paper's c is full-sample):
   - (a) *MM-faithful, expanding:* `c_t` = the value making `std(c·f/RV_lag) = std(f)` for the **uncapped** series, estimated on all months up to t. Seed it with VFINX from 1980.
   - (b) *Real-time target (Bongaerts et al. style):* `c_t = mean(RV)` over all months up to t (at least 10 years), so `w = 1` when last month's variance equals its long-run average. **I recommend (a) as primary for fidelity and (b) as the robustness check.** With (b), because RV is right-skewed, w is 1 in most months and falls below 1 only after turbulent months.
5. Report turnover. The paper reports |Δw| ≈ 0.16/month for the capped version.

**VM-2: Moreira & Muir, modestly levered.** Same rule with a 1.5 cap (as in the paper). Implement with margin, or with SSO (2x, since 2006-06) for the part above 1. Deduct financing at T-bill plus a spread. The paper assumes financing at the risk-free rate, which overstates results. Test spreads of 0.5 / 1.5 / 3%.

**VM-3: Harvey et al., daily EWMA vol target.**
- `σ̂_t = sqrt(252 · Σ_k λ^k r²_{t−k} / Σ_k λ^k)` with `λ = 0.5^(1/HL)`, HL = 20 days, zero mean, returns through the decision close.
- Target `w_t = min(cap, σ*/σ̂_t)`, with σ* = 10% (paper) and cap = 1 (unlevered) or 1.5 (levered).
- For an unlevered version, 10% gives about 0.55–0.7 average exposure. A σ* equal to the expanding long-run SPY vol (in the Bongaerts et al. manner) is the "same risk as buy-and-hold" analogue.
- Paper: daily rebalancing. Adaptation to limit costs: trade only if |Δw| > 0.05–0.10. Report both.

**VM-4: Conditional vol targeting (Bongaerts et al.).**
- `σ̂` = std of daily returns in month t−1 excluding its last day. `σ_target` = expanding long-run std (at least 10 years; VFINX makes this available from 1990).
- If `σ̂` is in the top or bottom quintile of all prior monthly `σ̂`, set `w = min(L_max, σ_target/σ̂)`. Otherwise `w = 1`.
- Unlevered: `L_max = 1`, so only the high-vol de-risking side is active. Levered: `L_max` = 1.5 (paper used 2.0).

### 2.5 Pitfalls and recommended resolutions
- **Look-ahead in c / k.** Both papers set scale constants ex post. Use the expanding or long-run-target versions above. This is the critique of Liu-Tang-Zhou and Cederburg et al.
- **Capping changes the economics.** With cap 1, average equity exposure falls. MM Table 4 gives E[R] of 5.61% capped vs 9.47% uncapped, and the market's mean excess return over 1926–2016 is 7.80% per Cederburg et al. Table 1. Sharpe is preserved but return is not. Report CAGR, Sharpe, MDD and average exposure together.
- **Variance vs volatility scaling:** 1/RV² is more extreme than 1/RV. Under a cap of 1 the difference is smaller. Test both.
- **Month-end timing:** MM trade at the month-end close using that month's data. With a next-open fill the harness adds about one day of lag. This is fine, but report next-close fills too.
- **RV definition:** a sum over variable month lengths (19–23 days) versus a per-day average. Use the paper's sum. As a neighbor, normalize by N/21.
- **Crash dynamics:** monthly RV reacts slowly to sudden crashes that start in calm months (Oct-1987 type; Feb-2020 type). Daily EWMA (VM-3) reacts faster. Do not claim either result without running it.
- **Evidence strength:** the market-factor improvement is statistically weak (Cederburg p = 0.30 on the Sharpe difference). Barroso-Detzel say it survives costs. Treat it as a risk-reduction overlay, not an alpha source.

### 2.6 Parameter neighbors
- RV window: 1 month (base), 2 weeks, 2 months, 3 months, 6 months.
- EWMA half-life: 10 / 20 / 40 / 60 / 90 days.
- Scaling power: 1/σ vs 1/σ².
- Cap: 1.0 / 1.25 / 1.5 / 2.0.
- Target: 10 / 12 / 15% or the expanding long-run vol.
- Rebalance: daily / weekly / monthly. No-trade band: 0 / 5 / 10%.
- Conditional thresholds: quintile vs quartile vs tercile.
- Asset: SPY; robustness on EFA/EEM, which are also "risk assets" per Harvey et al. Expect no benefit on TLT/GLD.

---

## 3. Risk parity

### 3.1 Asness, Frazzini & Pedersen (2012), "Leverage Aversion and Risk Parity"
- **Citation:** *Financial Analysts Journal* 68(1), 47–59, Jan/Feb 2012. DOI 10.2469/faj.v68.n1.1. PDF: https://www.aqr.com/-/media/AQR/Documents/Insights/Journal-Article/Leverage-Aversion-and-Risk-Parity.pdf. SSRN 1990493 (listed 2012-01-23 per snippet). **OOS start: 2012-02.** Earlier drafts may have circulated in 2011 (not verified).
- **Exact rule (Figure 1 notes; Appendix A):**
  - At the **end of each calendar month**, weight each asset class `w_{t,i} = k_t · σ̂_{t,i}^{-1}`.
  - `σ̂` = **3-year rolling volatility of monthly excess returns, data up to month t−1**. Other volatility estimators gave "similar results".
  - **Unlevered RP:** `k_t = 1 / Σ_i σ̂_{t,i}^{-1}` (weights sum to 1).
  - **Levered RP:** k is constant, set so ex-post annualized vol matches the benchmark (value-weighted market or 60/40). The authors note similar results when k_t is set to match the benchmark's *conditional* vol at formation.
  - No covariance is used. The rebalance is monthly. Excess returns are over the **US T-bill** rate. Leverage is financed at T-bill in the base case. Appendix B covers other financing rates, and futures-based results were similar.
- **Samples and results (Table 2):**
  - *Long sample, US stocks + Treasuries (CRSP), 1926–2010:*

    | Portfolio | Excess return | Vol | Sharpe |
    |---|---|---|---|
    | 60/40 | 4.65% | 11.68% | 0.40 |
    | Value-weighted | 3.84% | 15.08% | 0.25 |
    | **Unlevered RP** | 2.20% | 4.25% | **0.52** |
    | **Levered RP** | 7.99% | 15.08% | **0.53** |

    Average unlevered RP weights: 15% stocks / 85% bonds.
  - *Broad sample, 1973–2010:* stocks, Barclays Treasury + other government bonds, credit (Barclays corporate, securitized, HY, etc.), S&P GSCI. Value-weighted Sharpe 0.43. Unlevered RP 3.39% / 5.44% / **0.62**. Levered RP 6.15% / 10.10% / **0.61**.
  - *Global stock/bond sample, 11 countries, 1986–2010:* RP beats 60/40 in every country. US: RP Sharpe 0.78 vs 0.51.
  - Ambiguity: Table 1 lists the "CRSP Value-Weighted Index" for stocks in the broad sample, while the text says "global stocks".

### 3.2 Maillard, Roncalli & Teiletche (2010), "The Properties of Equally Weighted Risk Contribution Portfolios"
- **Citation:** *Journal of Portfolio Management* 36(4), 60–70, Summer 2010. DOI 10.3905/jpm.2010.36.4.060. SSRN 1271972 (posted 2008-09-22 per snippet). Working paper PDF: http://www.thierry-roncalli.com/download/erc.pdf. It states "**First version: June 2008**". **OOS start: 2008-07.**
- **Definition:** Choose long-only, fully invested `x` with equal risk contributions `x_i (Σx)_i = x_j (Σx)_j`. This is equivalent to minimizing variance subject to `Σ ln x_i ≥ c`, then normalizing. Vol ordering: σ_MV ≤ σ_ERC ≤ σ_1/N. ERC equals inverse-vol when correlations are equal.
- **Backtest rules (§4.2):** **monthly rebalance on the last trading day of the month**. **Covariance from daily returns over a rolling 1-year window.** Fed funds is the risk-free rate for Sharpe. There is no leverage or cash leg.
- **Results:**

  | Example | 1/N (ret / vol / Sharpe / MDD) | MV (ret / vol / Sharpe / MDD) | ERC (ret / vol / Sharpe / MDD) |
  |---|---|---|---|
  | 10 FTSE-Datastream US sectors, 1973–2008 | 10.03% / 16.20% / 0.62 / −49.0% | 9.54% / 12.41% / 0.77 / −46.2% | 10.01% / 15.35% / 0.65 / −47.2% |
  | Global diversified, 13 assets, 1995–2008 | 7.17% / 10.87% / 0.27 / −45.3% | 5.84% / 3.20% / 0.49 / −19.7% | 7.58% / 4.92% / **0.67** / −22.7% |
  | Agricultural commodities, 1979–2008 | Sharpe 0.27 | Sharpe 0.74 | Sharpe 0.49 |

  The global diversified set was S&P 500, Russell 2000, Euro Stoxx 50, FTSE 100, Topix, MSCI LatAm, MSCI EM Europe, Asia ex-Japan, JPM Euro and US government bonds, ML US HY, EMBI, S&P GSCI.
- **Solver:** minimize `½ yᵀΣy − (1/n) Σ ln y_i` over y > 0, then set `x = y/Σy`. This is convex (see Griveau-Billion, Richard & Roncalli 2013, https://arxiv.org/pdf/1311.4057, which gives a cyclical coordinate-descent algorithm). A simple Newton or `scipy.optimize` implementation is sufficient for fewer than 20 assets.

### 3.3 Qian (PanAgora)
- Qian, E. (2005), "Risk Parity Portfolios: Efficient Portfolios Through True Diversification", PanAgora white paper, **Sept 2005**. https://www.panagora.com/assets/PanAgora-Risk-Parity-Portfolios-Efficient-Portfolios-Through-True-Diversification.pdf.
  - Illustrative, static and in-sample. Russell 1000 / Lehman Aggregate, 1983–2004. 60/40 gets 93% of its risk from stocks.
  - A fully invested **23% stocks / 77% bonds** portfolio equalizes risk contributions. Sharpe 0.87 vs 0.67 for 60/40.
  - The levered version, scaled to 60/40's 9.6% vol, earns 8.4% vs 6.4% excess.
  - This is a concept paper with no dynamic rule. Use it for motivation only.
- Also by Qian: "On the financial interpretation of risk contribution: risk budgets do add up", *Journal of Investment Management* (2006); "Risk Parity and Diversification", *Journal of Investing* 20(1), 2011 (https://www.panagora.com/wp-content/uploads/2012/08/JOI_Spring_2011_Panagora.pdf, not read in full). The book *Risk Parity Fundamentals* (CRC, 2016).

### 3.4 Post-publication evidence and critiques
- **Chaves, Hsu, Li & Shakernia (2011)**, "Risk Parity Portfolio vs. Other Asset Allocation Heuristic Portfolios", *Journal of Investing* 20(1), 108–118. DOI 10.3905/joi.2011.20.1.108 (Crossref-verified). SSRN 1917064. Abstract-level: RP does **not** consistently beat equal-weight or 60/40 on risk-adjusted terms. It does beat minimum-variance and mean-variance optimized portfolios.
- **Anderson, Bianchi & Goldberg (2012)**, "Will My Risk Parity Strategy Outperform?", *FAJ* 68(6), 75–93 (SSRN 2101898). Abstract-level:
  - Backtest start and end dates matter materially even over decades.
  - Transaction costs and the historical **cost of leverage can reverse the ranking**. Over an 80-year test, levered RP underperformed 60/40 after realistic financing and turnover costs.
  - Significant premiums do not guarantee outperformance over investable horizons.
- **Bond-bull-market concern:** Clare et al. (2016) cite Inker (2010, GMO), who argues that 1981+ flattered bonds. AFP respond that 1926–2010 includes a "near-perfect round trip" in yields.
- **2022 (my computation from Yahoo):** stock/bond correlation turned positive. RPAR, a levered RP ETF, returned **−22.8%** in 2022, against −18.2% for SPY, −15.6% for AOR (60/40), −15.2% for IEF and −31.2% for TLT. Equal-risk portfolios with large, long-duration bond weights did worse than 60/40 that year.
- **Portfolio-level vol targeting helps RP** (Harvey et al. 2018, §2.2): asset-level plus portfolio-level scaling raised Sharpe on 60/40-in-risk-terms from 0.80 to 0.91.

### 3.5 ETF universes and proposed implementations

**RP-A: AFP "long sample" analogue (stocks/bonds).**
- SPY + IEF. AFP's bond index is value-weighted Treasuries of all maturities, which fits IEF, IEI+IEF, or GOVT (from 2012). Proxies are VFINX and VFITX.
- 36-month monthly-excess-return vol with month-end rebalance means data from 1991-10 gives a backtest start of about **1994-10**, so 2000+ is fully covered.

**RP-B: AFP "broad sample" analogue.**
- Stocks: SPY (base; the text says global, so a variant uses VT/ACWI from 2008 or a fixed SPY/EFA/EEM blend).
- Treasuries: IEF.
- Credit: LQD, with VWESX/VFICX proxies. HYG could be added from 2007 but was not in AFP's simple mapping.
- Commodities: **GSG (same S&P GSCI index)**, with PCRIX as the proxy before 2006-07.
- The 36-month lookback with commodities starting 2002-07 gives a start of about **2005-07**. For earlier starts, (i) let commodities enter the universe only once 36 months exist, or (ii) use a 12-month lookback.

**RP-C: practitioner multi-asset (the user's list): SPY, EFA, EEM, IEF (or TLT), TIP, GLD, DBC, VNQ.**
- This goes **beyond AFP**. It is closest to MRT's "global diversified" example.
- Run both **inverse-vol (AFP rule)** and **ERC (MRT rule: 252-day daily covariance, month-end)**.
- IEF, TIP (and AGG) are highly correlated, so naive inverse-vol concentrates risk in the bond cluster. ERC corrects for this. The difference is informative.
- Earliest robust start is about 2003-07 with a 1-year lookback (commodities from PCRIX 2002-07, gold from GC=F 2000-08), or 2005-07 with 3 years.

**Unlevered versions:** weights sum to 1. Expect a portfolio vol of roughly 4–7% and a 60–85% bond weight (AFP: 85% bonds on average for stock/bond).

**Modestly levered versions (not faithful to AFP's constant-k, which is ex post):**
1. **Vol-target overlay:** gross `L_t = min(L_max, σ*/σ̂_p,t)`, with σ̂_p from the same covariance (or 20-day-HL EWMA of portfolio returns in the Harvey manner), σ* = 10% (≈ AFP broad-sample benchmark vol of 10.1%), L_max = 1.5 (or 2.0). Finance at T-bill plus a spread (Anderson et al. show this cost is decisive).
2. **Duration substitution** (an ETF-specific adaptation, not in the papers): use TLT instead of IEF to get more bond risk per dollar within 1x gross. This changes the curve exposure and should be labeled as an adaptation.
3. **Embedded leverage** (UBT, TMF, SSO): daily-reset path dependence and higher fees. Last resort.

### 3.6 Pitfalls and recommended resolutions
- **"Up to month t−1" ambiguity:** I read AFP as using the 36 months ending at the rebalance date, with no skip month. Test a one-month skip as a neighbor.
- **Excess vs total returns for σ:** AFP uses excess returns. The difference is negligible for vol.
- **Daily vs monthly vol:** AFP uses monthly (36 obs), MRT daily (≈252 obs). Given the proxy-staleness issue (§1.3), monthly or weekly is safer before ETF inception.
- **Commodity/gold data gaps** limit start dates (§1.4). Do not use ^SPGSCI returns.
- **Leverage costs** are ignored in AFP's base case. Always model them in the levered variant.
- **Correlation regime risk** (2022): report subperiods 2000–2011 (in-sample for AFP), 2012–2021, and 2022+.

### 3.7 Parameter neighbors
- Vol lookback: 12 / 24 / **36** / 60 months (monthly); 63 / 126 / **252** / 504 days (daily); EWMA HL 20 / 60 / 120 days.
- Rebalance: monthly (base) / quarterly / weekly. Drift bands of 5 / 10% relative.
- Weighting: inverse-vol vs inverse-variance vs ERC.
- Bond choice: IEF vs TLT vs AGG.
- Levered target vol: 8 / 10 / 12%. L_max: 1.25 / 1.5 / 2.0. Financing spread: 0.5 / 1.5 / 3%.

---

## 4. Minimum variance / low volatility

### 4.1 Clarke, de Silva & Thorley (2006), "Minimum-Variance Portfolios in the U.S. Equity Market"
- **Citation:** *JPM* 33(1), 10–24, Fall 2006. DOI 10.3905/jpm.2006.661366. Published 2006-10-31 (Crossref). No SSRN version found. **OOS start: 2006-11.**
- **Method (from the authors' 2011 follow-up, which says its portfolios are "similar to" 2006; the 2006 text itself was not obtained):**
  - Universe is the 1,000 largest US stocks (CRSP).
  - Covariance is a **60-month rolling window** with **Bayesian (Ledoit-Wolf 2004) shrinkage** of variances and covariances toward cross-sectional means.
  - **Monthly** optimization. **Long-only, fully invested**, no other constraints (max weights come out at about 3–4%, around 120 names).
  - The 2006 paper also used principal-components and shrinkage estimators (secondary sources; not verified).
- **Results:**
  - 2006, per a secondary summary: 1968–2005, MV vol about three-quarters of the market's (≈11.7% vs 15.4%) with comparable or higher return.
  - 2011 (verified): 1968–2009, MV excess return 5.37% vs 4.88% market. Vol **11.90% vs 15.56%**. Sharpe **0.45 vs 0.31**. β 0.66. α 2.17%. Information ratio 0.35.
  - 2011 citation: *JPM* 37(2), 31–45; SSRN 1549949. PDF: https://www.hillsdaleinv.com/uploads/Minimum-Variance_Portfolio_Composition,_Roger_Clarke,_Harindra_de_Silva,_Steven_Thorley.pdf.
- **Mechanism (2011):** 80–90% of long-only MV names are low-**beta** stocks. The effect is a stock-level low-beta tilt.

### 4.2 Frazzini & Pedersen (2014), "Betting Against Beta"
- **Citation:** *JFE* 111(1), 1–25. DOI 10.1016/j.jfineco.2013.10.005. NBER w16601 (Dec 2010). The JFE received it 2010-12-16. PDF: https://pages.stern.nyu.edu/~afrazzin/pdf/Betting%20Against%20Beta%20-%20Frazzini%20and%20Pedersen.pdf. **OOS start: 2011-01.**
- **Rule (published version):**
  - β̂ = ρ̂ · σ̂_i / σ̂_m. Volatility is a **1-year rolling std of daily log returns**. Correlation uses **5-year overlapping 3-day log returns**. At least 120 or 750 days are required.
  - Shrink `β = 0.6·β̂_TS + 0.4·1`.
  - Rank each month into low and high groups, **rank-weighted**. **Lever the low-beta leg and de-lever the high-beta leg to β = 1 each**, then take long low minus short high.
  - The US stock BAB averages about $1.5 long and $0.7 short (2010 WP numbers).
  - The NBER 2010 draft used a Dimson-lag regression with shrink weight 0.5. **The published version differs.**
- **Results:** US equity BAB Sharpe **0.78** (1926–Mar 2012). Positive in 18 of 19 developed markets, in Treasuries (Sharpe 0.81) and credit. BAB exists across asset classes.
- **ETF verdict: not faithfully implementable.** It requires shorting and leverage by design. A long-only low-beta basket keeps only half the trade and none of the beta-neutral leverage.

### 4.3 Ang, Hodrick, Xing & Zhang (2006), "The Cross-Section of Volatility and Expected Returns"
- **Citation:** *JF* 61(1), 259–299. DOI 10.1111/j.1540-6261.2006.00836.x. NBER w10852 (Oct 2004). SSRN 681343. **OOS start: 2004-11.**
- **Rule:** monthly value-weighted quintiles on **idiosyncratic volatility relative to the FF3 model from the prior month's daily returns**, held one month. Separately, quintiles on the sensitivity to ΔVIX, from past-month daily regressions.
- **Results:** highest-minus-lowest IVOL quintile **−1.06%/month** (1963–2000). The ΔVIX-beta spread is −1.04%/month (1986–2000).
- **ETF verdict: not implementable.** It is a stock-level cross-sectional long-short strategy.

### 4.4 Supporting evidence for an industry/sector-level version
- **Asness, Frazzini & Pedersen (2014)**, "Low-Risk Investing without Industry Bets", *FAJ* 70(4), 24–41. DOI 10.2469/faj.v70.n4.1. PDF: https://www.aqr.com/-/media/AQR/Documents/Insights/Journal-Article/FAJ-LowRisk-Investing-Without-Industry-Bets.pdf.
  - A pure **industry BAB** (long-short across industry portfolios) earned positive returns, 1926–2012 US and 1986–2012 global.
  - **Industry-neutral BAB had the higher Sharpe.** Most of the low-risk premium is within industries, which ETFs cannot access.
- **DeMiguel, Garlappi & Uppal (2009)** (§5.3) include a constrained minimum-variance ("min-c", Jagannathan-Ma 2003 long-only) strategy on an "**S&P Sectors**" dataset: 10 S&P 500 sector portfolios plus the market, 1981–2002, rolling 120-month covariance, monthly.
  - Of the 14 models, min-c performed best on Sharpe but was **not statistically better than 1/N** in any dataset, and had higher turnover.
- **MRT (2010)** US-sectors example (§3.2): MV Sharpe 0.77 vs 0.62 for 1/N, 1973–2008 (1-year daily covariance, monthly).

### 4.5 Honest ETF-level options
| Option | Rule | Faithful to | Not faithful to |
|---|---|---|---|
| **MV-S: long-only min-variance across 9 Select Sector SPDRs** (XLB XLE XLF XLI XLK XLP XLU XLV XLY; data from 1998-12-22) | Month-end; covariance from 252 daily returns (MRT) **or** 60 monthly returns with Ledoit-Wolf shrinkage to the constant-correlation / cross-sectional mean (CST-style estimator); long-only, fully invested; optional 35–40% single-sector cap (an adaptation) | MRT sector example; DGU "S&P Sectors" min-c | **CST 2006** (stock-level, 1,000 names), BAB |
| **MV-A: long-only min-variance across asset classes** (SPY, EFA, EEM, IEF, TIP, GLD, DBC, VNQ) | Same | MRT global example | Nothing equity-specific. It will be about 70–90% short or intermediate bonds (MRT MV vol was only 3.2%), so it is largely a bond portfolio when unlevered |
| **LV-P: hold SPLV or USMV** | Product. The S&P 500 Low Volatility Index takes the 100 lowest 252-day-vol S&P 500 stocks, weights by inverse vol, and rebalances quarterly (index methodology, https://www.spglobal.com/spdji/en/documents/methodologies/methodology-sp-low-volatility-indices.pdf) | The low-vol stock-level effect (closest to CST/AHXZ in spirit) | Only from 2011. No Yahoo proxy for the index history. A stock-level reconstruction on Alpaca data would suffer from survivorship bias |
| **BAB-lite: long-only low-beta sectors** (e.g., the three lowest 1-year beta sectors, inverse-beta weighted) | Adaptation | Direction of AFP 2014 industry BAB | Missing the levered long and the short leg. Expect a defensive tilt, not BAB returns |

**Recommendation.** Use **MV-S** as the minimum-variance representative. Label it "sector-level min-variance (DGU/MRT style)", not "Clarke-de Silva-Thorley". Use LV-P only as a post-2011 reference series.

### 4.6 Pitfalls
- With only 9 assets, unconstrained long-only MV concentrates in XLP, XLU and XLV, and turnover spikes when correlations shift. Weight caps and shrinkage are necessary judgment calls. Report the uncapped version too.
- XLRE (2015) and XLC (2018) were carved out of XLF, XLK and XLY. Keep the 9-sector universe for consistency, and treat a variant that adds them as they appear as secondary.
- Sample covariance with 60 monthly observations and 9 assets is fine. For larger universes, shrinkage is needed.

### 4.7 Parameter neighbors
- Covariance window: 126 / **252** / 504 days; 36 / **60** / 120 months.
- Shrinkage intensity: 0 / Ledoit-Wolf optimal / 0.5.
- Max weight: none / 40% / 30% / 25%.
- Rebalance: monthly / quarterly.
- Return frequency for covariance: daily vs weekly.

---

## 5. Static benchmarks

### 5.1 60/40
- **Convention in the RP literature (AFP 2012, Table 2 notes):** 60% stocks / 40% bonds, **rebalanced monthly** to constant weights. Bonds are US Treasuries (CRSP).
- **Tickers:** SPY/IEF (AFP-faithful, Treasuries). SPY/AGG (industry standard, VBINX-like). Proxies are VFINX / VFITX / VBMFX.
- Sanity-check against VBINX (from 1992-09-28, 60% total stock / 40% total bond) and AOR (from 2008-11-19).
- **Reported:** 1926–2010: excess return 4.65%, vol 11.68%, Sharpe 0.40 (AFP).
- **Neighbors:** monthly / quarterly / annual rebalance; 5% threshold rebalance; IEF vs AGG vs TLT.

### 5.2 Harry Browne Permanent Portfolio
- **Sources:** Harry Browne, *Why the Best-Laid Investment Plans Usually Go Wrong* (1987) and *Fail-Safe Investing* (St. Martin's, 1999).
  - These are books, not peer-reviewed. The rule predates the whole sample, so everything is effectively "OOS".
  - I did not read the books. Details come from the Wikipedia summary (https://en.wikipedia.org/wiki/Fail-Safe_Investing) and secondary summaries (e.g., https://www.getrichslowly.org/fail-safe-investing-harry-brownes-permanent-portfolio/).
- **Rule:** 25% US stocks (Browne named S&P 500 index funds such as VFINX), 25% **long-term** US Treasuries, 25% gold (bullion coins), 25% cash (T-bills).
  - **Rebalance:** secondary sources describe an annual review, plus rebalancing back to 25% if any sleeve falls **below 15% or rises above 35%**. Wikipedia describes annual rebalancing. Treat the bands as secondary-source only.
- **Tickers:** SPY or VTI / TLT / GLD (or IAU/GLDM) / BIL (or SGOV/SHV). Proxies: VFINX (VTSMX) / VUSTX / GC=F / ^IRX accrual.
  - **Earliest start is 2000-09** because gold begins on 2000-08-30.
  - Do not use PRPFX as a stand-in: it is a different allocation.
- **Recommended conventions:**
  - (a) Annual rebalance on the first trading day of January.
  - (b) A 15/35 band check at each daily close, with the fill at the next open.
  - (c) Monthly rebalance, to put it on the same footing as the other baselines.

### 5.3 1/N (DeMiguel, Garlappi & Uppal 2009)
- **Citation:** "Optimal Versus Naive Diversification: How Inefficient is the 1/N Portfolio Strategy?", *Review of Financial Studies* 22(5), 1915–1953, May 2009. DOI 10.1093/rfs/hhm075. SSRN 1376199 (RFS version).
  - Earlier: "How Inefficient is the 1/N Asset-Allocation Strategy?", CEPR DP 5142 / SSRN 785164 (July 2005).
  - The June-2006 draft states "**First draft: March 2005**" (https://users.nber.org/~confer/2006/si2006/ap/uppal.pdf). **OOS start: 2005-04.**
- **Rules (2006 draft §3):**
  - Rolling estimation window **M = 120 months** (M = 60 gives similar results); expanding windows were also similar.
  - Weights are set each month and applied to month t+1. **1/N is rebalanced monthly** back to equal weights. A buy-and-hold 1/N gave similar results, but it is sensitive to its start date and is not reported.
  - Out-of-sample Sharpe uses excess returns over T-bills. Turnover and a 50 bp proportional cost are reported in the RFS version (from memory; not verified in the draft).
- **Datasets:** "S&P Sectors" (10 sector portfolios plus market, 1981–2002), 10 industries plus market, 8 MSCI countries plus World, MKT/SMB/HML, and Fama-French size/BM portfolios with factors.
- **Result:** none of the 14 optimizing models is consistently better than 1/N in Sharpe, CEQ or turnover. For S&P Sectors, the out-of-sample monthly Sharpe of 1/N is **0.1876** (≈0.65 annualized). The critical estimation window for sample mean-variance to beat 1/N is about 3,000 months for 25 assets.
- **ETF versions:**
  - **1/N-S:** 9 Select Sector SPDRs equal-weight, monthly (the S&P Sectors analogue; from 1999-01).
  - **1/N-MA:** equal weight over the same multi-asset universe used for RP and trend, so each risk-based method has a matched naive control. Examples: Faber's 5 (SPY, EFA, IEF, GSG/DBC, VNQ) or the 8-asset RP-C set.
- **Neighbors:** monthly / quarterly / annual rebalance; drift bands.

---

## 6. Trend plus risk parity combination

### 6.1 Clare, Seaton, Smith & Thomas (2016), "The trend is our friend: Risk parity, momentum and trend following in global asset allocation"
- **Citation:** *Journal of Behavioral and Experimental Finance* 9, 63–80. DOI 10.1016/j.jbef.2016.01.002. Received 2015-09-02, online 2016-01-15. SSRN 2126478 (originally posted 2012 per snippet; later version dated 2015-07-31). PDF used: https://www.wmcapitalmanagement.com/wp-content/uploads/2018/08/Trend-is-your-friend.pdf (the published article).
- **First public:** SSRN 2012 (month not verified). **OOS start: 2012-09 for the concept, 2016-01 for the published sample (it ends 2015).**
- **Data:** five broad total-return indices, 1994–2015:
  - MSCI World (developed equities)
  - MSCI Emerging Markets
  - Citigroup World Government Bond Index (its 2.99% vol suggests a USD-hedged version; not stated in the section I read)
  - DJ-UBS Commodity (now BCOM)
  - FTSE/EPRA Global REIT
  - Sub-component data (95 markets) was used for within-class tests.
- **Rules (§3.1, verbatim logic):**
  - **Trend filter (Faber 2007):** at each **month-end**, an asset is "in trend" if price > its **10-month simple moving average** (6, 8 and 12 months also tested). Otherwise its allocation goes to **US 3-month T-bills**. No shorting. **No transaction costs deducted.**
  - **Risk parity:** "following Asness et al.", weights are proportional to **inverse volatility computed from one year of data**, recalculated monthly. The return frequency for the vol estimate is not stated in the section read.
  - **RPTF:** risk-parity weights, with the RP weight of any asset below its 10-month SMA moved to T-bills.
  - **Rebalance monthly.**
- **Results (Table 1, 1994–2015):**

  | Portfolio | Return | Vol | Sharpe | MDD |
  |---|---|---|---|---|
  | Equal weight 20% × 5 | 6.61% | 12.09% | 0.33 | 46.6% |
  | EW + TF (6/8/10/12-month) | 7.45–8.09% | about 6.7% | 0.72–0.80 | 6.9–11.7% |
  | Risk parity | 6.59% | 5.91% | 0.67 | 20.5% |
  | **RP + TF (10-month)** | **6.92%** | **4.05%** | **1.06** | **4.9%** |

  Momentum (top half or quarter by 12-month return within classes) combined with TF was also strong (Tables 5–6).
- **Faber (2007)**, "A Quantitative Approach to Tactical Asset Allocation", *Journal of Wealth Management* 9(4), 69–79. SSRN 962461 (https://papers.ssrn.com/sol3/papers.cfm?abstract_id=962461; PDF https://mebfaber.com/wp-content/uploads/2016/05/SSRN-id962461.pdf).
  - This is the trend-rule source: month-end price vs 10-month SMA, with the alternative being T-bills.
  - Its universe is S&P 500, MSCI EAFE, US 10-year Treasuries, GSCI and NAREIT, which maps cleanly to SPY, EFA, IEF, GSG/DBC and VNQ.

### 6.2 ETF mapping for a faithful replication
| Clare asset | Preferred ETF (inception) | Pre-inception proxy | Comment |
|---|---|---|---|
| MSCI World | URTH (2012-01) | Before 2012: fixed SPY/EFA blend (e.g., 60/40, rebalanced monthly); proxies VFINX/VTMGX | Or simplify to SPY (US-centric variant) |
| MSCI EM | EEM (2003-04) | VEIEX (1994) | |
| Citi WGBI | IEF (2002-07) or BWX (2007-10, unhedged); BNDX (2013, hedged) | VFITX | US Treasuries are the practical choice. Hedged global has lower vol (2.99% in the paper) |
| DJ-UBS / BCOM | DJP (2006-10, an ETN) / BCI (2017) | PCRIX (2002-07) | DBC or GSG are acceptable alternatives with different index rules |
| FTSE EPRA Global REIT | RWO (2008-05) / REET (2014) | VGSIX (US only) | US-only VNQ is the simplest |
| T-bills | BIL (2007-05) / SGOV | ^IRX accrual | |

- **Earliest robust start:** commodities from PCRIX 2002-07. A 12-month vol and 10-month SMA need about 12 months, giving **about 2003-07**.
- The Faber-5 US mapping (SPY, EFA, IEF, DBC/GSG, VNQ) supports the same start.
- If commodities are dropped until available, a 4-asset version can start around 2000.

### 6.3 Pitfalls and resolutions
- **Signal price:** Faber and Clare use month-end index levels (price or total return is not clearly stated in the part read). Use the **adjusted close** (total return) for both SMA and signal, and test raw close as a neighbor.
- **Timing:** signal at month-end close, fill next open. The papers implicitly trade at the month-end close.
- **Costs:** none are deducted in the paper. Add ETF spread costs; turnover is moderate (monthly, binary switches).
- **Vol frequency ambiguity:** "one year's worth of data". Use 12 monthly returns as the base (with index data that is most likely) and 252 daily returns as the neighbor.
- **Sample is 1994–2015**, a period favorable to bonds. Report 2016+ separately as OOS.

### 6.4 Parameter neighbors
- SMA: 6 / 8 / **10** / 12 months. Alternatively, sign of 12-month excess return (time-series momentum).
- RP vol window: 6 / **12** / 36 months.
- Risk-off asset: BIL vs SHY vs IEF.
- Universe: Clare-5 vs Faber-5 vs RP-C 8.
- Add a portfolio-level vol target (Harvey-style) as a "trend + vol" variant, labeled as a combination not in Clare et al.

---

## 7. Other well-supported, ETF-implementable additions (brief)
- **Fleming, Kirby & Ostdiek (2001)**, "The Economic Value of Volatility Timing", *JF* 56(1), 329–352 (abstract via RePEc).
  - Conditional mean-variance allocation across **stocks, bonds, gold and cash**, rebalanced daily using rolling covariance estimates. It "outperform[s] the unconditionally efficient static portfolios… robust to estimation risk and transaction costs".
  - Maps to SPY / TLT or IEF / GLD / BIL. The rules in the full text (estimator decay and target) were not verified.
- **Kirby & Ostdiek (2012)**, "It's All in the Timing: Simple Active Portfolio Strategies that Outperform Naive Diversification", *JFQA* 47(2), 437–467. DOI 10.1017/S0022109012000117 (Crossref-verified). SSRN 1530022.
  - "Volatility timing" weights `w_i ∝ (1/σ²_i)^η` with a tuning parameter η (η = 0 gives 1/N, η = 1 inverse variance) to control turnover. Reported to beat 1/N even with high costs (abstract-level).
  - The exact η grid and windows were not verified. Treat it as a neighbor family for RP-C: η ∈ {0, 0.5, 1, 2, 4}.
- **Time-series momentum with vol scaling** (Moskowitz, Ooi & Pedersen 2012, JFE) is futures-based and long-short. A long-only ETF adaptation is essentially §6. Not researched further here.

---

## 8. Cross-cutting implementation conventions (recommended defaults for the harness)
1. **Month-end strategies:** compute signals with data through the last trading day's close, and fill at the **next open** (the first trading day of the new month). Also report next-close fills. Papers assume a same-close fill, so a one-day lag is a conservative deviation.
2. **Daily strategies (VM-3):** signal at close t, fill at open t+1. Harvey et al. use an extra day of lag, which roughly matches this.
3. **Cash** = BIL, or ^IRX accrual before 2007-05-30. SGOV is a cheaper post-2020 alternative.
4. **Leverage:**
   - Model borrowing at ^IRX plus a spread, since Alpaca margin interest applies (check the current rate; test 0.5–3%).
   - Reg-T overnight buying power is 2x.
   - Any modestly levered variant should cap gross at 1.5x, consistent with Moreira-Muir's "standard margin" cap.
5. **Transaction costs:** papers mostly assume 0–1 bp (Harvey et al. 1 bp; MM 1/10/14 bp scenarios; Clare 0). For ETFs, use a per-side half-spread of about 1 bp (SPY/IEF) to 5–10 bp (EEM, DBC, sector SPDRs in stress) as a sensitivity. **This range is my suggestion, not taken from the papers.**
6. **OOS reporting:** split results at each strategy's OOS start (§0.1). Also report 2000–2007, 2008–2009, 2010–2021 and 2022+ to expose the bond-regime dependence of RP.
7. **Survivorship:** all strategies here use indices or ETFs, so there is no stock-level survivorship issue. Do not try to rebuild CST or SPLV from Alpaca's current stock list.

---

## 9. Reference list (with URLs)
- Moreira, A., Muir, T. (2017). Volatility-Managed Portfolios. *JF* 72(4):1611–1644. https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12513 ; NBER w22208 https://www.nber.org/papers/w22208 ; SSRN https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2659431
- Harvey, C., Hoyle, E., Korgaonkar, R., Rattray, S., Sargaison, M., Van Hemert, O. (2018). The Impact of Volatility Targeting. *JPM* 45(1):14–33. https://people.duke.edu/~charvey/Research/Published_Papers/P135_The_impact_of.pdf ; SSRN https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3175538
- Cederburg, S., O'Doherty, M., Wang, F., Yan, X. (2020). On the performance of volatility-managed portfolios. *JFE* 138(1):95–117. https://www.sciencedirect.com/science/article/abs/pii/S0304405X2030132X ; https://www.lehigh.edu/~xuy219/research/COWY.pdf ; SSRN https://www.ssrn.com/abstract=3357038
- Liu, F., Tang, X., Zhou, G. (2019). Volatility-Managed Portfolio: Does It Really Work? *JPM* 46(1):38–51. https://jpm.pm-research.com/content/46/1/38 ; SSRN https://www.ssrn.com/abstract=3283395
- Barroso, P., Detzel, A. (2021). Do limits to arbitrage explain the benefits of volatility-managed portfolios? *JFE* 140(3):744–767. https://econpapers.repec.org/article/eeejfinec/v_3a140_3ay_3a2021_3ai_3a3_3ap_3a744-767.htm ; SSRN https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3088828
- Bongaerts, D., Kang, X., van Dijk, M. (2020). Conditional Volatility Targeting. *FAJ* 76(4):54–71. https://repub.eur.nl/pub/130215/Bongaerts-Kang-van-Dijk-Conditional-volatility-targeting-2020-FAJ.pdf ; SSRN https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3636727
- DeMiguel, V., Martín-Utrera, A., Uppal, R. (2024). A Multifactor Perspective on Volatility-Managed Portfolios. *JF* 79(6):3859–3891. https://onlinelibrary.wiley.com/doi/full/10.1111/jofi.13395
- Asness, C., Frazzini, A., Pedersen, L. H. (2012). Leverage Aversion and Risk Parity. *FAJ* 68(1):47–59. https://www.aqr.com/-/media/AQR/Documents/Insights/Journal-Article/Leverage-Aversion-and-Risk-Parity.pdf ; SSRN https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1990493
- Maillard, S., Roncalli, T., Teiletche, J. (2010). The Properties of Equally Weighted Risk Contribution Portfolios. *JPM* 36(4):60–70. http://www.thierry-roncalli.com/download/erc.pdf ; SSRN https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1271972
- Griveau-Billion, T., Richard, J.-C., Roncalli, T. (2013). A Fast Algorithm for Computing High-dimensional Risk Parity Portfolios. https://arxiv.org/pdf/1311.4057
- Qian, E. (2005). Risk Parity Portfolios: Efficient Portfolios Through True Diversification. PanAgora. https://www.panagora.com/assets/PanAgora-Risk-Parity-Portfolios-Efficient-Portfolios-Through-True-Diversification.pdf ; Qian (2011) Risk Parity and Diversification, *J. of Investing* 20(1). https://www.panagora.com/wp-content/uploads/2012/08/JOI_Spring_2011_Panagora.pdf
- Chaves, D., Hsu, J., Li, F., Shakernia, O. (2011). Risk Parity Portfolio vs. Other Asset Allocation Heuristic Portfolios. *J. of Investing* 20(1):108–118. https://www.ssrn.com/abstract=1917064
- Anderson, R., Bianchi, S., Goldberg, L. (2012). Will My Risk Parity Strategy Outperform? *FAJ* 68(6):75–93. https://www.ssrn.com/abstract=2101898
- Clarke, R., de Silva, H., Thorley, S. (2006). Minimum-Variance Portfolios in the U.S. Equity Market. *JPM* 33(1):10–24. DOI 10.3905/jpm.2006.661366 ; (2011) Minimum-Variance Portfolio Composition, *JPM* 37(2):31–45. https://www.hillsdaleinv.com/uploads/Minimum-Variance_Portfolio_Composition,_Roger_Clarke,_Harindra_de_Silva,_Steven_Thorley.pdf
- Frazzini, A., Pedersen, L. H. (2014). Betting Against Beta. *JFE* 111(1):1–25. https://pages.stern.nyu.edu/~afrazzin/pdf/Betting%20Against%20Beta%20-%20Frazzini%20and%20Pedersen.pdf ; NBER w16601 https://www.nber.org/papers/w16601
- Asness, C., Frazzini, A., Pedersen, L. H. (2014). Low-Risk Investing without Industry Bets. *FAJ* 70(4):24–41. https://www.aqr.com/-/media/AQR/Documents/Insights/Journal-Article/FAJ-LowRisk-Investing-Without-Industry-Bets.pdf
- Ang, A., Hodrick, R., Xing, Y., Zhang, X. (2006). The Cross-Section of Volatility and Expected Returns. *JF* 61(1):259–299. https://onlinelibrary.wiley.com/doi/10.1111/j.1540-6261.2006.00836.x ; NBER w10852 https://www.nber.org/papers/w10852
- DeMiguel, V., Garlappi, L., Uppal, R. (2009). Optimal Versus Naive Diversification. *RFS* 22(5):1915–1953. https://academic.oup.com/rfs/article-abstract/22/5/1915/1592901 ; 2006 draft https://users.nber.org/~confer/2006/si2006/ap/uppal.pdf ; SSRN (2005) https://papers.ssrn.com/sol3/papers.cfm?abstract_id=785164
- Clare, A., Seaton, J., Smith, P., Thomas, S. (2016). The trend is our friend. *JBEF* 9:63–80. https://www.sciencedirect.com/science/article/abs/pii/S2214635016000083 ; SSRN https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2126478
- Faber, M. (2007). A Quantitative Approach to Tactical Asset Allocation. *J. Wealth Management* 9(4):69–79. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=962461
- Fleming, J., Kirby, C., Ostdiek, B. (2001). The Economic Value of Volatility Timing. *JF* 56(1):329–352. https://ideas.repec.org/a/bla/jfinan/v56y2001i1p329-352.html
- Kirby, C., Ostdiek, B. (2012). It's All in the Timing. *JFQA* 47(2):437–467. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1530022
- Browne, H. (1999). *Fail-Safe Investing*. Summary: https://en.wikipedia.org/wiki/Fail-Safe_Investing
- S&P Dow Jones Indices, S&P Low Volatility Indices Methodology. https://www.spglobal.com/spdji/en/documents/methodologies/methodology-sp-low-volatility-indices.pdf
