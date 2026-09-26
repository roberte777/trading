# Antonacci Global Equities Momentum (GEM, dual momentum)

Strategy name: `antonacci_gem` · class `GlobalEquitiesMomentum` · module `src/trader/strategies/antonacci_gem.py` · config `configs/strategies/antonacci_gem.yaml`

## Summary

GEM is Gary Antonacci's canonical dual-momentum model. It combines two kinds of momentum:

- **Absolute momentum** (trend): are US stocks beating T-bills over the last 12 months?
- **Relative momentum** (cross-sectional): are US or non-US stocks the stronger of the two?

At each month-end the strategy holds 100% of exactly one asset:

- US stocks (SPY), or
- ACWI ex-US stocks (VEU), or
- US aggregate bonds (AGG).

It is a monthly, single-asset rotation that trades about 1.3 times a year.

## Sources

- Antonacci, G. (2014). *Dual Momentum Investing: An Innovative Strategy for Higher Returns with Less Risk.* McGraw-Hill, ISBN 9780071849456, published 2014-11-21. https://books.google.com/books?isbn=9780071849456. GEM is specified in the book.
- Antonacci, G. (2012). "Risk Premia Harvesting Through Dual Momentum." SSRN 2042750, posted 2012-04-19. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2042750. This is the source of the `abs_on="winner"` variant.
- Antonacci, G. (2013). "Absolute Momentum: A Simple Rule-Based Strategy and Universal Trend-Following Overlay." SSRN 2244633, posted 2013-04-04. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2244633
- Antonacci, G. "Global Equities Momentum" (the rules as stated by the author). https://www.optimalmomentum.com/global-equities-momentum/ and the extended backtest at https://www.optimalmomentum.com/extended-backtest-of-global-equities-momentum/
- **Publication date used for the out-of-sample split: 2014-11-21** (the book). The SSRN papers came earlier, but they specify different rules (see the variant below). GEM itself was first specified in the book.

## Rules as implemented

Notation: R(x) is the total return of x from the close `lookback_months` month-ends ago to the latest close.

- With the default of 12, that is 13 month-end observations and no skip month.
- It is computed on total-return-adjusted closes: `indicators.month_end` + `indicators.trailing_return`.
- Decisions are made on the last session of each month (`MonthEnd()`). On that day the latest close *is* the current month-end.

**Default: book / author's-site ordering (`abs_on="us"`)**

1. If R(SPY) > R(BIL), hold 100% of whichever of SPY and VEU has the higher R. On a tie, SPY is held.
2. Otherwise hold 100% of the fallback (`fallback="AGG"`).

**Variant: Risk Premia Harvesting ordering (`abs_on="winner"`)**

1. Pick the winner of SPY vs VEU by R.
2. Hold the winner if R(winner) > R(BIL); otherwise hold the fallback.

**Availability handling** (required by the harness; with proxies it is never triggered from 2000 on):

- A symbol is eligible only if it has a price today and a valid close `lookback_months` month-ends ago.
- If one equity is missing, the comparison runs among the available ones. If SPY is missing, the absolute test is applied to the available equity.
- If BIL has no history, the hurdle is a 0% return.
- If the fallback cannot trade, the strategy holds BIL; if BIL cannot trade either, it holds cash.
- A symbol without data never gets weight (unit-tested).

**Parameters** (the defaults are the published values):

| Param | Default | Grid (robustness suite) |
|---|---|---|
| `lookback_months` | 12 | 6, 9 |
| `fallback` | AGG | BIL |
| `abs_on` | us | winner |

**Execution:**

- Signals are computed at the month-end close and filled at the next session's open.
- Default costs apply: 5 bps slippage plus SEC/FINRA fees.
- Orders are for whole shares, and there is no rebalance band.

## ETF mapping and proxies

| Role | ETF (inception) | Index in the source | Pre-inception proxy |
|---|---|---|---|
| US equities | SPY (1993-01-29) | S&P 500 | VFINX (1980) |
| Non-US equities | VEU (2007-03-08) | MSCI ACWI ex-US (not EAFE; Antonacci insists on this) | VGTSX (1996-04-29) |
| Bonds (fallback) | AGG (2003-09-29) | Barclays US Aggregate | VBMFX (1986-12-11) |
| T-bill hurdle / cash | BIL (2007-05-30) | 90-day US T-bills | `@tbill`: synthetic series from ^IRX, net of a 0.10% fee |

