# Trend-Following & Momentum Strategies — Research Dossier for an ETF / Daily-Bar Harness

Prepared 2026-09-25. Scope: reputable-source trend-following (time-series momentum) and cross-sectional momentum strategies that can be run on split+dividend-adjusted daily OHLCV of US-listed ETFs (Alpaca-tradeable), deciding at the close and executing next open/close, long-only and ≤1x gross preferred.

**How to read this document**

- "VERIFIED" means I read it in the primary source (paper PDF text, a figure image extracted from the paper, or the SSRN abstract page via the Internet Archive), or I queried it directly (Yahoo inception dates).
- "SECONDARY" means the fact comes from a co-author's blog, an authorized summary (CXO Advisory, AllocateSmartly), or similar. I could not get the primary PDF.
- "NOT VERIFIED" is stated explicitly wherever I could not confirm a detail.
- SSRN blocks direct fetching (HTTP 403). I got SSRN posting dates from Internet Archive snapshots of the abstract pages. Those dates are VERIFIED unless noted.
- Keller & Keuning PDFs (PAA/VAA/DAA) could not be downloaded: SSRN, ResearchGate and S3 mirrors all returned 403/AccessDenied. Their rules below come from the co-author's (J.W. Keuning's) TrendXplorer blog posts, CXO Advisory and AllocateSmartly. These are labeled SECONDARY.

---

## 0. Summary table