The proxies come from `proxies_for(["SPY", "VEU", "AGG", "BIL"])`. The overlap correlations are in `src/trader/data/proxies.py`.

- Proxy bars make up **25.9%** of held exposure in the base run (`proxy_share`).
- The proxy-era holdings are AGG via VBMFX (2000-11 → 2003-07) and VEU via VGTSX (2000-01 → 2000-08 and 2003-08 → 2007-03). SPY (from 1993) and BIL are never held on proxy data.
- The `etf_era` variant starts at 2008-07-21 and holds no proxy data.

## Deviations from the source

- **Fills at the next open**, not at the same month-end close. This adds one overnight gap per switch. Against an idealized same-close replay of the same signals on month-end data, the harness trails by less than 0.1%/yr over 2000–2026 (9.81% vs 9.88%, from 2000-02). Over 2015–2026 it trails by about 0.6%/yr (7.77% vs 8.36%), mostly from the 2019 and 2020 switch months (see Results).
- **ETFs and mutual-fund proxies instead of indices.** Before ETF inception, the proxies' NAV-only bars mean a "next open" fill is really the next day's NAV.
- **T-bill hurdle is BIL's own total return**, net of its expense ratio (about 0.1–0.14%/yr). It is not the gross 90-day bill yield, so the hurdle is slightly lower than Antonacci's. For example, BIL's 12-month return was about −0.15% in late 2015.
- **Test window 2000–2026** instead of Antonacci's 1950/1974 starts. VEU's proxy only begins in 1996-04.
- **The first decision (2000-01-03) is the harness's initial rebalance, not a month-end.** It compares the 2000-01-03 close with the 1999-01 month-end, a lookback just under 12 months.
- **The `shift_5`/`shift_10` timing-luck variants** also measure R from the prior-year month-end to a mid-month close. This is inherent to evaluating a month-end model off-cycle.
- **Long-only and unlevered**, like the source. There is no adaptation needed.

## Known critiques and post-publication evidence