| # | Strategy | Primary source | First public date | Suggested OOS start | Signal | Long-only as published? |
|---|---|---|---|---|---|---|
| 1a | TSMOM (MOP) | Moskowitz, Ooi & Pedersen, JFE 2012 | JFE received 16 Aug 2010; AFA Jan 2011; JFE online 11 Dec 2011; SSRN 23 Jun 2012 | 2012-01 (sample ends 2009-12) | sign of 12-mo excess return, vol-scaled to 40%/asset | No (long/short futures, levered) |
| 1b | Trend 1/3/12 (HOP) | Hurst, Ooi & Pedersen, JPM 2017 (AQR WP Fall 2012) | AQR white paper Fall 2012 (data to Jun 2012) | 2012-07 | equal-wt 1, 3, 12-mo sign signals, 10% portfolio vol target | No |
| 2 | GTAA / QTAA (10-mo SMA) | Faber, J. Wealth Mgmt 2007; 2013 update; JPM 2018 | Draft May 2006 (data to 2005); SSRN 11 Feb 2007 | 2006-01 (Faber's own OOS split) | month-end price > 10-mo SMA → hold, else T-bills | Yes |
| 3 | Dual Momentum / GEM | Antonacci SSRN 2012, 2013; book 21 Nov 2014 | RPH SSRN 19 Apr 2012; GEM rules in book Nov 2014 | 2014-12 (GEM) / 2013-01 (AbsMom) | 12-mo return: US vs T-bill (abs), US vs ex-US (rel), else bonds | Yes |
| 4 | Industry/sector momentum | Moskowitz & Grinblatt JF 1999; Jegadeesh & Titman JF 1993 | JF Aug 1999 (sample Jul 1963–Jul 1995) | entire sector-ETF era is OOS | rank sectors on 6-mo (MG) or 12-1 (JT/AMP) return, hold top 3 | No (long/short); long side carries most of it |
| 5 | PAA / VAA / DAA | Keller & Keuning, SSRN 2016/2017/2018 | 8 Apr 2016 / 19 Jul 2017 / 1 Aug 2018 | 2016-01 / 2017-07 / 2018-04 | SMA12 momentum (PAA), 13612W (VAA/DAA); breadth/canary crash protection | Yes |
| 6 | Adaptive Asset Allocation | Butler, Philbrick, Gordillo (+Varadi), 2012 | GestaltU blog May 2012; SSRN 21 Sep 2013 | 2012-06 | top 5 of 10 by 6-mo return, minimum-variance weights | Yes |
| 7 | Value & Momentum Everywhere (momentum leg) | Asness, Moskowitz & Pedersen JF 2013 | SSRN 20 Mar 2009; final sample to Jul 2011 | 2011-08 | 12-1 month return ranks within asset class | No (long/short); long-only = top tercile |

---

## 0.1 Cross-cutting implementation conventions (apply to every strategy)

**Month-end signal and execution.** Every paper here (except AAA's daily covariance and MOP's daily vol estimate) is a monthly model: signals use month-end total-return values, and the portfolio is re-formed monthly.

- Faber states: "All entry and exit prices are on the day of the signal at the close. The model is only updated once a month on the last day of the month" (Faber 2013 update, p. 22, VERIFIED).
- AllocateSmartly's implementations of PAA, VAA and AAA also trade at the last trading day's close. Its AAA rules were agreed with the authors.
- **Harness mapping:** compute signals on the last trading day of month *m* at the close, then trade at the next open (first trading day of *m+1*). This adds ~1 overnight gap versus the papers' same-close fills. Keep it constant across strategies. Optionally run a "next close" variant as a sensitivity check.

**Adjusted prices = total-return series.** All of these papers use total-return data: Faber says "All data series are total return series including dividends". Antonacci, Keller & Keuning, and AMP use TR indices. So compute every signal (returns, SMAs, 13612W) on the split+dividend-adjusted close, not on raw price. This matters most for bonds, REITs and HY.

**"12-month return" definition.** Use R12(t) = AdjClose(month-end t) / AdjClose(month-end t−12) − 1, i.e., 13 month-end observations.

- "12-1" (skip-month) means AdjClose(t−1)/AdjClose(t−12) − 1.
- 13612W needs month-ends t, t−1, t−3, t−6, t−12.

**Cash.**

- BIL (inception 2007-05-30) is the closest ETF to "90-day T-bills". Alternatives: SHV (2007-01-11) and SGOV (2020-06-01).
- Pre-2007, build a synthetic T-bill total-return series from Yahoo ^IRX (13-week T-bill discount yield in %, daily from 1960). A reasonable approximation is daily return ≈ (^IRX/100)/252.
- Do not use VFISX (1–3y Treasuries) as "T-bills". It has ~2y duration.

**Warm-up.** A 12-month lookback needs 13 month-ends before the first signal. Example: the sector SPDRs start 1998-12-22, so the first 12-month signal is at end-Dec 1999 and the first trade is Jan 2000.

**Mutual-fund proxy quirks (VERIFIED on Yahoo).** Mutual funds report O = H = L = C = NAV with volume 0.

- A "next open" fill on a proxy is therefore really the next day's NAV close. That is actually realistic for a mutual fund.
- International funds' NAVs can be stale relative to US close (time-zone/fair-value effects, especially pre-2003). This slightly distorts daily vol/covariance estimates.

**Time-varying universes.** MOP explicitly averages over "all the S_t securities that are available at time t" (MOP p. 236, VERIFIED). So adding assets as their data (or proxy) begins is faithful for TSMOM. For fixed-universe strategies (Faber 5/13, Keller G12, AAA-10), document any period where a sleeve is missing.

### 0.2 Verified ETF inception dates and pre-inception proxies (Yahoo, queried 2026-09-25)

`meta.firstTradeDate` from `query1.finance.yahoo.com/v8/finance/chart/TICKER`. For proxies I also checked that daily bars actually start there (period1=0 query).

"Overlap check" is my own computation on month-end adjusted closes over the full overlap window: CAGR proxy vs ETF, monthly-return correlation, and annualized tracking error.

| Exposure | ETF (inception) | Proxy on Yahoo (first daily bar) | Overlap check (proxy vs ETF) | Notes |
|---|---|---|---|---|
| S&P 500 | SPY 1993-01-29; VOO 2010-09-09 | VFINX 1980-01-02 | 10.85% vs 10.85%, ρ=0.998, TE 0.8% | excellent |
| US total mkt | VTI 2001-06-15 | VTSMX 1992-04-27 | – | |
| US small | IWM 2000-05-26 | NAESX 1980-01-02 | ρ=0.988, TE 3.1% | NAESX index changed over time (Russell 2000 → MSCI → CRSP) |
| Nasdaq-100 | QQQ 1999-03-10 | RYOCX 1994-02-14 | ρ=0.999, CAGR −1.3%/yr (fees) | |
| US LC value | IWD 2000-05-26 | VIVAX 1992-10-30 | ρ=0.986, TE 2.5% | |
| US SC value | IWN 2000-07-28 | VISVX 1998-05-21 | ρ=0.978, TE 4.1% | |
| US LC momentum | MTUM 2013-04-18 | none suitable | – | GTAA13 "US LC momentum" sleeve has no pre-2013 ETF/proxy |
| EAFE / developed ex-US | EFA 2001-08-27; VEA 2007-07-26; SPDW 2007-04-26 | VTMGX 1999-08-17 | vs EFA ρ=0.994, TE 1.8% | pre-1999: blend VEURX + VPACX (1990-06-18) |
| ACWI ex-US | VEU 2007-03-08; ACWX 2008-04-01; CWI 2007-01-17; VXUS 2011-01-28 | VGTSX 1996-04-29 | vs VEU ρ=0.998, TE 1.2% | |
| Europe | VGK 2005-03-10; IEV 2000-07-28; EZU 2000-07-31 | VEURX 1990-06-18 | vs VGK ρ=0.998 | |
| Japan | EWJ 1996-03-18 | (VPACX 1990-06-18) | vs EWJ ρ=0.942, TE 5.9% | VPACX includes Australia/HK; weak proxy — prefer starting at EWJ inception |
| EM | VWO 2005-03-10; EEM 2003-04-14 | VEIEX 1994-05-04 | vs VWO ρ=0.992, TE 2.5% | |
| US REITs | VNQ 2004-09-29; IYR 2000-06-19 | VGSIX 1996-05-13; FRESX 1986-11-14 (active) | VGSIX vs VNQ ρ=0.999 | |
| Intl REITs | RWX 2006-12-19 | FIREX 2004-09-09 (active) | ρ=0.961, TE 5.4% | nothing on Yahoo before 2004 |
| 7–10y UST | IEF 2002-07-30 | VFITX 1991-10-28 | ρ=0.982, TE 2.2% | |
| 20+y UST | TLT 2002-07-30 | VUSTX 1986-05-19 | ρ=0.992, TE 2.3% | |
| 1–3y UST | SHY 2002-07-30 | VFISX 1991-10-28 | ρ=0.962, TE 0.5% | |
| US Agg | AGG 2003-09-29; BND 2007-04-10 | VBMFX 1986-12-11 | vs AGG ρ=0.978, TE 0.9% | |
| IG corporate | LQD 2002-07-30 | VFICX 1993-10-29; VWESX 1980-01-02 | ρ≈0.92, TE 3.6–4.5% | VWESX is longer duration than LQD |
| High yield | HYG 2007-04-11 | VWEHX 1980-01-02 | ρ=0.906, TE 4.4% | VWEHX is higher quality than HYG |
| TIPS | TIP 2003-12-05 | VIPSX 2000-06-29 | ρ=0.993 | |
| Intl govt bonds | BWX 2007-10-11 | RPIBX 1986-09-10 (unhedged) | ρ=0.978, TE 1.9% | PFORX is USD-hedged — do not use (ρ=0.55) |
| Broad commodities | DBC 2006-02-06; GSG 2006-07-21; PDBC 2014-11-07 | PCRIX 2002-07-01 | vs DBC ρ=0.907, TE 8.1% | PCRIX is active (BCOM + TIPS collateral). **No usable commodity TR proxy on Yahoo before 2002-07** |
| Gold | GLD 2004-11-18; IAU 2005-01-28 | GC=F 2000-08-30 (front-month futures, price only) | ρ=0.992, TE 2.2% | continuous futures has roll seams |
| T-bills | BIL 2007-05-30; SHV 2007-01-11; SGOV 2020-06-01 | ^IRX 1960 (yield, not price) | – | build synthetic TR |
| Sector SPDRs | XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY: 1998-12-22; XLRE 2015-10-08; XLC 2018-06-19 | XLRE ← IYR/VNQ; XLC ← VOX (2004-09-29) / IYZ (2000-05-26) | – | see §4 pitfalls |
| Country ETFs (AMP universe) | EWA, EWO, EWK, EWC, EWQ, EWG, EWH, EWI, EWJ, EWN, EWP, EWD, EWL, EWU: all 1996-03-18; EDEN 2012-01-26; ENOR 2012-01-24; Portugal (PGAL) not on Yahoo (delisted); US = SPY | – | – | |

**Do NOT use these proxies:**

- **^SPGSCI.** It is a spot/price index, not total return. Over 2007–2009 ^SPGSCI returned +21% while GSG returned −21%. Over 2022–2024 it returned −2% vs GSG +27% (my check). This is because roll yield and collateral are missing.
- **FSAGX / VGPMX as gold proxies.** These are gold-miner equity funds, and VGPMX is now "Global Capital Cycles".
- **PFORX for BWX.** It is USD-hedged.

---

## 1. Time-Series Momentum / Trend Following

### 1a. Moskowitz, Ooi & Pedersen (2012), "Time Series Momentum"

**Citation.** Moskowitz, T.J., Ooi, Y.H., Pedersen, L.H. (2012). "Time series momentum." *Journal of Financial Economics* 104(2), 228–250. DOI 10.1016/j.jfineco.2011.11.003.

- PDF: https://w4.stern.nyu.edu/facdir/lpederse/papers/TimeSeriesMomentum.pdf
- SSRN: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2089463

**Dates (VERIFIED).**

- Received 16 Aug 2010; revised 11 Jul 2011; accepted 12 Aug 2011; available online 11 Dec 2011. The acknowledgements mention the 2011 AFA meetings in Denver.
- SSRN posting 23 Jun 2012 ("Date Written: September 1, 2011").
- Sample Jan 1985–Dec 2009, with data back to 1965.
- **OOS recommendation:** 2012-01 onward, the first month after journal online publication. 2010–2011 is post-sample but pre-publication.

**Data.** 58 futures/forwards: 24 commodities, 12 cross-currency pairs (9 currencies), 9 developed equity indexes and 13 developed government bond futures, Jan 1965–Dec 2009. Performance is reported mostly from 1985 onward (VERIFIED, pp. 229–232).

**Exact rules as published (VERIFIED).**

1. **Signal:** sign of the instrument's past 12-month excess return, r(t−12, t). The focal strategy has lookback k = 12 months and holding period h = 1 month ("TSMOM"). Futures returns are already excess of the financing rate. There is **no skip month**.
2. **Ex-ante volatility.** Exponentially weighted lagged squared daily returns:
   σ²_t = 261 · Σ_{i≥0} (1−δ) δ^i (r_{t−1−i} − r̄_t)²
   - r̄_t is the EWMA mean return, computed with the same weights.
   - δ is chosen so the center of mass δ/(1−δ) = **60 days**, i.e., δ = 60/61 ≈ 0.98361. In pandas this is `ewm(com=60)`.
   - The 261 factor annualizes.
   - "To ensure no look-ahead bias ... we use the volatility estimates at time t−1 applied to time-t returns."
3. **Position sizing:** each position is sized to 40% ex-ante annualized vol, so the position is 40%/σ_{t−1}. The per-instrument return is r^{TSMOM}_{t,t+1} = sign(r_{t−12,t}) · (40%/σ_t) · r_{t,t+1}.
4. **Portfolio:** equal-weighted average across all S_t instruments available at time t. The 40% choice "is inconsequential". With 40% per instrument, the diversified factor had ~12% annualized vol over 1985–2009.
5. **Rebalance:** monthly, at month-end.

**Reported performance (VERIFIED).**

- The diversified TSMOM portfolio has "a Sharpe ratio greater than one on an annual basis, or roughly 2.5 times the Sharpe ratio for the equity market portfolio" (gross, 1985–2009).
- All 58 instruments show positive 12-month TSMOM returns, and 52 are significant at 5%.
- Alpha versus MSCI World + SMB/HML/UMD is 1.58%/month (t=7.99). Versus MSCI World + AMP VAL/MOM Everywhere it is 1.09%/month (t=5.40) (Table 3, monthly).
- Returns partially reverse after ~12 months (Fig. 1 and Table 2).
- The paper notes it performed best in extreme up and down markets ("smile"), including big gains in Oct–Dec 2008.

### 1b. Hurst, Ooi & Pedersen (2017), "A Century of Evidence on Trend-Following Investing"

**Citation.** Hurst, B., Ooi, Y.H., Pedersen, L.H. (2017). "A Century of Evidence on Trend-Following Investing." *Journal of Portfolio Management* 44(1), 15–29. DOI 10.3905/jpm.2017.44.1.015.

- AQR page and PDF: https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing
- SSRN: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2993026 (posted 28 Jun 2017, VERIFIED)
- Earlier versions: AQR white paper "Fall 2012" (Jan 1903–Jun 2012) and "Fall 2014" update (Jan 1880–Dec 2013). Both VERIFIED from PDFs: https://www.trendfollowing.com/whitepaper/Century_Evidence_Trend_Following.pdf
- **OOS recommendation:** 2012-07 onward, for the 1/3/12 combined specification.

**Exact rules (VERIFIED, JPM 2017 text).**

- Universe: 67 markets (29 commodities, 11 equity indices, 15 bond markets, 12 currency pairs), 1880–2016. Cash indices financed at local short rates are used before futures exist.
- Signal: "equal-weighted combination of 1-month, 3-month, and 12-month time-series momentum strategies". For each horizon the position is long if the past excess return over that lookback is > 0, otherwise short.
- Rebalanced each month.
- "Each position is sized to target the same amount of volatility". The per-asset vol estimator is not spelled out in the 2017 text (NOT VERIFIED — presumably the MOP EWMA).
- The positions across the three strategies are aggregated and scaled "such that the combined portfolio has an annualized ex ante volatility target of 10%". Endnote 7: "We use a simple covariance matrix estimated using rolling three-year (equally weighted) monthly returns in the portfolio volatility scaling process."
- Three years of data are required to estimate vols.
- Costs are asset-class specific (2003–2016 levels; ×2 for 1993–2002; ×6 for 1880–1992). Fees are 2/20 with a high-water mark.

**Reported performance (VERIFIED, Exhibit 1 of the SSRN/JPM version; excess of T-bills).**

| Period | Gross/gross | Gross fee, net cost | Net 2/20, net cost | Vol | Sharpe (net) |
|---|---|---|---|---|---|
| 1880–2016 | 18.0% | 11.0% | 7.3% | 9.7% | 0.76 |
| 2000–2009 | 11.6% | 9.9% | 6.3% | 10.3% | 0.61 |
| 2010–2016 | 7.6% | 6.2% | 3.3% | 8.1% | 0.41 |

- Exhibit 2 gross Sharpe by signal (1880–2016): 1-mo 1.38, 3-mo 1.19, 12-mo 1.32.
- **Lagged one month** (signal computed at the end of Jan, traded at the end of Feb): 0.45 / 0.64 / 1.04. Short lookbacks are very sensitive to implementation delay, while 12-month is robust.
- Trend was positive in 8 of the 10 worst 60/40 drawdowns.

### 1c. Post-publication evidence and critiques

- **Weak 2010s (VERIFIED from HOP):** 2010–2016 net Sharpe 0.41 vs 0.76 full-sample.
  - Babu, Levine, Ooi, Schroeder & Stamelos, "You Can't Always Trend When You Want," *JPM* 46(4), 2020 (AQR: https://www.aqr.com/Insights/Research/Journal-Article/You-Cant-Always-Trend-When-You-Want) attribute the weak decade mainly to muted market moves, not to reduced ability to profit from trends or to less diversification (SECONDARY — abstract).
- **Strong 2022:** the SG Trend Index returned +27.3% in 2022, a record (Hedgeweek: https://www.hedgeweek.com/trend-followers-turn-leaders-ctas-deliver-record-returns-2022/). In a year when stocks and bonds fell together, short positions were likely a major contributor (attribution not verified here). A long-only ETF adaptation can only go to cash in that environment.
- **Kim, Tse & Wald (2016)**, "Time series momentum and volatility scaling," *Journal of Financial Markets* 30, 103–124, DOI 10.1016/j.finmar.2016.05.003. They argue MOP's large alphas are "largely driven by volatility scaling". Unscaled TSMOM alphas are similar to unscaled buy-and-hold alphas (abstract, SECONDARY).
- **Huang, Li, Wang & Zhou (2020)**, "Time series momentum: Is it there?" *JFE* 135(3), 774–794, DOI 10.1016/j.jfineco.2019.08.004. Asset-by-asset regressions show little evidence of TSMOM predictability in- or out-of-sample, and the pooled t-stat is below bootstrap critical values. Abstract (VERIFIED via RePEc): "the TSM strategy is profitable, but its performance is virtually the same as that of a similar strategy that is based on historical sample mean and does not require predictability."
- **Hamill, Rattray & Van Hemert (2016)** (Man AHL), "Trend Following: Equity and Bond Crisis Alpha," SSRN 2831926 (posted 30 Aug 2016). Trend works both before and after 1985 and is positively skewed ("long straddle"). "Putting restrictions on the strategy to prevent it being long equities or long bonds has the potential to further enhance the crisis alpha, but reduces the average return" (VERIFIED abstract). This is relevant to long-only restrictions: removing the short side changes the payoff profile.
- **Harvey, Hoyle, Korgaonkar, Rattray, Sargaison & Van Hemert (2018)**, "The Impact of Volatility Targeting," *JPM* 45(1); SSRN 3175538.
  - Vol targeting raises Sharpe only for "risk assets" (equity, credit), is negligible for bonds/commodities/FX, but reduces tail events across all asset classes (VERIFIED abstract).
  - Vol scaling at the asset and portfolio level improves Sharpe for 60/40 and risk-parity portfolios.
- **Zakamulin (2014)**, "The real-life performance of market timing with moving average and time-series momentum rules," *J. Asset Management* 15, 261–278, DOI 10.1057/jam.2014.25. Reported timing performance usually contains considerable data-mining bias and ignores frictions. OOS tests with realistic costs are weaker (abstract, SECONDARY).

### 1d. ETF universe and long-only / unlevered adaptation (my proposal, designed to stay faithful)

**Why an adaptation is needed.**

- MOP/HOP are long/short futures. 40%/σ sizing implies ~5–8x notional in bond futures (σ ≈ 5–8%).
- With ETFs, ≤1x gross and long-only, you keep (a) the sign signal and (b) inverse-vol risk budgeting. You replace shorts with cash.
- Expect materially lower returns and loss of "crisis alpha" from shorts (e.g., short bonds in 2022, short equities in late 2008 — though long Treasuries partly captured 2008).

**Suggested universe** (multi-asset, no FX, all Alpaca-tradeable; proxies from §0.2):

- Equities: SPY, IWM, EFA (or VEA), EEM (or VWO), EWJ, VGK
- Bonds: IEF, TLT, LQD, TIP (optionally HYG)
- Real assets: VNQ, DBC (or GSG), GLD
- Cash: BIL (synthetic ^IRX before 2007)
- Following MOP, include each asset once it has ≥ 3 years of history (HOP's vol-estimation warm-up) or at least 12 months plus 60+ trading days.

**Variant A — "MOP long/flat" (primary replication).** At each month-end *t*:

1. excess12_i = R12_i(t) − R12_BIL(t)
2. s_i = 1 if excess12_i > 0 else 0 (flat instead of short)
3. σ_i = sqrt(261 · EWMA_com60 of (r_d − EWMA mean)²) on daily adjusted-close returns, using data through t (the decision is at t's close; fills at t+1 open satisfy MOP's "σ at t−1 applied to t returns").
4. Risk-budgeted base weight: b_i = (1/σ_i) / Σ_{j∈U_t} (1/σ_j) over **all** available assets U_t, not just the longs. Each asset gets an equal ex-ante risk slot, as in MOP's equal-weighted average of vol-normalized positions.
5. w_i = s_i · b_i; w_BIL = 1 − Σ w_i. Gross is ≤ 1 by construction.
6. Optional portfolio-level scaling k = min(1, 10% / σ̂_p), using a 3-year monthly covariance (HOP endnote 7). Put the remainder in BIL.

**Variant B — "HOP 1/3/12 long/flat".**

- Same as A, but s_i = (1/3)·[1{R1>rf}] + (1/3)·[1{R3>rf}] + (1/3)·[1{R12>rf}], with rf over the same horizon from BIL.
- Then apply the 10% portfolio target with a 3-year equally weighted monthly covariance, capping gross at 1.

**Pitfalls and ambiguities (with recommended resolution).**

- *Excess vs raw return:* futures returns are excess returns. For ETFs, subtract the matched-horizon T-bill return (BIL/^IRX). The difference matters when rates are 4–5% (2006–07, 2023–25).
- *Center-of-mass convention:* use δ = 60/61 (pandas `com=60`, `adjust=True` is fine after warm-up). Do not confuse it with span=60 or halflife=60.
- *Timing of σ:* use σ computed through the signal date. Never use the realized σ of the holding month.
- *Scale factor:* MOP uses 261, not 252. This is immaterial after normalization in Variant A.
- *Signal lag:* HOP shows 1- and 3-month signals degrade sharply with a one-month lag. Keep the one-day (next open) lag, not more.
- *Universe changes:* adding assets as data appear is MOP-faithful. Freezing the universe to the post-2007 ETF set gives a cleaner but shorter test.
- *Long-only bias:* in long-only form a meaningful part of any TSMOM performance comes from assets' positive unconditional drift (cf. Huang et al. 2020). Always benchmark against the same risk-budgeted portfolio **without** the trend filter (i.e., s_i ≡ 1).

**Parameter neighbors for robustness.**

- Lookbacks: 1, 3, 6, 9, 12 months; also the 1/3/12 blend.
- EWMA center of mass: 20 / 60 / 120 days.
- Portfolio vol target: 8 / 10 / 12%, or none.
- Rebalance: monthly vs weekly (MOP's h=1 month is canonical).
- Per-asset caps: none vs 25%.

---

## 2. Meb Faber — "A Quantitative Approach to Tactical Asset Allocation" (GTAA / QTAA)

**Citations (VERIFIED).**

- Faber, M.T. (2007). "A Quantitative Approach to Tactical Asset Allocation." *Journal of Wealth Management* 9(4), 69–79 (Spring 2007). DOI 10.3905/jwm.2007.674809.
  - SSRN 962461, posted **11 Feb 2007**, last revised 3 Mar 2014: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=962461
  - Title page: "May 2006, Working Paper; Spring 2007 JWM; February 2009, Update; February 2013, Update."
  - 2013 update PDF: https://mebfaber.com/wp-content/uploads/2016/05/SSRN-id962461.pdf
- Faber, M. (2018). "A Quantitative Approach to Tactical Asset Allocation Revisited 10 Years Later." *JPM* 44(2), 156–167 (Multi-Asset Special Issue 2018). DOI 10.3905/jpm.2018.44.2.156. PDF viewed: https://allocatortraining.com/wp-content/uploads/2023/06/A-Quantitative-Approach-to-Tactical-Asset-Allocation.pdf
- **OOS start:** 2006-01. Faber: "Since the paper was originally published in 2006 with results up to 2005, returns after 2005 should be seen as out of sample."

**Exact rules (VERIFIED, 2013 update p. 21–22).**

- **BUY:** "monthly price > 10-month SMA". **SELL:** "Sell and move to cash when monthly price < 10-month SMA."
- "All entry and exit prices are on the day of the signal at the close. The model is only updated once a month on the last day of the month. Price fluctuations during the rest of the month are ignored."
- "All data series are total return series including dividends, updated monthly."
- "Cash returns are estimated with 90-day Treasury bills". Leverage uses the broker call rate. Taxes and commissions are excluded.
- **GTAA (5 assets):** 20% each, and each asset is timed independently (either long or its 20% sits in T-bills). The portfolio is on average ~70% invested.

**Universe (VERIFIED from Figure images).**

| Weight | Asset | Index used by Faber | ETF | Proxy |
|---|---|---|---|---|
| 20% | US Large Cap | S&P 500 | SPY | VFINX |
| 20% | Foreign Developed | MSCI EAFE | EFA (or VEA) | VTMGX (1999); VEURX/VPACX blend earlier |
| 20% | US 10-Year Govt Bonds | GFD 10-yr | IEF | VFITX |
| 20% | Commodities | Goldman Sachs Commodity Index | GSG (closest to GSCI) or DBC | PCRIX (2002-07); none earlier |
| 20% | REITs | NAREIT | VNQ (or IYR) | VGSIX |

**GTAA 13 ("Moderate"), 2013 update (VERIFIED from the allocation table image):**

| Weight | Asset | Index | Suggested ETF (my mapping; also AllocateSmartly's) |
|---|---|---|---|
| 5% | US Large Cap Value | French-Fama | IWD (VIVAX) |
| 5% | US Large Cap Momentum | French-Fama | MTUM (2013+; no proxy) |
| 5% | US Small Cap Value | French-Fama | IWN (VISVX) |
| 5% | US Small Cap Momentum | French-Fama | no clean ETF (IWM as stand-in) |
| 10% | Foreign Developed | MSCI EAFE | EFA |
| 10% | Foreign Emerging | MSCI EEM | EEM (VEIEX) |
| 5% | US 10 Year Govt Bonds | GFD | IEF |
| 5% | Foreign 10 Year Govt Bonds | GFD | BWX (RPIBX) |
| 5% | US Corporate Bonds | GFD | LQD (VFICX) |
| 5% | US 30 Year Govt Bonds | GFD | TLT (VUSTX) |
| 10% | Commodities | GSCI | GSG / DBC |
| 10% | Commodities | Gold | GLD (GC=F from 2000-08) |
| 20% | REITs | NAREIT | VNQ |

**GTAA 13 variants (VERIFIED from the 2013 update text and tables).**

- **Conservative:** 3.75% each US equity sleeve, 7.5% EAFE/EEM, 10% each of the four bond sleeves, 7.5% GSCI, 7.5% gold, 15% REITs. Cash is in 10-year bonds.
- **Aggressive:** "selects the top six out of the thirteen assets as ranked by an average of 1, 3, 6, and 12-month total returns (momentum) ... The assets are only included if they are above their long-term moving average, otherwise that portion of the portfolio is moved to cash." Also a top-3 version. Positions are equal-weighted (1/6 or 1/3), and the ranking method is from Faber's "Relative Strength Strategies for Investing" (2010).
- **Cash alternative:** 10-year bonds instead of T-bills (+1.37%/yr for GTAA13, 1973–2012).

**Reported performance (VERIFIED from 2013-update tables, 1973–2012; Sharpe uses rf 5.41%).**

| | Return | Vol | Sharpe | MaxDD |
|---|---|---|---|---|
| B&H 5 | 9.92% | 10.28% | 0.44 | −46.00% |
| GTAA 5 | 10.48% | 6.99% | 0.73 | −9.54% |
| B&H 13 | 11.54% | 10.70% | 0.57 | −42.66% |
| GTAA 13 (Mod) | 12.04% | 7.09% | 0.94 | −10.74% |
| GTAA 13 Conservative | 12.94% | 7.42% | 1.01 | −10.72% |
| GTAA 13 Agg Top 6 | 17.76% | 11.61% | 1.06 | −23.43% |
| GTAA 13 Agg Top 3 | 19.10% | 14.82% | 0.92 | −20.29% |
| GTAA 13 with 10-yr bond cash | 13.41% | 8.14% | 0.98 | −11.90% |

**Out-of-sample (VERIFIED):**

- 2013 update, 2006–2012: GTAA 5 returned 6.01% (vol 7.27%, MaxDD −9.42%) vs B&H 3.94% (vol 14.96%, MaxDD −46%).
- JPM 2018, Exhibit 8:

| | 1972–2005 GAA | 1972–2005 QTAA | 2006–2016 GAA | 2006–2016 QTAA |
|---|---|---|---|---|
| Return | 11.51% | 11.73% | 3.51% | 4.88% |
| Vol | 8.88% | 6.84% | 12.81% | 6.55% |
| Sharpe | 0.60 | 0.81 | 0.19 | 0.59 |
| MaxDD | −19.62% | −9.54% | −46.00% | −9.45% |

- Returns roughly halved OOS, but the drawdown control held.
- Faber also shows (2013 Fig. 15; JPM Exh. 12) that MA lengths from 3 to 12 months all work similarly.

**Post-publication critiques.**

- Zakamulin (2014), cited above: data-mining bias and frictions in MA-timing studies.
- **Rebalance timing luck.** Hoffstein, Faber & Braun, "Rebalance Timing Luck: The (Dumb) Luck of Smart Beta," SSRN 3673910 (https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3673910), shows timing luck is often >100 bp/yr for monthly-rebalanced concentrated strategies. A month-end-only SMA check is exposed to this.
- The AAA authors (GestaltU 2012 post) note QTAA "has suffered recently because the dispersion of returns around monthly moving averages has increased".
- The strategy lags in V-shaped recoveries (e.g., 2009, 2020) and cannot protect when bonds and stocks fall together (2022). Cash is T-bills, so in the base model the bond sleeve simply exits.

**Pitfalls and resolutions.**

1. *SMA on total-return vs price series:* Faber used TR series, so use the adjusted close.
2. *"10-month SMA"* = the average of the last 10 month-end adjusted closes, **including** the current month-end. Signal: close_t > SMA10_t.
3. *Commodity sleeve:* GSCI (GSG) is energy-heavy. DBC and PDBC are different indices. Prefer GSG for fidelity, and treat DBC as a robustness variant. Pre-2002 there is no usable proxy. Either start the full 5-asset test after PCRIX warm-up (first SMA10 signal ≈ 2003-04), or hold the commodity 20% in T-bills before then and flag it.
4. *Execution:* the paper fills at the signal close. The harness fills at the next open. Keep that and document it.
5. *Ties/equality:* use strict > for "buy". Equality is essentially impossible with floats.

**Parameter neighbors.**

- SMA 6/8/10/12 months (the paper tested 3–12).
- A daily 200-day SMA version.
- Cash = BIL vs IEF.
- Rebalance on month-end vs mid-month (timing-luck check).
- GTAA13 Top-3/Top-6 using average(1,3,6,12) momentum.

---

## 3. Gary Antonacci — Dual Momentum / GEM

**Citations and dates (VERIFIED unless noted).**

- Antonacci, G. "Risk Premia Harvesting Through Dual Momentum." SSRN 2042750, posted **19 Apr 2012**, last revised 23 May 2017 (current version "Date Written: October 1, 2016"). The PDF I read is "First version: April 18, 2012; This version: January 28, 2013". Mirror: https://www.emiratescapitalassetmanagement.com/uploads/2/5/5/4/25541321/risk_premia_harvesting_through_dual_momentum.pdf. First place, 2012 NAAIM Wagner Award.
- Antonacci, G. "Absolute Momentum: A Simple Rule-Based Strategy and Universal Trend-Following Overlay." SSRN 2244633, posted **4 Apr 2013** (dated Feb 28, 2013 in the NAAIM PDF): https://www.naaim.org/wp-content/uploads/2013/10/00D_Absolute-Momentum_gary_antonacci.pdf
- Antonacci, G. (2014). *Dual Momentum Investing: An Innovative Strategy for Higher Returns with Less Risk.* McGraw-Hill, published **21 Nov 2014**, ISBN 9780071849456 (Google Books). GEM is specified in the book.
- The book's exact ETF list and its 1974–2013 GEM statistics table were NOT VERIFIED (no primary access).

**GEM rules (VERIFIED from Antonacci's own site, which paraphrases the book).**

- https://www.optimalmomentum.com/global-equities-momentum/ and https://www.optimalmomentum.com/extended-backtest-of-global-equities-momentum/
- "When the trend of stocks is up according to absolute momentum applied to the S&P 500, we use relative strength to determine if we will be in U.S. or non-U.S. stocks. When the trend of stocks is down, we invest in bonds. We use a 12-month lookback period for both types of momentum and rebalance monthly."
- "absolute momentum looks for positive past returns in excess of US Treasury bill returns."
- Indices: S&P 500; MSCI ACWI ex-US (MSCI World ex-US 1970–1988, GFD before 1970); Barclays US Aggregate (Ibbotson Intermediate Government before 1976).
- Operationally, at each month-end:
  1. If R12(S&P 500) > R12(T-bills): hold whichever of S&P 500 or ACWI ex-US has the higher R12.
  2. Otherwise: hold US Aggregate Bonds.
  3. 100% in one asset. No skip month.
- Antonacci's FAQ insists on ACWI ex-US, not EAFE, to avoid selection bias.

**ETFs.**

| Role | ETF | Proxy |
|---|---|---|
| US equity | SPY / VOO / IVV | VFINX |
| ACWI ex-US | VEU / ACWX / CWI / VXUS | VGTSX (1996-04) |
| Bonds | AGG / BND | VBMFX |
| T-bill hurdle | BIL | ^IRX synthetic |

Whether the book lists exactly these tickers is NOT VERIFIED. The FAQ confirms ACWI ex-US ETFs are acceptable for signals.

**Precursors — different rules, do not conflate with GEM.**

- **RPH "modules" (VERIFIED, 2013 version):**
  - Two-stage process: "First, we choose between our module's non-Treasury bill assets using relative strength momentum. If our selected asset does not also show positive momentum with respect to Treasury bills ... we select Treasury bills." So the absolute filter is applied to the *winner*, and the fallback is **T-bills**, not bonds.
  - 12-month lookback, no skip month ("we adjust all our positions monthly without skipping a month").
  - Four modules:
    - Equities: MSCI US vs "EAFE+" (EAFE until 1987, then ACWI ex-US)
    - Credit: HY vs Barclays Intermediate Credit
    - REITs: equity vs mortgage REITs
    - Economic stress: Barclays Long Treasury vs gold
  - The composite is equal-weighted across modules.
- **Absolute Momentum paper (VERIFIED):**
  - Absolute momentum is positive when the asset return minus the T-bill return over the lookback is > 0. If not, switch to 90-day T-bills.
  - Monthly re-evaluation, 20 bp per trade.
  - Formation-period Sharpe ratios for 2–18 months "cluster at 12 months".

**Reported performance (VERIFIED).**

- RPH (Jan 1974–Dec 2011): Equities dual momentum 15.79% / SD 12.77% / Sharpe 0.73 / MaxDD −23.01%, vs MSCI US 11.49% / −50.65%.
  - Composite of the four dual-momentum modules: 14.90% / 7.99% / 1.07 / −10.92%.
  - Absolute-momentum-only composite: 11.76% / 5.50% / 1.05 / −7.52%.
- Absolute Momentum paper (1974–2012): MSCI US with 12-mo abs momentum 12.26% / 11.57% / 0.55 / −22.90% vs 11.62% / 15.74% / 0.37 / −50.65%.
  - 60/40 with abs momentum: 11.52% / 7.88% / 0.72 / −13.45% vs 10.86% / 10.77% / 0.47 / −29.32%.
- GEM extended backtest (Antonacci's site; Jan 1950 to ~2018, "68 years"): CAGR 15.8%, SD 11.5%, Sharpe 0.96, worst DD −17.8%, vs S&P 500 11.4% / 14.2% / 0.52 / −51.0%.
  - Relative momentum alone: 13.4% / −54.6% DD. Absolute alone: 12.3% / −29.6% DD. About 1.5 trades/yr.
- Independent simulation by Keller & Keuning (TrendXplorer VAA post, Dec 1970–Jun 2017, VOO/VEU/BND): GEM R 16.88%, V 12.94%, D −18.57% (SECONDARY).

**Post-publication evidence and critiques.**

- **ReSolve, "Global Equity Momentum: A Craftsman's Perspective"** (Butler, Philbrick, Gordillo; ~Mar 2019): https://investresolve.com/inc/uploads/pdf/global-equity-momentum-a-craftsmans-perspective.pdf; exec summary: https://investresolve.com/global-equity-momentum-executive-summary/
  - Tested 1,226 GEM specifications (1–18-month absolute/relative lookbacks, return vs MA-cross, S&P-only vs both trend checks).
  - The canonical 12/12 spec is near the ~61st percentile, with no statistical edge.
  - "Specification risk" is large: the 5-yr rolling dispersion between the 5th and 95th percentile specs averages 64 pp.
  - An equal-weight ensemble kept returns (14.2% vs 14.9%) and cut average max drawdown (13.2% vs 17.4%) (SECONDARY — exec summary).
- AllocateSmartly reports high sensitivity to the exact trade date (timing luck) for concentrated one-asset models like VAA-G4. The same logic applies to GEM.
- **My own sanity check (not a published result):** ETF version (SPY / VEU / AGG, BIL hurdle), month-end signals, no costs, computed from Yahoo data.
  - Since Dec 2014 (post-book): CAGR ≈ 8.2% vs SPY ≈ 13.8%, max monthly DD ≈ −19.5%.
  - Switches to AGG in Sep-2015, Jan-2016, Dec-2018, Mar-2020 and May-2022 (held AGG through the 2022 bond drawdown until Jun-2023).
  - This illustrates the whipsaw and bond-fallback risk after publication.

**Pitfalls and resolutions.**

1. **Order of filters:** GEM (book/site) applies absolute momentum to the S&P 500. RPH applies it to the relative winner. These give different results when ex-US wins but the S&P is below T-bills (or vice versa). Implement the book version as primary and the RPH version as a variant.
2. **Fallback asset:** bonds (AGG) for GEM vs T-bills for RPH/AbsMom.
3. **T-bill hurdle:** use BIL's 12-month total return (or ^IRX synthetic). Pre-2008 BIL-type fees are negligible. Note BIL's 12-mo return was slightly negative in 2015 (fees), so the hurdle ≈ 0.
4. **ACWI ex-US vs EAFE:** use VEU/ACWX (proxy VGTSX). EFA changes signals (Antonacci FAQ).
5. **Month-end vs start-of-month:** Antonacci's FAQ describes the model adjusting "at the beginning of the month", which is consistent with a month-end signal and next-open fill.

**Parameter neighbors.**

- Lookbacks 3/6/9/12 and a blended (1,3,6,12) average.
- Absolute check on S&P only vs on both equities.
- Fallback: AGG / IEF / BIL / best-of(AGG, BIL).
- Rebalance day offsets: tranche across 4 weekly sub-portfolios to neutralize timing luck.

---

## 4. Industry / Sector Momentum

### 4a. Moskowitz & Grinblatt (1999), "Do Industries Explain Momentum?"

**Citation.** Moskowitz, T.J., Grinblatt, M. (1999). *Journal of Finance* 54(4), 1249–1290 (Aug 1999). DOI 10.1111/0022-1082.00146. PDF: http://www-stat.wharton.upenn.edu/~steele/Courses/956/Resource/Momentum/MoskowitzGrinblatt99.pdf

**Dates.** Presented at the 1998 WFA and 1999 AFA meetings (per acknowledgements). Sample July 1963–July 1995. **The whole Select-Sector-SPDR era (1998+) is OOS.** An SSRN date was not checked.

**Rules (VERIFIED).**

- 20 value-weighted industry portfolios (2-digit SIC groupings) from CRSP/Compustat, formed monthly.
- Main strategy IM(6,6):
  - "Sorting industry portfolios ... based on their past six-month returns, and investing equally in the top three industries while shorting equally the bottom three industries (holding this position for six months)".
  - Overlapping Jegadeesh–Titman style: a new cohort each month, each held 6 months. The monthly return is the average of the 6 live cohorts.
  - No skip month.
- Also reports L ∈ {1, 6, 12} and H ∈ {1, 6, 12, 24, 36}.

**Key findings (VERIFIED).**

- IM(6,6) earns 0.43%/month (long-short), "identical in magnitude" to individual-stock momentum.
- **Profits come mostly from the long side:** top-3 minus middle-3 = 0.36%/month, while middle-3 minus bottom-3 = 0.07%/month. This makes long-only implementation appropriate.
- Unlike stock momentum, industry momentum is **strongest at the 1-month horizon**. "Skipping a month eliminates the profitability of the one-month, one-month industry momentum strategy."
- Momentum dissipates after ~12 months and reverses at long horizons.
- Turnover is ~200%/yr for (6,6). Holding 12 months with 6-month ranking does not reduce average returns and halves turnover.

### 4b. Jegadeesh & Titman (1993)

**Citation.** Jegadeesh, N., Titman, S. (1993). "Returns to Buying Winners and Selling Losers: Implications for Stock Market Efficiency." *Journal of Finance* 48(1), 65–91. DOI 10.1111/j.1540-6261.1993.tb04702.x.

**Rules and findings (VERIFIED).**

- NYSE/AMEX stocks, 1965–1989, ranked into deciles on J-month returns (J, K ∈ {3, 6, 9, 12}). Equal-weighted winner minus loser decile, overlapping K-month holdings.
- A second set skips **one week** between formation and holding.
- Best: 12-month/3-month, 1.31%/month without skip and 1.49%/month with a 1-week skip. Six-month formation earns ~1%/month regardless of holding period.
- The now-standard "12-1" convention (skip the most recent month) comes from later literature (e.g., AMP 2013 "MOM2–12", to avoid the 1-month reversal in *stocks*). For **industries**, MG1999 show the 1-month effect is positive, so skipping is not obviously right.

### 4c. Other reputable evidence relevant to ETF implementation

- **Andreu, Swinkels & Tjong-A-Tjoe (2013)**, "Can exchange traded funds be used to exploit industry and country momentum?" *Financial Markets and Portfolio Management* 27(2), 127–148, DOI 10.1007/s11408-013-0207-8 (SSRN 1150972). Using actual ETF prices, country and industry momentum earned an excess return of ~5%/yr. ETF bid-ask spreads were well below breakeven costs (abstract, SECONDARY). Detailed parameters NOT VERIFIED.
- **Vanstone, Hahn & Earea (2021)**, "Industry momentum: an exchange-traded funds approach," *Accounting & Finance* 61(3), 4007–4024, DOI 10.1111/acfi.12724. "The performance of sector ETF-based industry momentum is very different to stock momentum, and the strong performance of an unexpected group of sector ETF momentum portfolios remains robust after controlling for risk" (abstract, SECONDARY; which formation/holding combos worked NOT VERIFIED).
- **Faber (2010)**, "Relative Strength Strategies for Investing," SSRN 1585517, posted 6 Apr 2010 (VERIFIED). PDF: https://www.cambriainvestments.com/wp-content/uploads/2018/01/Relative-Strength-Strategies-for-Investing.pdf
  - Uses the French–Fama 10 US sectors, July 1926–Dec 2009.
  - Each month, rank the 10 sectors on trailing total return (1, 3, 6, 9, 12 months, or the average of all five). No skip.
  - Hold Top-1/2/3 equal-weighted. Month-end updates only.
  - Optional hedge: move 100% to T-bills when the S&P 500 is below its 10-month SMA.
  - "A rough estimate of 300–600 basis points of outperformance per year is reasonable". It beats B&H in ~70% of years (VERIFIED text; detailed tables are images, not extracted).

### 4d. ETF implementation with Select Sector SPDRs

**Universe.**

- 9 original SPDRs (XLB, XLE, XLF, XLI, XLK, XLP, XLU, XLV, XLY; all 1998-12-22).
- XLRE (2015-10-08) and XLC (2018-06-19) are added when each has ≥ lookback+1 month-ends.
- Alternatively, proxy XLRE with IYR (2000) and XLC with VOX (2004) / IYZ (2000) to keep an 11-sector universe earlier. This is not faithful to what the SPDR family offered, so prefer the add-when-available approach.

**Recommended canonical spec (two primaries, since the literature splits).**

- **MG-style:** rank on 6-month total return (no skip). Long the top 3 equal-weighted. Hold 6 months via 6 overlapping monthly cohorts (each 1/6 of capital), or the simpler "monthly re-rank, hold top 3" (H=1) as a variant.
- **JT/AMP-style:** rank on 12-1 month return. Long the top 3 equal-weighted. Monthly rebalance.
- Optional Faber hedge: all-to-BIL when SPY < its 10-month SMA. Or an absolute filter: a sector is only held if its 12-month excess return > 0, else BIL.

**Pitfalls.**

1. **GICS reclassifications change what the ETFs hold.**
   - Real estate left financials in Sep 2016 (XLF lost REITs, XLRE became standalone).
   - Communication Services was created in Sep 2018. It pulled Alphabet and Meta out of Information Technology (XLK), media/internet names (e.g., Netflix, Disney) out of Consumer Discretionary (XLY), and absorbed telecoms (XLC).
   - Lookback returns straddling these dates mix compositions. Accept this, since it's what an investor would have held, but note it.
2. **Small N (9–11 assets):** top-3 of 9 ≈ top tercile (vs MG's top 3 of 20 = 15%). Results are concentrated and noisy. Report the number of distinct holdings and turnover.
3. **Momentum crashes:** cross-sectional momentum crashes in "panic" rebounds (Daniel & Moskowitz 2016, §9). Sector rotation into defensives in 2008–09 and the 2009 junk rally are the kind of events to inspect.
4. **Skip month:** for industries, MG1999 shows the most recent month helps. Test both.

**Parameter neighbors.** Lookback 3/6/9/12; skip 0/1; top 2/3/4/5; holding 1/3/6 months (overlapping); with/without trend filter; equal vs inverse-vol weights.

---

## 5. Keller & Keuning — PAA (2016), VAA (2017), DAA (2018)

These are **SSRN working papers, not peer-reviewed journal articles**. Jan Willem Keuning (co-author) runs the TrendXplorer blog, where each paper was announced. The papers are widely replicated (AllocateSmartly, CXO Advisory), but data-snooping risk is high (see 5d). I did not verify the authors' affiliations.

### 5a. Protective Asset Allocation (PAA)

**Citation.** Keller, W.J., Keuning, J.W. "Protective Asset Allocation (PAA): A Simple Momentum-Based Alternative for Term Deposits." SSRN 2759734, **posted 8 Apr 2016** (dated 5 Apr 2016) (VERIFIED). https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2759734

- Abstract (VERIFIED): backtest from Dec 1970; "in-sample (Dec 1970–Dec 1992) and out-of-sample" returns reported.
- **OOS start for us:** 2016-01 (data used to Dec 2015).

**Rules (SECONDARY — co-author blog https://indexswingtrader.blogspot.com/2016/04/introducing-protective-asset-allocation.html and AllocateSmartly https://allocatesmartly.com/protective-asset-allocation/).**

- Momentum: MOM(L) = p0 / SMA(L) − 1, where for L=12 the SMA covers **13** month-end prices (p0 … p12). The same metric is used for absolute and relative momentum. The risk-free rate is **not** subtracted.
- Risky universe N=12:
  - Paper (blog): SPY, QQQ, IWM, VGK, EWJ, EEM, IYR, GSG, GLD, HYG, LQD, TLT
  - AllocateSmartly: VNQ for IYR, DBC for GSG
- Bond fraction: BF = (N − n) / (N − a·N/4), clipped to [0, 1]. Here n = the number of risky assets with MOM > 0, and a is the protection factor ∈ {0, 1, 2}.
  - With a=2 and N=12: BF = (12 − n)/6. That means n ≤ 6 → 100% safe; n ≥ 7 → (12 − n)/6 in the safe asset.
- Risky part: the top T assets by MOM (T=6 in the headline variant). The remaining (1 − BF) is split equally among the positive-momentum assets in the top T.
- Safe asset: IEF (AllocateSmartly), or the higher-MOM of SHY/IEF regardless of sign (blog's best risk-adjusted variant). SHY alone and IEF alone are also shown.
- Monthly rebalance, last trading day.

**Reported (SECONDARY — blog tables, Dec 1970–Dec 2015, synthetic ETF data, no costs).**

| Safe asset | R | V | MaxDD |
|---|---|---|---|
| SHY/IEF (best of) | 13.78% | 7.75% | 8.76% |
| IEF | 14.17% | 8.60% | 10.35% |
| SHY | 12.62% | 6.82% | 7.39% |

All with PAA2 (a=2), Top 6.

### 5b. Vigilant Asset Allocation (VAA)

**Citation.** Keller, W.J., Keuning, J.W. "Breadth Momentum and Vigilant Asset Allocation (VAA): Winning More by Losing Less." SSRN 3002624, **posted 19 Jul 2017** (dated 14 Jul 2017) (VERIFIED). https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3002624

- **OOS start:** 2017-07.

**Rules (SECONDARY — co-author blog https://indexswingtrader.blogspot.com/2017/07/breadth-momentum-and-vigilant-asset.html; CXO summary https://www.cxoadvisory.com/technical-trading/conservative-breadth-rule-for-asset-class-momentum-crash-protection/).**

- **13612W momentum:** (12·r1 + 4·r3 + 2·r6 + 1·r12)/4, with r_t = p0/p_t − 1 on month-end TR prices. This gives 40% weight to the last month. It is used for both relative and absolute momentum.
- b = number of risk-on assets with 13612W ≤ 0. Breadth threshold B.
- Cash fraction with "easy trading": CF = (1/T)·floor(b·T/B), clipped to [0, 1].
- Hold the top T risk-on assets equally. Replace the worst CF·T of them with the single best "cash" asset (highest 13612W among SHY, IEF, LQD, regardless of sign). Monthly.
- **VAA-G4:** risk-on VOO (SPY), VEA (EFA), VWO (EEM), BND (AGG); cash SHY/IEF/LQD.
  - T=1, B=1 means any risk-on asset with non-positive 13612W → 100% cash, else 100% in the top-1.
  - The authors recommend T=1/B=1. T=2/B=1 has the best risk-adjusted result.
- **VAA-G12:** risk-on SPY, IWM, QQQ, VGK, EWJ, VWO, VNQ, GSG, GLD, TLT, LQD, HYG; cash SHY/IEF/LQD.
  - The IS-optimal setting is B=4, T=2 (CXO). The blog also lists T=3/4/5 with B=4 as diversified options.

**Reported.**

- CXO (from paper; IS ≈ 1970–1993, OOS ≈ 1993–2016):
  - VAA-G12 (B=4, T=2): IS 21% CAGR / −6% MaxDD / Sharpe 1.24; OOS 10% / −13% / 0.51.
  - VAA-G4 (B=1, T=1): IS 22% / −13% / 0.98; OOS 16% / −10% / 0.92.
- The paper's abstract (VERIFIED): "out-of-sample at annual returns above 10% with max drawdowns below 15% for each of these four universes". The average cash fraction is often >50%.
- Blog table (Dec 1970–Jun 2017):
  - VAA-G4 T1/B1: R 20.42%, V 12.57%, D −12.80%
  - VAA-G4 T2/B1: R 17.44%, V 9.94%, D −8.60%
  - GEM for comparison: 16.88% / 12.94% / −18.57%

### 5c. Defensive Asset Allocation (DAA)

**Citation.** Keller, W.J., Keuning, J.W. "Breadth Momentum and the Canary Universe: Defensive Asset Allocation (DAA)." SSRN 3212862, **posted 1 Aug 2018** (dated 12 Jul 2018; last revised 7 Sep 2021) (VERIFIED). https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3212862

- Abstract (VERIFIED): the canary universe VWO+BND was chosen using "a very simple model from Dec 1926 to Dec 1970 with only the SP500 index as risky asset", then applied Dec 1970–Mar 2018.
- **OOS start:** 2018-04 (data end Mar 2018) or 2018-08 (SSRN posting). Use 2018-08 to be conservative.

**Rules (SECONDARY — co-author blog https://indexswingtrader.blogspot.com/2018/07/announcing-defensive-asset-allocation.html; CXO https://www.cxoadvisory.com/strategic-allocation/multi-class-momentum-portfolio-with-canary-crash-protection/).**

- 13612W momentum on all assets.
- Canary {VWO, BND}. b = number of canaries with non-positive 13612W. B=2, so CF = b/B ∈ {0, 0.5, 1}, rounded down to multiples of 1/T.
  - Both canaries bad → 100% in the single best cash asset (highest 13612W of SHY, IEF, LQD).
  - One bad → 50% in the top half of the best risky assets, equal-weighted (with T=6, the top 3 at 1/6 each), and 50% in the best cash asset.
  - None bad → 100% in the top T risky assets, equal weight.
  - The risky assets themselves are **not** trend-filtered (pure relative momentum).
- **DAA-G12:**
  - Risky: SPY, IWM, QQQ, VGK, EWJ, VWO, VNQ, GSG, GLD, TLT, HYG, LQD
  - Cash: SHY, IEF, LQD
  - Canary: VWO, BND
  - **T=6**, selected by a one-dimensional sweep of T=1..6 on the IS 1971–1993 period, maximizing the Keller ratio K(25%)
- CXO also lists G4 = SPY, VEA, VWO, BND, plus U6/U15 US-factor/sector universes. The DAA-G4 T setting is NOT VERIFIED.
- Monthly.

**Reported (SECONDARY — blog table image, DAA-G12 T6/B2).**

| Period | Dates | R | MaxDD | Avg cash fraction |
|---|---|---|---|---|
| IS | Dec 1970–Dec 1993 | 20.4% | 10.5% | 21.8% |
| OS | Dec 1993–Mar 2018 | 14.1% | 8.2% | 28.8% |
| Recent | Mar 2008–Mar 2018 | 11.1% | 8.2% | – |
| Full | – | 17.15% (vol 9.45%) | −10.47% | – |

CXO: DAA beats VAA on CAGR in 3 of 4 universes (2008–2018) but has worse max drawdown in all four.

### 5d. Overfitting / critique (applies to PAA, VAA, DAA)

- **Many degrees of freedom**, chosen on in-sample data: momentum metric (SMA12 → 13612W), T, B, protection factor a, canary set, cash universe, "easy trading" rounding.
  - The DAA canary pair was selected from alternatives on 1926–1970 data, and T was then optimized on 1971–1993.
  - The simulated pre-ETF "ETF proxies" are the authors' index constructions.
- **CXO Advisory's cautions (VAA):**
  - snooping bias from multiple modeling choices and prior literature;
  - index-based simulations ignore fund costs;
  - trading-friction assumptions;
  - an OOS period too short for the global universes.
- **AllocateSmartly (VAA):**
  - Found "substantial variation depending on exact trading dates" (timing luck), due to the 40% weight on the last month.
  - Flagged AGG-as-offensive-asset as a red flag, though it concluded the breadth relation looked genuine.
- **The authors' own later work** acknowledges the issue. Keller & Keuning's "Hybrid Asset Allocation (HAA)" (Mar 2023, SSRN 4346906) states: "in view of the complexity of BAA there is the risk of 'overfitting' where the in-sample results might be better than the future (out-of-sample) results". It also says the "very high cash-fractions ... of more than 50% for BAA was considered risky in times of rising yields and inflation", and redesigns the canary (TIP) after 2022. (VERIFIED from a PDF copy: https://jennifersjw.wordpress.com/wp-content/uploads/2024/04/ssrn-id4346906.pdf)
- **Recommendation:** treat post-publication data (PAA ≥ 2016-01, VAA ≥ 2017-07, DAA ≥ 2018-08) as the only honest test, and run parameter neighborhoods. Also run a trading-day-offset ensemble to measure timing luck.

**Implementation pitfalls.**

1. 13612W uses *simple* returns over 1/3/6/12 month-ends (p0/p1 − 1, etc.). The r1 weight of 12 annualizes.
2. The cash asset is the best by 13612W even if negative.
3. PAA's MOM uses 13 month-ends (SMA of p0..p12).
4. Ties in top-T are unlikely.
5. The universe includes GSG and GLD, so the full G12 needs commodity/gold proxies. With PCRIX (2002-07) and GC=F (2000-08), the first full-universe 12-mo signal is ≈ 2003-07. Earlier runs must drop those sleeves and are not the published universe.
6. The canary BND needs VBMFX before 2007-04.

**Parameter neighbors.**

- PAA: L = 6/9/12; a = 0/1/2; Top = 3/4/6/12.
- VAA: T = 1/2/3 with B = 1/2/4.
- DAA: T = 4/5/6; B = 1/2; canary {VWO, BND} vs {EEM, AGG} vs {SPY, BND}.
- Momentum metric: 13612W vs 13612U (unweighted) vs R12.

---

## 6. Adaptive Asset Allocation (Butler, Philbrick, Gordillo, Varadi)

**Citation.** Butler, A., Philbrick, M., Gordillo, R., Varadi, D. "Adaptive Asset Allocation: A Primer." SSRN 2328254, **posted 21 Sep 2013**, "Date Written: May 31, 2012" (VERIFIED). https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2328254

- First public as a GestaltU blog post/whitepaper in **May 2012**: https://www.gestaltu.com/2012/05/adaptive-asset-allocation-a-true-revolution-in-portfolio-management.html/
- 2015 revision PDF: https://www.investresolve.com/inc/uploads/pdf/Adaptive-Asset-Allocation-Whitepaper.pdf
- A book followed: *Adaptive Asset Allocation: Dynamic Global Portfolios to Profit in Good Times — and Bad* (Wiley; ISBN 9781119220350; publication year not verified).
- **OOS start:** 2012-06.

**Rules.**

- VERIFIED from the 2012 post and 2015 text:
  - 10 asset classes: US stocks, European stocks, Japanese stocks, EM stocks, US REITs, international REITs, US intermediate Treasuries, US long Treasuries, commodities, gold.
  - Each month-end, take the top 5 by 6-month return.
  - Weight them with a long-only **minimum-variance** optimization (sum = 1, no leverage).
  - Rebalance monthly. Data from 1995, using ETF data spliced with proxies ("proxy ETFs; passive no-load mutual funds; underlying indexes; active no-load funds").
  - The vol-weighted intermediate step uses 60-day volatility.
- The covariance windows for the min-var step are **not stated** in the 2012 post or the 2015 revision (NOT VERIFIED).
- AllocateSmartly's rules, which it says were agreed with the authors because "complete strategy rules are not precisely stated in the paper" (SECONDARY): https://allocatesmartly.com/adam-butler-gestaltu-adaptive-asset-allocation/
  - Covariance built from **126-day correlations and 20-day volatilities**; 6-month = 126-day return.
  - Positions < 2% dropped and reallocated.
  - Trade on the last trading day of the month.
  - ETFs: SPY, EZU, EWJ, EEM, VNQ, RWX, IEF, TLT, DBC, GLD.

**Reported performance (VERIFIED).**

- 2012 post (1995–May 2012): top-5 min-var 15.4%/yr, "Sharpe" 1.71, MaxDD < 16%, vs 13.7%/1.51 for top-5 vol-weighted.
- 2015 revision (Jan 1995–Nov 2014; "Sharpe" = return/vol, not excess):

| Variant | CAGR | Vol | "Sharpe" | MaxDD |
|---|---|---|---|---|
| Equal weight 10 | 8.1% | 11.2% | 0.72 | −39.2% |
| Vol-weighted 10 | – | 8.6% | 0.99 | −24.2% |
| Top-5 EW (6-mo mom) | 13.0% | 11.0% | 1.17 | −21.7% |
| Top-5 vol-weighted | 14.0% | 9.9% | 1.41 | −14.8% |
| Top-5 min-var | 15.0% | 9.4% | 1.60 | −8.8% |

**Critiques.**

- I found no peer-reviewed critique specific to AAA. The authors themselves warn that "returns in the future may not live up to what we have observed in testing" (2015, "Managing Expectations").
- General concerns apply:
  - min-var with only 5 assets tends to concentrate in the lowest-vol asset (often IEF/TLT), creating hidden duration exposure (2022);
  - no absolute-momentum/cash filter, so it is always 100% invested;
  - short covariance windows cause turnover.

**Pitfalls.**

1. Covariance specification: use 126-day correlation × 20-day vol (authors-agreed via AllocateSmartly) as primary, and 60-day covariance as a variant.
2. Solver: long-only, fully invested, no leverage. Consider a max weight (none was published).
3. International REITs (RWX 2006-12; FIREX 2004-09) — before that, run with 9 assets (top 5 of 9, or top 4) and flag it.
4. Commodities before 2002-07 have no proxy (same as above).

**Parameter neighbors.** Momentum 3/6/9/12 months; top 3/4/5/6; covariance windows 60/126/252; vol 20/60; min-var vs inverse-vol vs ERC weighting.

---

## 7. Asness, Moskowitz & Pedersen (2013), "Value and Momentum Everywhere" — momentum leg

**Citation.** Asness, C.S., Moskowitz, T.J., Pedersen, L.H. (2013). *Journal of Finance* 68(3), 929–985. DOI 10.1111/jofi.12021.

- PDF: https://pages.stern.nyu.edu/~lpederse/papers/ValMomEverywhere.pdf
- SSRN 1363476 (first posted **20 Mar 2009**) and 2174501 (posted 14 Nov 2012, "Date Written: June 1, 2012") (VERIFIED).
- Final sample ends July 2011. **OOS start:** 2011-08.

**Rules (VERIFIED).**

- **Momentum signal:** "past 12-month cumulative raw return on the asset ... skipping the most recent month's return, MOM2–12", uniformly for all asset classes. For non-stock assets, "Momentum returns ... are in fact stronger when we don't skip the most recent month, hence our results are conservative."
- **Portfolios:**
  1. Tercile sorts P1/P2/P3 within each asset class. Stocks are value-weighted; **non-stock asset classes are equal-weighted**.
  2. Zero-cost rank-weighted factors: w_it = c_t(rank(S_it) − Σ_i rank(S_it)/N), scaled to $1 long / $1 short.
- Monthly rebalancing.
- Across asset classes, weight by inverse ex-post sample volatility.
- Footnote: weighting non-stock classes by ex-ante vol "gives similar results".

**Universes.**

- Stocks: US, UK, Europe, Japan.
- Country equity index futures, 18 developed markets: Australia, Austria, Belgium, Canada, Denmark, France, Germany, Hong Kong, Italy, Japan, Netherlands, Norway, Portugal, Spain, Sweden, Switzerland, UK, US (Jan 1978–Jul 2011).
- 10 currencies; 10 government bond markets; 27 commodities.

**Reported (VERIFIED, Table I, excess returns).**

- **Country equity indices (1978–2011) momentum:**
  - P1 2.3% (Sharpe 0.14), P2 5.8% (0.37), **P3 11.0% (0.65)**
  - P3−P1 8.7% (Sharpe 0.73)
  - Factor 7.4% (Sharpe 0.63)
- **Global all asset classes (1972–2011) momentum factor:** 5.4%, vol 7.4%, Sharpe 0.74.
- 50/50 value-momentum combo factor: Sharpe 1.59. Across all markets the combination reaches Sharpe 1.45.

**ETF-implementable long-only version (my proposal).**

- **Country momentum:** SPY + 14 iShares MSCI country ETFs available from 1996-03-18: EWA, EWO, EWK, EWC, EWQ, EWG, EWH, EWI, EWJ, EWN, EWP, EWD, EWL, EWU. EDEN and ENOR join in 2012; Portugal is not available on Yahoo.
- At each month-end, rank on MOM2–12 (primary; MOM1–12 variant). Hold the **top tercile (5 of 15) equal-weighted**, i.e., AMP's P3 portfolio. Monthly.
- Rank-weight variant: w ∝ max(0, rank − mean rank), normalized to 1.
- **Cross-asset:** commodity and bond ETF cross-sections are thin before 2007 (DBA/DBB 2007-01, GLD 2004, bond country ETFs 2009+), and FX is excluded. A faithful multi-asset AMP momentum portfolio is therefore only feasible post-2007/2009. Treat it as out of scope for the long 2000+ backtest.

**Pitfalls.**

1. AMP uses futures (local-currency, hedged). US-listed country ETFs are **USD-unhedged**, so momentum rankings include currency moves. Note it as a deviation.
2. Early iShares country ETFs had high fees and tracking error.
3. Crash risk (§9).
4. Tiny cross-section: use terciles, not deciles.

**Parameter neighbors.** MOM2–12 vs MOM1–12 vs 6-month; top 3/5/7; equal vs rank weights; add an absolute filter (hold only if 12-mo excess return > 0, else BIL).

---

## 8. Additional reputable supporting strategies and evidence (brief)

- **Faber (2010) sector/asset relative strength** — see §4c. It is effectively the momentum layer of GTAA-Aggressive.
- **Clare, Seaton, Smith & Thomas (2016)**, "The trend is our friend: Risk parity, momentum and trend following in global asset allocation," *Journal of Behavioral and Experimental Finance* 9, 63–80 (SSRN 2126478). Long-only trend following across equities, bonds, commodities and real estate substantially improves risk-adjusted performance versus buy-and-hold and versus risk parity. Combining it with momentum gives momentum-like returns with lower drawdowns (abstract, SECONDARY). This is academic support for §1d Variant A-type long/flat, risk-budgeted TSMOM on ETFs. Exact rules NOT VERIFIED.
- **Geczy & Samonov (2016)**, "Two Centuries of Price-Return Momentum," *Financial Analysts Journal* 72(5), and "215 Years of Global Multi-Asset Momentum: 1800–2014" (SSRN 2607730). Long-history out-of-sample support for cross-asset and country momentum, cited by Antonacci. Details not re-verified here.
- **Keller & van Putten "FAA"** (SSRN 2193735, posted 25 Dec 2012); **Keller & Butler "EAA"** (SSRN 2543979, posted 31 Dec 2014); **Keller "BAA"** (SSRN 4166845, posted 25 Jul 2022); **Keller & Keuning "HAA"** (SSRN 4346906, Mar 2023). These are later Keller variants and even more heavily parameterized. They are not recommended as primary tests; listed for completeness (dates VERIFIED except HAA's SSRN date).

---

## 9. Cross-cutting post-publication decay and crash evidence

- **McLean & Pontiff (2016)**, "Does Academic Research Destroy Stock Return Predictability?" *Journal of Finance* 71(1), 5–32, DOI 10.1111/jofi.12365. Across 97 anomalies, portfolio returns are 26% lower out-of-sample and 58% lower post-publication. Budget for similar haircuts.
- **Daniel & Moskowitz (2016)**, "Momentum Crashes," *JFE* 122(2), 221–247 (SSRN 2371227; earlier SSRN 1914673, posted 22 Aug 2011) (VERIFIED abstract).
  - Momentum returns are negatively skewed. Crashes are partly forecastable and occur in "panic states — following market declines and when market volatility is high, and are contemporaneous with market 'rebounds'".
  - Documented episodes: WML −91.59% over two months in 1932 and −73.42% over three months in 2009 (SECONDARY — quoted in secondary sources).
  - A dynamic, variance-scaled momentum strategy roughly doubles the Sharpe ratio.
  - Relevance: the cross-sectional strategies here (§4, §5 relative legs, §6, §7) are exposed. Long-only top-bucket versions lose less in short-squeeze rebounds than long-short, but still lag sharply in V-shaped recoveries.
- **Barroso & Santa-Clara (2015)**, "Momentum has its moments," *JFE* 116(1), 111–120. Scaling momentum by its own realized volatility nearly eliminates crashes. This supports optional vol-scaling overlays (not re-verified here).
- **Timing luck:** Hoffstein, Faber & Braun (SSRN 3673910) and ReSolve's GEM study (above). Single-day monthly rebalances of concentrated models carry large, uncompensated path dependence. Recommend reporting results for all ~21 possible monthly rebalance offsets, or a 4-tranche weekly-staggered version.
- **Trend's 2010s drought and 2022 rebound** — see §1c (HOP Exhibit 1; Babu et al. 2020; SG Trend Index 2022).

---

## 10. Recommended test plan (priorities and faithful defaults)

1. **Common infrastructure.**
   - Month-end signal calendar (last trading day), next-open fills.
   - Synthetic T-bill series (^IRX → BIL after 2007-05-30).
   - Proxy splicing per §0.2, by chaining daily returns. Record a "proxy share" flag per date.
2. **Strategies in order of evidence quality and implementability:**
   1. GTAA-5 (Faber). Cleanest rules, OOS since 2006.
   2. GEM (Antonacci book version) plus the RPH-order variant.
   3. TSMOM long/flat Variants A (12-mo) and B (1/3/12), on the §1d universe.
   4. Sector momentum with SPDRs (6-0 top-3 and 12-1 top-3; with and without the SPY-SMA hedge).
   5. Country momentum (AMP P3) with iShares country ETFs.
   6. AAA (authors-agreed covariance spec).
   7. PAA / VAA-G4 / VAA-G12 / DAA-G12 — score primarily on post-publication data.
3. **Report for each:**
   - full-sample, pre-publication and post-publication (OOS start from §0) statistics;
   - the parameter-neighbor grid;
   - a timing-offset ensemble;
   - turnover and cost sensitivity (e.g., 5–10 bp per side for ETFs);
   - the share of history relying on proxies.

---

## Sources (primary unless marked)

- Moskowitz, Ooi, Pedersen (2012) JFE — https://w4.stern.nyu.edu/facdir/lpederse/papers/TimeSeriesMomentum.pdf ; SSRN https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2089463
- Hurst, Ooi, Pedersen (2017) JPM — https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing ; SSRN https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2993026 ; 2014 version https://www.trendfollowing.com/whitepaper/Century_Evidence_Trend_Following.pdf
- Babu et al. (2020) JPM — https://www.aqr.com/Insights/Research/Journal-Article/You-Cant-Always-Trend-When-You-Want
- Faber (2007/2013) — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=962461 ; https://mebfaber.com/wp-content/uploads/2016/05/SSRN-id962461.pdf ; JWM https://jwm.iijournals.com/content/9/4/69
- Faber (2018) JPM "Revisited 10 Years Later" — https://www.pm-research.com/content/iijpormgmt/44/2/156
- Faber (2010) Relative Strength — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1585517 ; https://www.cambriainvestments.com/wp-content/uploads/2018/01/Relative-Strength-Strategies-for-Investing.pdf
- Antonacci RPH — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2042750 ; Absolute Momentum — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2244633 ; https://www.naaim.org/wp-content/uploads/2013/10/00D_Absolute-Momentum_gary_antonacci.pdf ; GEM pages https://www.optimalmomentum.com/global-equities-momentum/ , https://www.optimalmomentum.com/extended-backtest-of-global-equities-momentum/ , FAQ https://www.optimalmomentum.com/faq/
- Antonacci (2014) book — https://books.google.com/books/about/Dual_Momentum_Investing_An_Innovative_St.html?id=PVGoBAAAQBAJ
- ReSolve GEM Craftsman's Perspective (SECONDARY exec summary) — https://investresolve.com/global-equity-momentum-executive-summary/
- Moskowitz & Grinblatt (1999) JF — http://www-stat.wharton.upenn.edu/~steele/Courses/956/Resource/Momentum/MoskowitzGrinblatt99.pdf ; https://onlinelibrary.wiley.com/doi/abs/10.1111/0022-1082.00146
- Jegadeesh & Titman (1993) JF — https://www.bauer.uh.edu/rsusmel/phd/jegadeesh-titman93.pdf
- Andreu, Swinkels, Tjong-A-Tjoe (2013) FMPM — https://econpapers.repec.org/article/kapfmktpm/v_3a27_3ay_3a2013_3ai_3a2_3ap_3a127-148.htm
- Vanstone, Hahn, Earea (2021) A&F — https://ideas.repec.org/a/bla/acctfi/v61y2021i3p4007-4024.html
- Keller & Keuning PAA — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2759734 ; blog https://indexswingtrader.blogspot.com/2016/04/introducing-protective-asset-allocation.html ; AllocateSmartly https://allocatesmartly.com/protective-asset-allocation/
- Keller & Keuning VAA — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3002624 ; blog https://indexswingtrader.blogspot.com/2017/07/breadth-momentum-and-vigilant-asset.html ; CXO https://www.cxoadvisory.com/technical-trading/conservative-breadth-rule-for-asset-class-momentum-crash-protection/ ; AllocateSmartly https://allocatesmartly.com/vigilant-asset-allocation-dr-wouter-keller-jw-keuning/
- Keller & Keuning DAA — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3212862 ; blog https://indexswingtrader.blogspot.com/2018/07/announcing-defensive-asset-allocation.html ; CXO https://www.cxoadvisory.com/strategic-allocation/multi-class-momentum-portfolio-with-canary-crash-protection/
- Keller & Keuning HAA (2023) — https://jennifersjw.wordpress.com/wp-content/uploads/2024/04/ssrn-id4346906.pdf
- Butler et al. AAA — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2328254 ; https://www.gestaltu.com/2012/05/adaptive-asset-allocation-a-true-revolution-in-portfolio-management.html/ ; https://www.investresolve.com/inc/uploads/pdf/Adaptive-Asset-Allocation-Whitepaper.pdf ; AllocateSmartly https://allocatesmartly.com/adam-butler-gestaltu-adaptive-asset-allocation/
- Asness, Moskowitz, Pedersen (2013) JF — https://pages.stern.nyu.edu/~lpederse/papers/ValMomEverywhere.pdf ; SSRN https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2174501
- Daniel & Moskowitz (2016) JFE — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2371227
- McLean & Pontiff (2016) JF — https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12365
- Kim, Tse, Wald (2016) JFM — https://www.sciencedirect.com/science/article/abs/pii/S1386418116301379
- Huang, Li, Wang, Zhou (2020) JFE — https://ideas.repec.org/a/eee/jfinec/v135y2020i3p774-794.html
- Hamill, Rattray, Van Hemert (2016) — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2831926
- Harvey et al. (2018) JPM — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3175538
- Zakamulin (2014) JAM — https://link.springer.com/article/10.1057/jam.2014.25
- Clare, Seaton, Smith, Thomas (2016) JBEF — https://ideas.repec.org/a/eee/beexfi/v9y2016icp63-80.html
- Hoffstein, Faber, Braun — Rebalance Timing Luck — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3673910
- SG Trend Index 2022 (SECONDARY) — https://www.hedgeweek.com/trend-followers-turn-leaders-ctas-deliver-record-returns-2022/
- Yahoo Finance chart API (inception dates, proxy checks) — `https://query1.finance.yahoo.com/v8/finance/chart/TICKER?range=1d&interval=1d`