- **Specification risk** (ReSolve Asset Management: Butler, Philbrick and Gordillo, "Global Equity Momentum: A Craftsman's Perspective", 2019, https://investresolve.com/inc/uploads/pdf/global-equity-momentum-a-craftsmans-perspective.pdf):
  - The authors tested 1,226 GEM specifications (1–18-month lookbacks, return vs MA-cross, absolute test on the S&P only vs both). The canonical 12/12 sits around the **61st percentile**, with no statistical edge over its neighbours.
  - The 5-year rolling spread between the 5th and 95th percentile specifications averages about 64 percentage points.
  - An equal-weight ensemble of specifications kept most of the return and cut drawdowns. This figure comes from the executive summary, a secondary source.
- **Rebalance timing luck.** A concentrated single-asset model rebalanced on one day a month is very sensitive to the trade date (AllocateSmartly; Hoffstein, Faber & Braun, SSRN 3673910).
- **Whipsaw.** A 12-month lookback reacts late to V-shaped crashes. In 2020 the strategy rode SPY down through March, switched to AGG at the end of March, and missed the April–May rebound. The year returned −1.5% vs SPY +18.3%.
- **The bond fallback failing in 2022.** The strategy switched to AGG at the end of May 2022 and held it through the 2022 bond drawdown until June 2023. 2022 returned −16.6% vs SPY −18.2%.
- **Post-publication decay.** McLean & Pontiff (2016) find anomaly returns are 58% lower after publication. GEM's own out-of-sample record here is well below SPY (see below).

## Results

> **Note:** the numbers in this section come from the strategy's own branch run, which used a flat 5 bps slippage on every fill and an earlier harness version. The final numbers, from the tiered 2/4/6 bps cost model with the harness fixes applied, are in [`reports/comparison.md`](../../reports/comparison.md) and `results/<strategy>/summary.json` on the comparison branch. Conclusions are unchanged unless noted there.

Base run with `configs/strategies/antonacci_gem.yaml`:

- 2000-01-03 → 2026-09-25 (26.7 years), with proxies.
- Next-open fills and default costs.
- Benchmark: SPY buy-and-hold.

Output is in `results/antonacci_gem/`.

### Headline metrics (`summary.json`)

The SPY column is SPY's total return over the same sessions with the same metric code.

| Metric | GEM | SPY |
|---|---|---|
| CAGR | **9.59%** | 8.35% |
| Volatility (daily, annualized) | 15.10% | 19.25% |
| Sharpe (excess of T-bills) | **0.56** | 0.41 |
| Sortino | 0.77 | – |
| Max drawdown (daily) | **−33.71%** (COVID, 2020-02 → 03) | −55.19% |
| Calmar | 0.28 | – |
| Turnover (one-sided, per year) | 1.29× | – |
| Cost drag | 0.15%/yr | – |
| Switches per year | 1.27 (34 switches) | – |
| Beta / correlation to SPY | 0.50 / 0.64 | – |
| Bootstrap 90% CI: Sharpe | 0.28 – 0.86 | – |
| Bootstrap 90% CI: CAGR | 5.2% – 14.2% | – |
| P(Sharpe > SPY Sharpe), bootstrap | 0.84 | – |
| PSR vs 0 | 0.998 | – |
| Deflated Sharpe (13 trials) | 0.995 | – |

### In-sample vs out-of-sample (split 2014-11-21)

| Period | GEM CAGR | GEM Sharpe | GEM max DD | SPY CAGR | SPY Sharpe | SPY max DD |
|---|---|---|---|---|---|---|
| In-sample 2000-01-03 → 2014-11-21 | 11.20% | 0.69 | −23.31% | 4.27% | 0.22 | −55.19% |
| Out-of-sample 2014-11-24 → 2026-09-25 | **7.60%** | **0.41** | −33.71% | 13.70% | 0.70 | −33.72% |

In-sample, GEM beat SPY by about 7%/yr and avoided most of both bear markets. Out-of-sample it lagged SPY by about 6%/yr. It had a lower Sharpe than SPY and the same maximum drawdown. It kept only part of its downside protection: down-capture was 0.86, against 0.35 in-sample.

### Crisis returns

| Episode | GEM | Held |
|---|---|---|
| Dot-com bust (2000-03 → 2002-10) | **+5.9%** | VEU → SPY → AGG from 2000-11 |
| GFC (2007-10 → 2009-03) | **−7.7%** | VEU, then AGG from 2008-02 |
| Euro / US downgrade (2011-04 → 2011-10) | −19.8% | VEU, then SPY |
| Q4 2018 selloff | −18.7% | SPY until 2018-12-31 |
| COVID crash (2020-02 → 2020-03) | −33.4% | SPY (12-month return still positive at the end of February) |
| 2022 inflation bear | −18.5% | SPY until 2022-05, then AGG |
| 2025 tariff shock (2025-02 → 2025-04) | −18.6% | SPY |

The switches to AGG after publication fell at the end of Sep-2015, Jan-2016, Dec-2018, Mar-2020 and May-2022. AGG was then held until Jun-2023. These match the independent research check in the spec exactly. In 2008 the model moved to AGG at the end of January 2008 and returned to equities (VEU) at the end of October 2009.

All 320 month-end decisions were re-derived independently from the raw month-end closes, with zero mismatches.

### Robustness suite (`variants.json`)

| Variant | CAGR | Vol | Sharpe | Sortino | Max DD | Calmar | Turnover | Cost drag |
|---|---|---|---|---|---|---|---|---|
| **base** | 9.59% | 15.10% | 0.56 | 0.77 | −33.71% | 0.28 | 1.29× | 0.15% |
| costs 0× | 9.74% | 15.10% | 0.56 | 0.78 | −33.71% | 0.29 | 1.29× | 0.00% |
| costs 2× | 9.45% | 15.10% | 0.55 | 0.76 | −33.72% | 0.28 | 1.29× | 0.31% |
| costs 4× | 9.16% | 15.11% | 0.53 | 0.73 | −33.72% | 0.27 | 1.29× | 0.61% |
| exec next close | 9.57% | 15.10% | 0.55 | 0.77 | −33.71% | 0.28 | 1.29× | 0.15% |
| delay 2 | 9.61% | 15.10% | 0.56 | 0.77 | −33.71% | 0.29 | 1.29× | 0.15% |
| shift 5 sessions | 10.14% | 14.83% | 0.60 | 0.83 | −33.71% | 0.30 | 1.48× | 0.16% |
| shift 10 sessions | 9.56% | 14.72% | 0.56 | 0.77 | −32.02% | 0.30 | 1.59× | 0.18% |
| lookback 6 | 8.26% | 14.07% | 0.50 | 0.69 | −37.51% | 0.22 | 2.86× | 0.30% |
| lookback 9 | 8.56% | 14.66% | 0.50 | 0.69 | −34.65% | 0.25 | 1.97× | 0.22% |
| fallback BIL | 8.80% | 14.71% | 0.52 | 0.72 | −33.70% | 0.26 | 1.29× | 0.15% |
| abs_on winner (RPH) | 9.56% | 15.35% | 0.55 | 0.76 | −33.72% | 0.28 | 1.44× | 0.17% |
| ETF era (from 2008-07-21) | 8.80% | 16.18% | 0.52 | 0.72 | −33.69% | 0.26 | 1.62× | 0.17% |

What the suite shows:

- Costs and execution timing barely matter, because the strategy trades rarely.
- The published 12-month lookback is the best of 6/9/12 in this window. The gaps are small (Sharpe 0.50–0.56).
- The fallback and filter-ordering variants are within noise of the base run.

### Comparison with the reported numbers

| Source | Period | CAGR | SD | Sharpe | Worst DD |
|---|---|---|---|---|---|
| Antonacci, GEM extended backtest | 1950 → ~2018 | 15.8% | 11.5% | 0.96 | −17.8% |
| S&P 500, same source | 1950 → ~2018 | 11.4% | 14.2% | 0.52 | −51.0% |
| Antonacci RPH, equities dual momentum | 1974 → 2011 | 15.79% | 12.77% | 0.73 | −23.01% |
| Independent check, month-end, no costs | Dec 2014 → 2026 | ≈ 8.2% | – | – | ≈ −19.5% (monthly) |
| **This harness** | 2000 → 2026 | 9.59% | 15.10% (daily) / 11.88% (monthly) | 0.56 | −33.71% (daily) / −21.42% (monthly) |
| **This harness, in-sample** | 2000 → 2014-11 | 11.20% | 14.13% (daily) | 0.69 | −23.31% (daily) |

The large gaps have these explanations:

- **CAGR, 9.6% vs 15.8%.** Most of the gap is the window. SPY compounded 8.35% here vs 11.4% for 1950–2018, and 2000–2026 contains two equity bear markets in its first decade and a long stretch of ex-US underperformance after 2010. Relative to its benchmark, GEM added +1.2%/yr here vs +4.4%/yr in Antonacci's long sample. All of the excess came before publication.
- **Drawdown, −33.7% vs −17.8%.** Antonacci measures on month-end data, and this harness measures daily.
  - On month-end equity the harness's worst drawdown is −21.4%. An idealized same-close month-end replay of the same signals gives −17.8% over 2000–2014, the same number Antonacci reports, and −19.5% over 2015–2026.
  - The −33.7% daily figure is the COVID crash. GEM was 100% in SPY from the 2020-02-19 peak to the 2020-03-23 trough, because its 12-month signal only turned at the end of March.
  - The daily-annualized volatility (15.1%) is likewise higher than the monthly figure (11.9%, comparable to Antonacci's 11.5%).
- **Post-publication, 7.6% vs about 8.2%.** An idealized month-end, no-cost replay of the same signals reproduces the independent check: 8.23% from 2015-01 to date, and 8.36% for 2015-01 → 2026-08. Over 2015-01 → 2026-08 the harness makes 7.77%. The ~0.6%/yr difference is next-open fills on switch months (2019 −2.9 pp, 2020 −4.2 pp) plus about 0.15%/yr of costs. The signals themselves match the independent check month for month.

## Assessment

- GEM is implemented faithfully and reproduces both the independent post-2014 record and Antonacci's in-sample drawdown profile.
- As a live candidate it is **weak**:
  - After publication it earned 7.6%/yr vs 13.7% for SPY, with a lower Sharpe (0.41 vs 0.70) and the same maximum drawdown.
  - Its protection failed in the three fast post-publication selloffs (Q4 2018, COVID and 2025), and its bond fallback lost money in 2022.
- Its full-period edge over SPY rests entirely on 2000–2009. The bootstrap CI on its Sharpe advantage over SPY includes zero.
- ReSolve's specification-risk evidence and the timing-luck sensitivity visible here argue against deploying the single 12/12 specification. Shift variants move the Sharpe from 0.56 to 0.60 with no change to the rules.
