# Short-Term Mean-Reversion & Calendar/Seasonal Anomalies — Research Dossier

Prepared 2026-09-25 for a daily-bar, long-only, ≤1x gross, Alpaca-tradeable ETF harness
(signal at close *t*; fill at **next open** (MOO) or **next close** (MOC)).

Conventions used throughout

* **"First public date"** = earliest date I could verify that the idea/rules were publicly circulated. Data after that date may be treated as out-of-sample (OOS). Where only the journal date could be verified, that is stated; where an earlier working-paper date exists but could not be confirmed, that is flagged.
* **[VERIFIED]** = checked against the original paper/book text or an official page. **[SECONDARY]** = taken from a secondary source that quotes the original; I could not read the primary text. **[UNVERIFIED]** = could not confirm.
* **"Replication"** numbers are my own quick checks on Yahoo Finance split/dividend-adjusted daily bars (SPY/QQQ/IWM/DIA, data through 2026-09-24). They are *indicative only*, not peer-reviewed, run with no multiple-testing correction, and cash earns 0% when out of the market (so CAGR/Sharpe understate a T-bill-sweep version). The ad-hoc scripts behind them were not kept; the harness backtests in `results/` supersede them.

---

## 0. Executive summary

| # | Strategy | Key source (first public) | Harness-implementable? | Post-publication evidence | Verdict for this harness |
|---|---|---|---|---|---|
| 1 | Connors RSI(2) (+ Double 7s, RSI 25/75, R3) | Connors & Alvarez, *Short Term Trading Strategies That Work* (Nov 2008); *High Probability ETF Trading* (May 2009) | Yes (next-open works nearly as well as same-close; next-close is worse) | No peer-reviewed OOS test found. Academic support: index serial correlation turned **negative** after ~1999 (Baltussen, van Bekkum & Da 2019 JFE). My replication: edge persists 2009–2026 but weaker; very low exposure (4–15%) | **Strongest candidate** among the high-turnover ideas; costs are small relative to ~50–100 bp/trade edge. Use as a portfolio of ETFs, loose parameters |
| 2 | Turn-of-the-month (TOM) | Ariel (1987 JFE); Lakonishok & Smidt (1988 RFS); McConnell & Xu (SSRN Jul-2006; FAJ 2008) | Yes (deterministic calendar → MOC fills) | Han, Han & Tian (2025 FRL): "disappears entirely after 2001". My replication: SPY [-1,+3] TOM vs other days t = 0.24 for 2006–2026 | **Weak/decayed**; test only as a low-weight overlay, wider windows are data-mined |
| 3 | Halloween / Sell-in-May | Bouman & Jacobsen (AER Dec-2002; working paper 1997) ; Zhang & Jacobsen (JIMF 2021; SSRN 2012) | Yes (monthly) | Mixed: Jacobsen/Zhang & Andrade et al. (FAJ 2013) say persists internationally; Dichtl & Drobetz (IRFA 2015) and Maberly & Pierce (EJW 2004) say weak/outlier-driven in US. My replication: SPY winter–summer diff t = 0.52 (2002-11 → 2026) | **Not recommended** as return engine for US; lower vol but far lower CAGR than buy-and-hold since 2002 |
| 4 | Pre-FOMC drift | Lucca & Moench (NY Fed SR512 Sep-2011; JF Feb-2015) | Partially: close→close or open→open with a single fill type; the part that survived (close t-1 → open t) needs MOC entry + MOO exit | Kurov, Wolfe & Gilbert (2021 FRL): 2pm–2pm drift "essentially disappeared after 2015". Knox & Vissing-Jorgensen (FEDS 2026-023): ~20 bp **overnight** return the night before FOMC since Mar-2011. My replication: SPY close(t-1)→open(t) = 17.7 bp vs 3.2 bp normal nights (t = 3.4, Apr-2011→2026) | **Interesting but fragile**; only 8 events/yr; the surviving component is the overnight leg; treat as a small overlay |
| 5 | Pre-holiday | Ariel (1990 JF); Lakonishok & Smidt (1988) | Yes (deterministic) | Ko & Yang (2024 Critical Finance Review): pre-holiday premium "now exists only among small firms"; insignificant for VW/S&P 500 after 1990. My replication: SPY 10.4 bp vs 4.6 bp (t = 1.05) 1993–2026 | **Decayed for large caps**; IWM slightly better but not significant |
| 6 | Overnight vs intraday (buy MOC / sell MOO) | Cliff, Cooper & Gulen (SSRN 2007/08); Lou, Polk & Skouras (JFE 2019) | Yes but requires both MOC and MOO every day (252 round trips/yr) | Boyarchenko, Larsen & Whelan (NY Fed Liberty Street, Jul-2026): futures "overnight drift" ≈ 0 since 2021; NightShares overnight ETFs (2022) closed within 14 months. My replication: SPY overnight 1bp-round-trip-cost CAGR 8.2% vs B&H 15.4% (2017–2026) | **Reject for SPY/QQQ/DIA** (costs + auction-price risk); IWM looks anomalously strong in Yahoo data — needs validation with true auction prints before any use |
| 7 | IBS (Internal Bar Strength) | Pagonidis, NAAIM white paper (data to May-2013; 2014 collection) | Yes, but the edge is next-day; next-close fills destroy it | My replication: SPY IBS<0.2 one-day hold: next-open Sharpe 1.00 (1993–2013) → 0.53 (2013–2026) at 0 cost; ~40 round trips/yr, very cost sensitive | **Use as a filter** on RSI-type entries (as Pagonidis recommends), not standalone |

**Overall caveat (data snooping).** Sullivan, Timmermann & White (1998 WP / 2001 J. Econometrics) showed that once ~9,500 calendar rules (or a reduced 244-rule universe) are considered jointly with White's Reality Check, the best calendar rule on 100 years of DJIA data is **not** significant, and the in-sample best rule under-performed out-of-sample. Treat any window/threshold search in this dossier as part of that universe.

---

## 1. Harness-wide implementation notes (read first)

### 1.1 Execution-timing semantics

Alpaca supports auction orders via `time_in_force`:
* `opg` (market/limit-on-open): "OPG orders submitted after 9:28am but before 7:00pm ET will be rejected." Executes only in the opening auction. [VERIFIED — [Alpaca docs](https://docs.alpaca.markets/us/docs/orders-at-alpaca)]
* `cls` (market/limit-on-close): "CLS orders submitted after 3:50pm but before 7:00pm ET will be rejected." Executes only in the closing auction. [VERIFIED — same page]
* One secondary source claims OPG/CLS are restricted to "Elite Smart Router" users; the Alpaca docs page I read did **not** state such a restriction. [UNVERIFIED — confirm on your account before relying on MOO/MOC.]

Consequence: a signal computed from the official close of day *t* **cannot** be filled in day *t*'s closing auction. So "next close" = close of *t+1* (a full day later). Connors' "buy on the close" (same close that generates the signal) is only approximable by computing the signal from a ~3:45 pm snapshot and sending MOC before 3:50 pm — not possible with daily bars only.

Mapping used in my replications (per-day return decomposed into overnight close(t-1)→open(t) and intraday open(t)→close(t)):

| Mode | Entry fill | Exposure lost vs "book" | Notes |
|---|---|---|---|
| `same_close` (book, not implementable) | close *t* | — | Connors/Pagonidis convention |
| `next_open` (MOO) | open *t+1* | overnight *t→t+1* | usually the best implementable proxy for daily mean reversion |
| `next_close` (MOC) | close *t+1* | whole day *t+1* | loses the first (strongest) reversal day |

For **calendar strategies** (TOM, pre-holiday, Halloween, FOMC) the schedule is known in advance, so the decision can be made one bar early and filled at the exact close with MOC — no look-ahead, *provided the harness uses a forward-known exchange calendar* (unscheduled closures such as 2001-09-11..14, 2004-06-11, 2007-01-02, 2012-10-29/30, 2018-12-05, 2025-01-09 are not knowable in advance; treat them as exceptions).

If the harness enforces a single execution type per strategy, the FOMC-overnight leg (enter MOC, exit MOO) and the overnight anomaly are not directly expressible — see §5 and §7.

### 1.2 Transaction-cost model (recommended)

Explicit costs on Alpaca:
* Commission: $0 for self-directed API accounts (Alpaca marketing pages; Elite Smart Router arrangements may differ). [SECONDARY]
* SEC Section 31 fee on **sales**: $27.80 per $1M until 2025-05-13; **$0.00** from 2025-05-14 ([FINRA notice](https://www.finra.org/rules-guidance/notices/information-notice-20250424)); **$20.60 per $1M** (≈0.21 bp of sale value) from 2026-04-04 ([FINRA notice 2026-03-17](https://www.finra.org/rules-guidance/notices/information-notice-20260317)). [VERIFIED]
* FINRA TAF on sales: per-share, capped per trade; negligible at ETF prices (exact current rate not verified here).

Implicit costs:
* Quoted spreads: SPY/QQQ/IWM typically trade one cent wide (≈0.15 bp for SPY at ~$650; ≈0.35–0.5 bp for IWM at ~$200–280). SSGA reports a SPY pre-trade cost estimate of 0.07 bp vs 0.17–0.18 bp for VOO/IVV for a $25M trade as of 2026-06-30 ([SSGA](https://www.ssga.com/us/en/institutional/insights/spy-liquidity-flexibility-to-navigate-any-market)). [VERIFIED as reported by issuer; issuer-sourced]
* Auction orders do not "cross the spread", but the auction clearing price can deviate from the fair midpoint. Bogousslavsky & Muravyev (2023, *J. Financial Markets* 66; [SSRN 3485840](https://www.ssrn.com/abstract=3485840)) find closing-auction prices often deviate from closing midpoints, with deviations reverting ~half shortly after the close and ~85% by next morning; closing auctions nonetheless match volume at low cost. Closing auction share of volume rose from 3.1% (2010) to 7.5% (2018). [SECONDARY via abstract]
* Opening prices can be "expensive": Berkman, Koch, Tuttle & Zhang (2012, JFQA 47(4)) — "Paying Attention: Overnight Returns and the Hidden Cost of Buying at the Open" — high-attention stocks show high overnight returns then intraday reversal (retail buying at the open). [SECONDARY]
* Pre-decimalization (NYSE Jan-29-2001, Nasdaq Apr-9-2001; [Chicago Fed 2003](https://www.chicagofed.org/~/media/publications/economic-perspectives/2003/4qeppart1-pdf.pdf)) the standard tick was 1/16 ($0.0625): a one-tick SPY spread at ~$130–140 ≈ 4.5–5 bp. (SPY's exact pre-2001 quoting increment on AMEX not verified.)

**Recommended per-side cost assumptions for backtests** (my judgment, bracketing the above):

| Instrument | 2001–2008 | 2009–present | Stress (2×) |
|---|---|---|---|
| SPY, QQQ, IVV | 1.5–2 bp | 0.5–1 bp | 2 bp |
| IWM, DIA, MDY | 3 bp | 1–2 bp | 4 bp |
| Sector SPDRs, EFA/EEM, GLD | 4–5 bp | 2–3 bp | 6 bp |
| pre-2001 (SPY only) | 2.5–3 bp | — | 5 bp |

Add ~0.5–1 bp extra for MOO fills (open-auction noise / data-vendor "open" ≠ auction price). The daily-bar "open" from Yahoo or other vendors may be the first consolidated print, not the primary-exchange opening auction price (SPY/IWM list on NYSE Arca; QQQ on Nasdaq). **Validate a sample of vendor opens against actual auction prints** before trusting overnight-sensitive results.

### 1.3 What to hold when out of the market

| Asset | Ticker | Yahoo first bar | Notes |
|---|---|---|---|
| 0–3m T-bill | SGOV | 2020-06-01 | cleanest cash proxy but short history |
| 1–3m T-bill | BIL | 2007-05-30 | |
| 0–1y Treasury | SHV | 2007-01-11 | |
| 1–3y Treasury | SHY | 2002-07-30 | some duration risk |
| 7–10y Treasury | IEF | 2002-07-30 | "bonds when out" variant for Halloween |

Before 2002/2007 no T-bill ETF exists; use 0% cash or (if the harness allows) a synthetic cash return from 3-month T-bill yields (e.g., FRED DTB3). For **short-horizon** strategies (RSI(2), IBS, FOMC, overnight), rotating into a bill ETF on every exit doubles turnover; prefer cash, or run the mean-reversion sleeve as an overlay on a separate bill/equity core. For Halloween the bill switch is part of the published rule.

### 1.4 ETF inception (Yahoo `meta.firstTradeDate`, queried 2026-09-25)

SPY 1993-01-29 · MDY 1995-05-04 · DIA 1998-01-20 · Select Sector SPDRs (XLK/XLF/XLE/XLY/XLP/XLV/XLI/XLB/XLU) 1998-12-22 · QQQ 1999-03-10 · IVV 2000-05-19 · IWM 2000-05-26 · IJR 2000-05-26 · VTI 2001-06-15 · EFA 2001-08-27 · TLT/IEF/SHY 2002-07-30 · EEM 2003-04-14 · RSP 2003-05-01 · AGG 2003-09-29 · GLD 2004-11-18 · SHV 2007-01-11 · BIL 2007-05-30 · SGOV 2020-06-01.
(These are the first bars in Yahoo's database; official fund inception can be a few days earlier.)

---

## 2. Strategy 1 — Connors RSI(2) short-term mean reversion (and sibling Connors ETF rules)

### 2.1 Sources and first public dates

* Larry Connors & Cesar Alvarez, *Short Term Trading Strategies That Work*, TradingMarkets Publishing, ISBN 978-0981923901, **Nov 2008** (Biblio listing "2008-11"). Chapter 9 is the 2-period RSI chapter. [SECONDARY for contents]
* Larry Connors & Cesar Alvarez, *High Probability ETF Trading: 7 Professional Strategies to Improve Your ETF Trading*, TradingMarkets, ISBN 978-0615297415, **May 2009**. Tested on 20 liquid ETFs "since inception" with data through 2008. [SECONDARY]
* Earlier exposure: Connors' *How Markets Really Work* (1st ed. 2004, TradingMarkets; 2nd ed. 2012 Wiley/Bloomberg with Alvarez) includes a 2-period RSI chapter in the 2nd edition (studies 1989–Sept 2011). Whether the 2004 edition already contained RSI(2) rules is **[UNVERIFIED]**; TradingMarkets published RSI(2) articles in the mid-2000s.
* **Recommended OOS start: 2009-01-01** (conservative w.r.t. the exact book rules). A stricter choice (because the RSI(2) concept circulated earlier) is ~2005.

Academic foundation (cross-sectional, individual stocks — *not* index timing):
* Jegadeesh, N. (1990). "Evidence of Predictable Behavior of Security Returns." *Journal of Finance* 45(3): 881–898. [doi:10.1111/j.1540-6261.1990.tb05110.x](https://onlinelibrary.wiley.com/doi/10.1111/j.1540-6261.1990.tb05110.x) — significant negative first-order serial correlation in monthly individual-stock returns.
* Lehmann, B. (1990). "Fads, Martingales, and Market Efficiency." *QJE* 105(1): 1–28. [doi:10.2307/2937816](https://academic.oup.com/qje/article-abstract/105/1/1/1928416); NBER WP 2533 (1988) — weekly reversal in individual stocks.
* Nagel, S. (2012). "Evaporating Liquidity." *RFS* 25(7): 2005–2039 ([OUP](https://academic.oup.com/rfs/article-abstract/25/7/2005/1602153)) — short-term reversal returns ≈ returns to liquidity provision; strongly predictable by VIX (higher in turmoil).
* **Index-level** evidence (the relevant one for ETF timing): Baltussen, G., van Bekkum, S., & Da, Z. (2019). "Indexing and Stock Market Serial Dependence Around the World." *JFE* 132(1): 26–48. [doi:10.1016/j.jfineco.2018.07.016](https://www3.nd.edu/~zda/Indexing.pdf). [VERIFIED from accepted manuscript]
  * S&P 500 daily AR(1): **+0.103 before 1999-03-03 vs −0.076 after** (t = −3.29 after; diff t = −6.64). Weekly AR(1) +0.037 → −0.077.
  * Pattern holds in 16/20 indexes; linked to growth of index products (futures/ETFs).
  * With a **one-day implementation lag** (AR(2)), the post-1999 panel coefficient remains significantly negative (−0.029 daily; MAC(5) −0.057) — i.e., reversal is not confined to the first overnight, which is encouraging for next-open/next-close fills.
  * Trading against MAC(5) on the S&P 500 alone: annualized Sharpe **0.67** after 1999-03-02 (all indexes: 0.63), before costs; the authors caution it "might not be exploitable to many investors after accounting for transaction costs."
  * Before ~1990s index autocorrelation was positive (consistent with Lo & MacKinlay-era momentum at the index level), so *long pre-2000 index backtests of mean reversion are not representative*.
* Lou, Polk & Skouras (2019 JFE, see §7): the monthly short-term **reversal** (STR) premium in value-weighted ex-microcap stocks 1993–2013 is zero close-to-close but **+0.93%/month overnight (three-factor alpha, t = 4.28) and −1.05%/month intraday (CAPM alpha, t = −3.25)**. Reversal profits are an overnight phenomenon in the cross-section — a warning that execution timing matters.

No peer-reviewed journal article testing Connors' exact RSI(2) rules out-of-sample was found. Practitioner evidence: Cesar Alvarez (book co-author) blog; Raymond Micaletti, "A Comparison of Short-Term Mean-Reversion Indicators for Global Equities" ([SSRN 4339128](https://www.ssrn.com/abstract=4339128), Jan 2023) finds oscillators that use position within the intraday/multiday range (IBS-like) rank best — details not verified.

### 2.2 Exact rules

**RSI(2) — "Chapter 9" S&P 500 rules** [SECONDARY: widely and consistently quoted, incl. [StockCharts ChartSchool](https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/rsi-2)]:
1. Close > 200-day SMA (trend filter).
2. 2-period RSI (Wilder) closes **below 5** (ChartSchool: "returns were higher when buying on an RSI dip below 5 than on one below 10").
3. **Buy on the close** (same bar as the signal).
4. **Exit when the close is above the 5-day SMA** (on the close).
5. No stops ("stops actually 'hurt' performance" per Connors' testing, as quoted by StockCharts).
Short-side mirror (RSI(2) > 95 and close < 200-SMA; cover on close < 5-SMA) — ignore (long-only harness).
Reported result: "correctly predicted the short-term direction of the S&P 500 83.6% of the time" — quoted by a search snippet of the book; **[UNVERIFIED]** period/instrument. (My SPY replication 1993–2008 gives an 83.7% win rate on 49 trades, consistent with this figure.)

**Sibling rules** (all [SECONDARY]; primary text not read):
* **Cumulative RSI** (*STTSTW*): sum of last 2 days' RSI(2) below a threshold (secondary sources disagree: 35 vs 10), close > 200-SMA; exit RSI(2) > 65. Treat thresholds as unverified.
* **Double 7s** (*STTSTW*): close > 200-SMA and close = 7-day low of closes → buy on close; sell when close = 7-day high of closes. Rules confirmed by co-author Alvarez ([blog, 2016-02-10](https://alvarezquanttrading.com/blog/double-7s-strategy/)), who reports SPY/QQQ 2000–2007 beat buy-and-hold with ~26% exposure, but 2008–2015 CAGR fell below buy-and-hold (drawdown better for SPY).
* **RSI 25/75** (*HPETF*): close > 200-SMA and RSI(4) < 25 → buy; aggressive add if RSI(4) < 20; exit RSI(4) > 55 (book's original exit reportedly 75; 55 is a later preference in the secondary source). [SECONDARY]
* **R3** (*HPETF*, ch. 4): close > 200-SMA; RSI(2) down 3 days in a row; RSI(2) < 60 three days ago and < 10 today → buy close; exit RSI(2) > 70. [SECONDARY]
* *HPETF* ETF universe (per a secondary source): DIA, EEM, EFA, EWH, EWJ, EWT, EWZ, FXI, GLD, ILF, IWM, IYR, QQQ(Q), SPY, XHB, XLB, XLE, XLF, XLI, XLV; tested from 1993 (or inception) to 2008 ([EdgeRater](https://www.edgerater.com/blog/connors-etf-three-day-highlow-method/)). [SECONDARY]

### 2.3 Instruments

SPY (1993), QQQ (1999), IWM (2000), DIA (1998), MDY (1995), Select Sector SPDRs (1998-12). For a pre-2001 start only SPY/MDY/DIA/sectors exist. International/sector ETFs from the *HPETF* list broaden trade count (important: a single ETF trades only ~3–8 times/yr at the book thresholds).

### 2.4 Replication (Yahoo adjusted data; cash = 0%; 1 bp/side unless noted)

RSI(2)<5, close>SMA200, exit close>SMA5 — portfolio-level (100% in one ETF when in position):

| ETF | Mode | 1993(99/00)–2008 CAGR / Sharpe / MDD | 2009–2026 CAGR / Sharpe / MDD | Exposure |
|---|---|---|---|---|
| SPY | same_close (book) | 3.2% / 0.72 / −7.7% | 2.4% / 0.48 / −14.1% | 4–6% |
| SPY | next_open | 3.4% / 0.70 / −8.2% | 2.1% / 0.41 / −15.5% | |
| SPY | next_close | 1.9% / 0.46 / −6.3% | 2.1% / 0.42 / −15.0% | |
| QQQ | same_close | 2.7% / 0.42 | 3.0% / 0.47 | |
| QQQ | next_open | 2.4% / 0.40 | 2.7% / 0.44 | |
| IWM | same_close | 1.3% / 0.33 | 2.3% / 0.37 | |
| IWM | next_open | 1.3% / 0.32 | 1.9% / 0.32 | |

Per-trade (0 cost): SPY same_close 1993–2008: 49 trades, 83.7% win, avg +105 bp; 2009–2026: 80 trades, 77.5% win, avg +57 bp. SPY next_open: 77.6% / +112 bp → 73.8% / +49 bp. SPY next_close: 65.3% / +64 bp → 70.0% / +50 bp.

Parameter sensitivity (SPY, 0 cost, next_open, 2009–2026): RSI<2: Sharpe 0.08; **<5: 0.43; <10: 0.63; <15: 0.80**; exit RSI>70 instead of SMA5 similar or slightly better; dropping the 200-SMA filter raises exposure and MDD (−25% to −30%).

Sibling strategies (1 bp/side, SPY, pre → post May-2009): RSI(4)<25/exit>55: next_open Sharpe 0.92 → 0.70, CAGR 6.0% → 5.0%, exposure 11–14%. R3: 0.88 → 0.62. Double 7s (SPY, pre/post 2009): next_open CAGR 7.8% → 6.2%, Sharpe 0.85 → 0.66, exposure ~27–31%, avg trade ~+64–87 bp. **IWM RSI(4)/R3 post-2009 MDD −40% to −44%** (early-2020 crash with no stop) — tail risk is real.

Takeaways:
1. **Execution timing:** next-open retains most of the edge (≈85–105% of book return for SPY RSI(2); ≈90–95% for Double 7s). Next-close is materially worse for RSI(2)/IBS-type signals (loses the strongest day), especially in 1993–2008. This contrasts with the cross-sectional finding that reversal is earned overnight (LPS 2019) — at the ETF level, a lot of the bounce happens intraday on day *t+1* and beyond (consistent with Baltussen et al.'s lagged negative autocorrelation).
2. **Decay:** per-trade edge roughly halved post-2009 for the book thresholds, but Sharpe on the looser thresholds (RSI<10–15) held up. Nothing here is significant after accounting for the parameter search.
3. **Costs are not the binding constraint**: ~3–10 round trips/yr/ETF with +50–100 bp average trades; 1–3 bp/side costs reduce CAGR by only ~0.05–0.3 pp. The binding constraint is **low exposure** (standalone CAGR 2–7%).

### 2.5 Post-publication critiques / caveats
* No academic OOS test of these exact rules; evidence is practitioner backtests (often with same-close fills and survivorship-free ETF data only since the 1990s).
* Index mean reversion is a post-~1999 regime (Baltussen et al. 2019); a structural break could reverse it (their mechanism is index-product arbitrage).
* Tail risk: no stops, long-only buying of dips — large losses in crashes that start above the 200-SMA (Oct-1987-type, Feb/Mar-2020). Nagel (2012): reversal returns are compensation for liquidity provision — highest when VIX is high, i.e., when drawdown risk is highest.

### 2.6 Implementation pitfalls & resolutions
* **RSI definition**: use Wilder smoothing (EMA with α = 1/n). Cutler's (SMA) RSI (used by Pagonidis) gives different values at n = 2–3. Warm-up ≥ 250 bars for SMA200 + RSI stabilization.
* **Signal on adjusted vs raw prices**: compute on split/dividend-adjusted closes (dividend drops otherwise create false "down days" on ex-dates — relevant for SPY quarterly and high-yield ETFs).
* **Pending orders**: with next-open fills, don't re-trigger entries while an entry is pending; evaluate exits starting the first close after the fill.
* **Portfolio construction**: run on a basket (SPY, QQQ, IWM, DIA, MDY, sector SPDRs, EFA/EEM) with equal fixed slot sizes (e.g., 1/N or max 20–25% per position), cash otherwise; this raises exposure and diversifies. Avoid leverage (cap 1x gross).
* **Same-close illusion**: never backtest `same_close` as the headline; report `next_open` (primary) and `next_close` (secondary).

### 2.7 Parameter neighbors for robustness
RSI period {2, 3, 4}; entry threshold {2.5, 5, 10, 15, 20} (RSI(4): {20, 25, 30}); trend filter SMA {100, 150, 200, 250, none}; exit {close > SMA3/SMA5/SMA10, RSI(2) > 50/65/70, time stop 5/10 days}; Double 7s lookback {5, 6, 7, 8, 10}; universe {SPY only, 4 index ETFs, + 9 sectors, + international}.

---

## 3. Strategy 2 — Turn-of-the-month (TOM)

### 3.1 Sources and first public dates
* Ariel, R. A. (1987). "A Monthly Effect in Stock Returns." *JFE* 18(1): 161–174 (March 1987). [doi:10.1016/0304-405X(87)90066-3](https://www.sciencedirect.com/science/article/abs/pii/0304405X87900663). CRSP EW/VW 1963–1981: mean returns positive only in the "first half" = trading days **−1 through +9** (last trading day of prior month + first nine trading days); effect strongest in days −1 to +4 (per Pham's SFU thesis summary, [link](https://summit.sfu.ca/_flysystem/fedora/sfu_migrate/10272/etd2038.pdf)). [SECONDARY]
* Lakonishok, J., & Smidt, S. (1988). "Are Seasonal Anomalies Real? A Ninety-Year Perspective." *RFS* 1(4): 403–425. [doi:10.1093/rfs/1.4.403](https://academic.oup.com/rfs/article-abstract/1/4/403/1566965). DJIA 1897–1986; TOM = last trading day through third trading day ([−1,+3]); average 4-day TOM return 0.473% vs 0.349% for the full month. [VERIFIED via McConnell & Xu's description]
* McConnell, J. J., & Xu, W. (2008). "Equity Returns at the Turn of the Month." *FAJ* 64(2): 49–64 (Mar/Apr 2008). [doi:10.2469/faj.v64.n2.11](https://www.tandfonline.com/doi/abs/10.2469/faj.v64.n2.11); SSRN [917884](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=917884) posted **July 2006**. [VERIFIED from JSTOR copy of FAJ article]
  * CRSP VW 1987–2005: TOM [−1,+3] mean daily return **0.15%** vs **−0.00%** other days (diff t = 3.78); EW 0.25% vs 0.05%. 1926–2005 VW: 0.16% vs 0.01%.
  * "Investors received no reward for bearing market risk except at turns of the month" (1926–2005); present in 31/35 countries; not driven by small caps, year-/quarter-ends, or measured month-end buying pressure.
  * Subperiods: 1987–mid-1996 diff 0.17 pp (t = 3.63); mid-1996–2005 diff 0.14 pp (t = 2.00) — already weakening.
  * Earlier trading-strategy evidence they cite: Hensel & Ziemba (1996) S&P 500 during TOM / T-bills otherwise beat buy-and-hold by 0.63 pp/yr (1928–93); Maberly & Waggoner (2000) found the effect in S&P futures disappeared after 1990.
* **First public date for OOS**: Ariel 1987 / L&S 1988 for the basic window; July 2006 for the McConnell–Xu restatement. Use **2006-08-01** (strict: 1988-01-01).

### 3.2 Exact rules (canonical)
Long the equity index from the **close of trading day −2** (so the position earns day −1's close-to-close return) through the **close of trading day +3**; otherwise T-bills/cash. ≈4 of ~21 trading days (~19% exposure), 12 round trips/yr.
Harness: decide at close of day −3 → MOC fill at close −2; decide at close +2 → MOC exit at close +3. (With next-open fills: buy open of day −1, sell open of day +4 — shifts the window by half a day.)

### 3.3 Post-publication evidence
* **Han, L., Han, Y., & Tian, S. (2025). "The disappearing turn-of-month effect."** *Finance Research Letters* 71: 106461. [doi:10.1016/j.frl.2024.106461](https://ideas.repec.org/a/eee/finlet/v71y2025ics1544612324014909.html). Abstract: the TOM effect "disappears entirely after 2001"; attribute it to lower transaction costs after decimalization. [VERIFIED abstract]
* Etula, Rinne, Suominen & Vaittinen (2020). "Dash for Cash: Monthly Market Impact of Institutional Liquidity Needs." *RFS* 33(1): 75–111. [doi:10.1093/rfs/hhz054](https://doi.org/10.1093/rfs/hhz054). Payment-cycle explanation; documents month-end patterns in liquid markets globally (secondary summaries report a wider [−3,+3] window and 1995–2013 sample — not verified).
* Chen & Chua (2011), *Journal of Financial Planning* (Apr 2011), "The Turn-of-the-Month Anomaly in the Age of ETFs": 1954–Apr 2010; after ETFs arrived the effect "migrated toward the first day of the month"; T-bill/index switching underperformed buy-and-hold by ~1.40%/yr after costs. [SECONDARY abstract via FPA page]
* Plastun, Sibande, Gupta & Wohar (2019). "Rise and fall of calendar anomalies over a century." *NAJEF* 49: 181–205 — DJIA 1900–2018: calendar anomalies (incl. TOM) "disappeared" since the 1980s (conflicts with McConnell–Xu for 1987–2005; methodology differs). [SECONDARY]
* Sullivan, Timmermann & White (2001), see §0: TOM is among the rules that lose significance under data-snooping correction.

### 3.4 Replication (SPY, mean daily close-to-close return, bp)

| Window | 1993–2005 TOM / other (t) | 2006–2026 TOM / other (t) | 2016–2026 (t) |
|---|---|---|---|
| [−1,+3] canonical | 11.5 / 2.8 (1.72) | 5.7 / 4.8 (**0.24**) | 7.1 / 6.0 (0.21) |
| [−2,+3] | 10.8 / 2.5 (1.80) | 6.8 / 4.4 (0.65) | 9.4 / 5.2 (0.86) |
| [−4,+3] | 8.3 / 2.6 (1.41) | 9.4 / 2.7 (1.91) | 9.0 / 4.8 (0.95) |

QQQ and IWM similarly: canonical [−1,+3] insignificant after 2006 (IWM TOM *below* other days). Strategy (SPY [−1,+3] only, cash otherwise) CAGR 2.5% vs 11.2% buy-and-hold 2006–2026. The wider [−4,+3] looks better, but was chosen after looking — treat as data-mined unless justified ex-ante (e.g., by Etula et al.'s cash-need mechanism).

### 3.5 Turnover / costs
12 round trips/yr; at 1 bp/side ≈ 0.24%/yr drag — costs are not the issue; lack of edge is.

### 3.6 Pitfalls
* Define "trading day −1" from the **exchange calendar**, not calendar days; month-end holidays (e.g., Good Friday at March-end) shift the window.
* Month boundary with the harness's "decide at close": the decision to enter must be one bar early; code this with a forward-known calendar, not with future bars.
* Don't mix with Halloween/pre-holiday without controlling overlap (TOM contains New Year pre-holiday days, etc.).

### 3.7 Robustness neighbors
Windows [−1,+3] (primary), [−1,+2], [−2,+3], [−3,+3], [−4,+3], Ariel [−1,+9]; SPY vs RSP (equal weight) vs IWM; subperiods 2001–2010 / 2011–2026.

---

## 4. Strategy 3 — Halloween indicator / "Sell in May and go away"

### 4.1 Sources and first public dates
* Bouman, S., & Jacobsen, B. (2002). "The Halloween Indicator, 'Sell in May and Go Away': Another Puzzle." *American Economic Review* 92(5): 1618–1635 (Dec 2002). [doi:10.1257/000282802762024683](https://www.aeaweb.org/articles?id=10.1257%2F000282802762024683). SSRN [76248](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=76248); a Nov-1997 working-paper draft exists ([copy](https://www.bnains.org/backtest/periode/The_Halloween_indicator_Sel_in_May_and_go_away_-_Sven_Bouman_&_Ben_Jacobsen,_1997.pdf)) [date as labeled, not independently verified]. Sample: 37 countries, 1970–Aug 1998; Nov–Apr returns higher than May–Oct in 36/37 countries; May–Oct returns ~zero.
* Zhang, C. Y., & Jacobsen, B. (2021). "The Halloween indicator, 'Sell in May and Go Away': Everywhere and all the time." *Journal of International Money and Finance* 110: 102268. [doi:10.1016/j.jimonfin.2020.102268](https://ideas.repec.org/a/eee/jimfin/v110y2021ics0261560620302242.html). SSRN [2154873](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2154873) (first posted ~2012; latest SSRN version dated 2018-10-01). Published abstract: 62,962 observations, Nov–Apr ~4% higher than May–Oct; summer excess returns ≈ −1%.
  * SSRN 2012 version [VERIFIED from PDF]: 108 markets, 55,425 monthly obs over 319 years; winter − summer = 4.52% (t = 9.69); 6.25% over the past 50 years; "beats the market more than 80% of the time over 5 year horizons". **OOS (Nov 1998–Apr 2011) US: buy-and-hold 1.73%/yr (σ 16.3%) vs Halloween 5.02%/yr (σ 11.3%); Halloween beat B&H in only 46% of years.**
* **First public date**: 1997 (working paper) / Dec 2002 (AER). Use **2002-11-01** as OOS start.

### 4.2 Exact rules
Hold the equity market index from the **end of October (close of last October trading day) to the end of April (close of last April trading day)**; hold **short-term T-bills** May–October (Bouman & Jacobsen; Jacobsen & Zhang use local 3-month T-bill yields). One round trip per year.
Harness: decide at close of the second-to-last trading day of October → MOC fill on the last October close (or next-open fill on the first November day; difference is one overnight). Out-of-market: BIL/SHV (2007+), SHY (2002+), cash earlier; a common "bonds instead of bills" variant uses IEF/TLT (2002+), but that is a different strategy (adds duration/stock-bond correlation exposure).

### 4.3 Post-publication evidence & critiques
* Supportive: Andrade, Chhaochharia & Fuerst (2013). "'Sell in May and Go Away' Just Won't Go Away." *FAJ* 69(4) ([T&F](https://www.tandfonline.com/doi/abs/10.2469/faj.v69.n4.4)) — OOS Nov 1998–Apr 2012 across 37 countries; winter returns ~10 pp higher (annualized half-year difference) on average; also appears in size, value, volatility and credit premia. [SECONDARY]
* Critical: Maberly, E. D., & Pierce, R. M. (2004). "Stock Market Efficiency Withstands another Challenge: Solving the 'Sell in May/Buy after Halloween' Puzzle." *Econ Journal Watch* 1(1): 29–46 ([PDF](https://econjwatch.org/file_download/24/2004-04-maberlypierce-com.pdf)) [VERIFIED]: for CRSP VW 1970–Aug 1998 the Halloween coefficient 1.03%/month (significant) becomes 0.78% (p = 0.092) after dummying **October 1987 and August 1998**; in S&P 500 futures (Apr 1982–Apr 2003) the effect is insignificant (t ≈ 0.66–1.01). Rebuttal: Witte, H. D. (2010), "Outliers and the Halloween Effect: Comment on Maberly and Pierce," *Econ Journal Watch* 7: 91–98.
* Critical: Dichtl, H., & Drobetz, W. (2015). "Sell in May and Go Away: Still good advice for investors?" *International Review of Financial Analysis* 38: 29–43 ([ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S1057521915000149)) — restricting to implementable periods and post-publication data, the effect "strongly weakened or even disappeared." [SECONDARY abstract]

### 4.4 Replication (SPY, annualized mean daily returns)

| Period | Nov–Apr | May–Oct | diff t | Strategy (cash 0%) CAGR / Sharpe / MDD | Buy&hold CAGR / Sharpe / MDD |
|---|---|---|---|---|---|
| 1993–Oct 2002 | 16.5% | 5.1% | 0.97 | 7.5% / 0.65 / −26.6% | 9.3% / 0.57 / −47.5% |
| Nov 2002–2026 | 14.6% | 10.7% | 0.52 | 6.5% / 0.53 / −36.5% | 11.5% / 0.68 / −55.2% |
| Nov 2012–2026 | 15.6% | 15.1% | 0.05 | 7.0% / 0.58 / −33.7% | 15.0% / 0.92 / −33.7% |

(Adding T-bill income for May–Oct would add ~0.5–1 pp/yr on average post-2002 — not enough to close the gap.) QQQ post-2002: summer *higher* than winter. Conclusion: in US large caps the effect is not detectable post-publication; the international evidence is stronger but not tradeable here beyond EFA/EEM (2001/2003+).

### 4.5 Turnover / costs
1 round trip/yr; costs irrelevant. Tax drag (short-term gains) not modeled.

### 4.6 Pitfalls
* Monthly-return papers implicitly switch at month-end closes — align the harness fill to the last October/April close.
* Outlier sensitivity (Oct-1987, Aug-1998, Oct-2008, Mar-2020): report results with and without those months.
* Cash return assumption dominates the comparison; don't use 0% cash in 2023–2025 (bills paid ~4–5%).

### 4.7 Robustness neighbors
Switch dates ±5 trading days; Nov–Apr vs Oct–Apr vs Nov–May; out-of-market asset {cash, BIL/SHY, IEF}; SPY vs EFA vs IWM; combine with a 10-month SMA trend filter only if pre-specified.

---

## 5. Strategy 4 — Pre-FOMC announcement drift

### 5.1 Sources and first public dates
* Lucca, D. O., & Moench, E. (2015). "The Pre-FOMC Announcement Drift." *Journal of Finance* 70(1): 329–371. [doi:10.1111/jofi.12196](https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12196). NY Fed Staff Report 512 ([link](https://www.newyorkfed.org/research/staff_reports/sr512.html)); draft states **"First Draft: September 2011"**. [VERIFIED from Feb-2013 draft]
  * Sample Sept 1994–Mar 2011 (intraday), plus daily data 1960–2011.
  * SPX rose on average **49 bp in the 24 h 2:00 pm→2:00 pm** before scheduled announcements (~3.89%/yr vs 0.88%/yr on all other days) — ~80% of realized excess returns; strategy holding SPX only in that window: annualized Sharpe **1.14**.
  * **Daily-bar relevant**: **close(t−1)→close(t)** excess return on FOMC days ≈ **33 bp** (other days < 1 bp), Sharpe **0.84**; close(t−1)→2 pm window Sharpe 1.43. The 2 pm→close afternoon of announcement day averaged ~zero.
  * 1980–1993 (daily, meeting day return): ~20 bp; 1960–1979: none. Drift not reversed on subsequent days. No effect in Treasuries/fed funds futures.
* **First public date**: **2011-09-01** (SR 512). OOS: from Apr-2011 (post-sample) or Oct-2011 (post-release).

### 5.2 Rules as they map to the harness
Scheduled FOMC announcement day *t* (last day of scheduled meeting). Hold equity index:
* (a) **LM daily analogue**: close(t−1) → close(t). Enter MOC at t−1 (decided at close t−2 — schedule known), exit MOC at t. Single fill type (MOC). ✔
* (b) **Overnight leg**: close(t−1) → open(t). Enter MOC at t−1, exit **MOO** at t. Requires mixed fill types.
* (c) **Open-to-open**: open(t−1) → open(t) (MOO/MOO), closest single-fill-type proxy to Boguth et al.'s finding that post-2011 the drift starts at the prior day's open.
Out-of-market: cash (8 events/yr; don't rotate into bills per event).

FOMC dates: **Federal Reserve** — current/recent calendars (2021–2027) at [fomccalendars.htm](https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm); historical years at `https://www.federalreserve.gov/monetarypolicy/fomchistoricalYYYY.htm` (index [fomc_historical_year.htm](https://www.federalreserve.gov/monetarypolicy/fomc_historical_year.htm), 1936–2020). On historical pages scheduled meetings are labeled "Meeting" (two-day meetings "January 29-30 Meeting"); unscheduled actions appear as "Conference Call" or "(unscheduled)" / "(cancelled)" (e.g., 2020: "March 2 (unscheduled)", "March 15 (unscheduled)", "March 17-18 (cancelled)"); calendars also show "notation vote" entries (e.g., 2025-08-22) — exclude all of these. Anomaly: the 2003 page lists both "September 15 Meeting" and "September 16 Meeting"; the statement was 2003-09-16 (I excluded 09-15). Announcement day = last listed day. My parser (`fomc_dates.py`) yields exactly 8 scheduled announcements per year 1994–2027 (7 in 2020). ALFRED "FOMC Press Release" release dates ([rid=101](https://alfred.stlouisfed.org/release/downloaddates?rid=101)) are a cross-check only (they include revisions/unscheduled actions).
Announcement times: typically ~2:15 pm ET before 2011 (secondary sources, e.g., BIS WP 1079; LM use a 2:00 pm cutoff "about fifteen minutes before the announcement"; very early-1994 timing may have varied — not verified); in 2011–2012, press-conference meetings released at **12:30 pm** (others 2:15 pm); **2:00 pm** for all meetings from 2013 (Fed press release 2013-03-13). Every meeting has had a press conference since 2019. With daily bars, window (a) always includes the announcement reaction.

### 5.3 Post-publication evidence
* Kurov, A., Wolfe, M. H., & Gilbert, T. (2021). "The disappearing pre-FOMC announcement drift." *Finance Research Letters* 40: 101781. [doi:10.1016/j.frl.2020.101781](https://pmc.ncbi.nlm.nih.gov/articles/PMC7525326/); first draft **2018-01-11**. [VERIFIED] E-mini S&P futures; window = open of day before → 15 min before announcement. Apr 2011–Dec 2015 press-conference meetings: 44.5 bp; **Jan 2016–Dec 2019: 9.2 bp**; non-press-conference meetings Apr 2011–Dec 2018: −5.1 bp. Drift "essentially disappeared after 2015"; associated with lower VIX.
* Boguth, Grégoire & Martineau (2019). "Shaping Expectations and Coordinating Attention: The Unintended Consequences of FOMC Press Conferences." *JFQA* 54(6): 2327–2353 — Apr 2011–Sep 2017 drift only before press-conference meetings; begins at prior day's open.
* Ignatieva & Ohashi (2025). *Applied Economics* 57(17): 2021–2037 — find a (short-lived) pre-FOMC drift and a profitable strategy. [SECONDARY]
* **Knox, B., & Vissing-Jorgensen, A. (2026). "The Effect of the Federal Reserve on the Stock Market: Magnitudes, Channels and Shocks." FEDS 2026-023** ([PDF](https://www.federalreserve.gov/econres/feds/files/2026023pap.pdf); dated Aug 25, 2025). [VERIFIED text] Reports "a substantial average overnight return of about 20 bps the night before the FOMC" and a "20 bps per meeting overnight drift since March 2011"; the 2pm-2pm drift averaged ~180 bp/meeting over the 15 meetings Mar-2008–Dec-2009 (a few crisis meetings drive much of the LM average).

### 5.4 Replication (SPY, scheduled announcement days)

| Window | Sep-1994–Mar-2011 (n=138) | Apr-2011–Sep-2026 (n=123) | Jan-2016–Sep-2026 (n=85) |
|---|---|---|---|
| (a) close(t−1)→close(t) | **33.9 bp** (t=3.41) | 12.0 bp (t=1.15) | 3.0 bp (t=0.26) |
| (b) close(t−1)→open(t) | 9.4 bp (t=1.58) | **17.7 bp** (t=4.35); normal nights 3.2 bp; diff t=3.44 | **16.4 bp** (t=3.42); diff t=2.58 |
| (c) open(t−1)→open(t) | 26.3 bp (t=2.35) | 17.2 bp (t=2.82) | 12.0 bp (t=1.61) |

QQQ: (b) 28.6 bp vs 4.3 bp normal nights, diff t = 4.24 (2011–2026); 27.4 bp (2016–2026). Note (a) matches LM's 33 bp close-to-close figure in-sample; the close-to-close version has decayed, but the overnight leg (flagged by Knox & Vissing-Jorgensen — so partly in my "look-ahead" set) persists.

### 5.5 Turnover / costs
8 round trips/yr. Edge per event ~12–18 bp vs round-trip cost ~1–2 bp (SPY/QQQ) → costs consume ~10–15%. Standalone CAGR is tiny (~1–1.5%/yr at 100% weight on 8 nights) — only useful as an overlay (e.g., bump equity weight on FOMC eve within the 1x cap).

### 5.6 Pitfalls
* Exclude unscheduled/intermeeting actions (Jan-2001, Apr-2001, Sep-2001, Jan-2008, Oct-2008, Mar-2020) and notation votes.
* Two-day meetings: day t−1 is meeting day 1 — correct entry is close of t−1 regardless.
* 2011–2012 12:30 pm releases: window (a)/(c) mechanics unchanged, but intraday interpretation differs.
* Small n (8/yr): a few crisis meetings dominate means; report medians and win rates, and results ex-2008–2009.
* If the harness allows only one fill type, (b) is not expressible; use (c) (MOO/MOO) and accept the weaker edge, or request a per-order `time_in_force`.

### 5.7 Robustness neighbors
Windows (a)/(b)/(c); close(t−2)→close(t−1); press-conference meetings only (2011–2018); SPY vs QQQ vs IWM; ex-GFC; conditional on VIX above median (Kurov et al.'s mechanism).

---

## 6. Strategy 5 — Pre-holiday effect

### 6.1 Sources and first public dates
* Ariel, R. A. (1990). "High Stock Returns before Holidays: Existence and Evidence on Possible Causes." *Journal of Finance* 45(5): 1611–1626 (Dec 1990). [doi:10.1111/j.1540-6261.1990.tb03731.x](https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1540-6261.1990.tb03731.x). 1963–1982: pre-holiday mean returns 9–14× other days; >1/3 of the market's total return earned on ~8 pre-holiday days/yr; high returns throughout the pre-holiday session.
* Lakonishok & Smidt (1988), RFS (see §3.1): DJIA 1897–1986 pre-holiday returns anomalously high.
* **First public date**: 1988 (L&S) / Dec 1990 (Ariel). Everything in an ETF-era backtest (1993+) is OOS.

### 6.2 Rules
Hold the index over the close-to-close return of the **last trading day before each exchange holiday** (Ariel's eight: New Year's Day, Presidents' Day, Good Friday, Memorial Day, July 4, Labor Day, Thanksgiving, Christmas; modern NYSE calendar adds MLK Day (1998+) and Juneteenth (2022+)). Enter MOC at close of day −2 (known calendar), exit MOC at close of the pre-holiday day. ~9–10 round trips/yr.

### 6.3 Post-publication evidence
* **Ko, K.-C., & Yang, N.-T. (2024). "The Pre-Holiday Premium of Ariel (1990) Has Largely Become a Small-Firm Effect Out of Sample."** *Critical Finance Review* 13(3–4): 531–538 ([PDF](https://cfr.ivo-welch.info/published/papers/ko2021pre.pdf)). [VERIFIED] Replication 1963–1982: VW 0.37% vs 0.03% (t = 7.03). 1983–2019: VW 0.14% (t = 1.92), insignificant after controlling for weekend/turn-of-year; t = 1.19 (1990–2019) and 1.23 (1995–2019); **S&P 500 t = 0.93, DJIA t = 0.64 for 1983–2019**; EW (small firms) still significant (t = 6.76).
* Chong, Hudson, Keasey & Littler (2005). "Pre-holiday effects: International evidence on the decline and reversal of a stock market anomaly." *JIMF* 24(8) — decline in US/UK/HK. [SECONDARY]

### 6.4 Replication

| ETF | Period | Pre-holiday mean (bp) | Overnight / intraday parts | Other days | diff t | % up |
|---|---|---|---|---|---|---|
| SPY | 1993–2026 (n=298) | 10.4 | 7.9 / 2.6 | 4.6 | 1.05 | 57% |
| SPY | 2009–2026 | 13.6 | 5.9 / 7.7 | 5.9 | 1.14 | 62% |
| IWM | 2009–2026 | 21.6 | 11.2 / 10.4 | 4.9 | 1.85 | 62% |

Consistent with Ko & Yang: not significant for large caps; small caps (IWM) directionally stronger but marginal.

### 6.5 Costs / turnover
~10 round trips/yr; edge per event ~5–15 bp over normal days; at 1–2 bp/side, costs take 20–60% of the *excess* edge. Only viable as an overlay on an existing equity allocation (i.e., don't round-trip from cash).

### 6.6 Pitfalls
* Derive holidays from a forward-known exchange calendar; exclude unscheduled closures (9/11 week, Hurricane Sandy, national days of mourning 2004-06-11, 2007-01-02, 2018-12-05, 2025-01-09) — deriving "pre-holiday" from gaps in price data incorrectly flags these.
* Early-close days (July 3, day after Thanksgiving, Dec 24) close at 1 pm — MOC still works but check the broker's CLS cutoff on half days [UNVERIFIED for Alpaca].
* Overlap with TOM (Dec 31/Jan) and Halloween — attribute carefully.

### 6.7 Robustness neighbors
Day −1 only vs days −2..−1; Ariel's 8 holidays vs full modern list; SPY vs IWM vs RSP; exclude year-end.

---

## 7. Strategy 6 — Overnight vs intraday returns (buy MOC, sell MOO)

### 7.1 Sources and first public dates
* Cliff, M., Cooper, M. J., & Gulen, H. (2008). "Return Differences between Trading and Non-Trading Hours: Like Night and Day." SSRN [1004081](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1004081) (abstract ID indicates posting around 2007; one index lists 2008-09-26 — exact first date **[UNVERIFIED]**; never published in a journal as far as I found). 1993–2006: US equity premium "solely due to overnight returns"; holds for stocks, indexes (incl. SPY) and index futures. Transaction-cost conclusions **[UNVERIFIED]**.
* Kelly, M. A., & Clark, S. P. (2011). "Returns in trading versus non-trading hours: The difference is day and night." *Journal of Asset Management* 12(2) [doi:10.1057/jam.2011.2](https://link.springer.com/article/10.1057/jam.2011.2). [SECONDARY]
* Lou, D., Polk, C., & Skouras, S. (2019). "A tug of war: Overnight versus intraday expected returns." *JFE* 134(1): 192–213. [doi:10.1016/j.jfineco.2019.03.011](https://personal.lse.ac.uk/polk/research/TugOfWar.pdf). [VERIFIED] Circulated by 2014 (conference presentations 2014–2015). Key facts for us: CRSP VW market 1993–2013 = **0.38%/month intraday vs 0.55%/month overnight** — i.e., *not* all overnight for the broad market; "for the largest stocks, essentially all of their risk premium is earned overnight" (so Dow/SPY-type proxies exaggerate the effect). Momentum/reversal profits split sharply overnight vs intraday; authors speculate high-frequency trading of these components "may be profitable after transaction costs for execution-savvy short-term investors," especially in index futures.
* Liu, Q., & Tse, Y. (2017). "Overnight returns of stock indexes: Evidence from ETFs and futures." *IREF* 48: 440–451 — 1999–2014 overnight returns of US index ETFs significantly positive, trading-hours returns negative. [SECONDARY abstract]
* Bondarenko, O., & Muravyev, D. (2023). "Market Return Around the Clock: A Puzzle." *JFQA* 58(3): 939–967 — E-mini S&P: the 4 hours around the European open account for the entire average market return (Sharpe 1.6, "remains high after transaction costs") — requires futures (not in scope).
* Boyarchenko, N., Larsen, L. C., & Whelan, P. (2023). "The Overnight Drift." *RFS* 36(9): 3502–3547 — ~100% of the equity premium earned 2–3 am ET in futures; linked to end-of-day order imbalances; selloffs → strong overnight reversals.
* **Boyarchenko, Larsen & Whelan (2026-07-01), "The Disappearing Overnight Drift," *Liberty Street Economics*** ([link](https://libertystreeteconomics.newyorkfed.org/2026/07/the-disappearing-overnight-drift/)) [VERIFIED summary]: the 2–3 am drift earned ~3.7%/yr 1998–2020 but "averaged close to zero since 2021"; attributed to a >50% compression in end-of-day order-imbalance dispersion. NightShares launched overnight ETFs (NSPY, NIWM) in June 2022; both closed within fourteen months.
* **First public date**: 2007–2008 (CCG SSRN). Use **2008-01-01** as OOS start (conservative: 2009).

### 7.2 Rules
Each day: buy index ETF at the **closing auction (MOC)**, sell at the next **opening auction (MOO)**; flat intraday (cash). 252 round trips/yr; 50% "time exposure" but 100% of overnight sessions.
Harness: needs both fill types every day (enter next-close, exit next-open). If only one fill type per strategy is supported, this strategy is not expressible.

### 7.3 Replication (annualized arithmetic means; Yahoo opens)

| ETF | Period | Overnight | Intraday | Overnight-only CAGR at 0 / 1 / 2 bp per round trip | Buy&hold CAGR |
|---|---|---|---|---|---|
| SPY | 1993–2006 | 12.9% | −1.2% | 13.3 / 10.5 / 7.7% | 10.7% |
| SPY | 2007–2016 | 5.5% | 3.3% | 4.8 / 2.2 / −0.3% | 6.9% |
| SPY | 2017–2026 | 11.1% | 4.8% | 11.0 / 8.2 / 5.5% | 15.4% |
| QQQ | 2017–2026 | 14.1% | 8.1% | 14.0 / 11.1 / 8.4% | 21.6% |
| IWM | 2017–2026 | 16.6% | −5.1% | 16.8 / 13.9 / 11.1% | 9.2% |
| DIA | 2021–2026 | 5.8% | 6.1% | 5.6 / 3.0 / 0.4% | 11.4% |

### 7.4 Assessment (skeptical)
* For SPY/QQQ/DIA, post-publication overnight-only returns are well below buy-and-hold even at 1 bp round-trip cost; the "night premium" of 1993–2006 is not a stable free lunch.
* Every 1 bp of round-trip cost = −2.5%/yr. Realistic all-in MOC+MOO cost for SPY is ~0.5–2 bp round trip, but the auction price vs vendor "open" discrepancy is of the same order as the edge — data error can manufacture or erase the anomaly.
* IWM's large intraday-negative/overnight-positive split in Yahoo data is striking but is exactly the pattern that is most vulnerable to open-price measurement (first print vs NYSE Arca auction), auction dislocation (Bogousslavsky & Muravyev 2023), and attention effects at the open (Berkman et al. 2012). A dedicated overnight IWM ETF (NIWM) failed commercially (closed within 14 months). **Do not deploy without validating against actual auction fills (e.g., Alpaca paper/live MOO/MOC fills or exchange auction prints) for several months.**
* Tax: 252 short-term realizations/yr.

### 7.5 Robustness neighbors
SPY/QQQ/IWM/DIA/MDY; conditional versions (only after down days — Boyarchenko et al.'s selloff asymmetry; only before FOMC — §5); subperiods 2008–2015 / 2016–2020 / 2021–2026; cost grid 0–4 bp round trip.

---

## 8. Strategy 7 — IBS (Internal Bar Strength) and other short-horizon ETF rules

### 8.1 IBS
* Pagonidis, A. S. "The IBS Effect: Mean Reversion in Equity ETFs." NAAIM white paper (2014 collection; research conducted 2013, data "from the inception for each ETF to 5/12/2013") — [PDF](https://www.naaim.org/wp-content/uploads/2014/04/00V_Alexander_Pagonidis_The-IBS-Effect-Mean-Reversion-in-Equity-ETFs-1.pdf); earlier copy on the author's QUSMA blog (upload path 2013/09). Practitioner paper, not peer-reviewed. [VERIFIED from PDF]
* **First public date: ~September 2013** (use 2013-05-13 as OOS start, the day after the data end).
* Definition: IBS = (Close − Low) / (High − Low) of the same day (0 = closed at low, 1 = closed at high).
* Findings (close-to-close next-day returns, US equity ETFs incl. SPY, QQQ, IWM, country ETFs): IBS < 0.2 → avg **+0.35%** next day; IBS > 0.8 → **−0.13%**. Non-linear thresholds ~0.4 and ~0.9. Stronger in high volatility, after wide-range days, in bear markets, on Mondays; **disappears on low-volume days for US ETFs**; mostly a US-session phenomenon (local-market ETFs abroad show little/none).
* Pagonidis' combined rule: "Go long at the close if RSI(3) < 10; maintain the position while RSI(3) ≤ 40" (Cutler's SMA-based RSI), filtered by "enter or maintain long position only if IBS ≤ 0.5". Across ETFs the IBS filter removed ~43% of days in market while raising total returns ~9.6 pp. SPY: RSI(3) only 205.1% total over 1,081 days in market vs filtered 205.5% over 692 days.
* The author notes the edge is concentrated at the close ("requirement of executing over a very small amount of time (near the end of the market closing)") — i.e., built on same-close execution.

Replication (IBS<0.2 → hold one day; Wilder RSI; SPY):

| Mode | 1993–May 2013 Sharpe (0 / 2 bp per side) | May 2013–2026 Sharpe (0 / 2 bp) |
|---|---|---|
| same_close | 0.92 / 0.76 | 0.63 / 0.47 |
| next_open | 1.00 / 0.83 | 0.53 / 0.37 |
| next_close | 0.52 / 0.36 | 0.71 / 0.54 |

~20% exposure; ~40–45 round trips/yr (≈ −0.8 to −0.9%/yr per bp/side). IWM next_open collapses post-2013 (Sharpe 0.26 at 0 cost). RSI(3)+IBS filter (Pagonidis rule): SPY next_open Sharpe 0.43 → 0.26 post-2013; QQQ 1.03 → 0.52. **Decayed after publication; use IBS only as an entry filter/ranking variable on RSI(2)/Double-7 type signals (e.g., require IBS < 0.25–0.5 at entry), not as a standalone daily-trading system.**
Alvarez ([2022-02-16 post](https://alvarezquanttrading.com/blog/internal-bar-strength-for-mean-reversion/)) reports that adding IBS<25 to an RSI(2)-based S&P 500 *stock* strategy kept 63% of trades and raised average profit per trade by 21% (next-open entries). [SECONDARY]

Pitfalls: IBS needs reliable high/low (vendor highs/lows can include bad prints; early-1990s ETF data especially); division by zero when High = Low; IBS is scale-invariant so adjusted vs raw OHLC doesn't matter if all fields are adjusted by the same factor.
Neighbors: thresholds {0.1, 0.15, 0.2, 0.25, 0.3}; exit {1-day, IBS > 0.8, close > prior high}; volume filter (require volume > 20-day median).

### 8.2 Other candidates considered and not recommended
* Day-of-week/"Turnaround Tuesday", monthly "week of month", January effect — covered by Sullivan–Timmermann–White's universe; weak post-publication; not documented further.
* Connors' 3-Day High/Low, %b, MDU/MDD, TPS (*HPETF*) — same family as RSI(2); rules only available second-hand; if tested, treat as parameter neighbors of §2 rather than independent evidence.
* Baltussen et al.'s MAC(5) index contrarian signal — academically grounded (§2.1) and implementable with daily bars (position ∝ −(4r_{t−1}+3r_{t−2}+2r_{t−3}+r_{t−4}) scaled by variance); long-only version = scale equity weight up after multi-day declines. Costs are the issue (daily rebalancing); consider as a research extension.

---

## 9. Suggested research plan for the harness

1. Build common infra: forward-known NYSE calendar (holidays, half-days), FOMC schedule file (Fed pages), per-order MOO/MOC support, cost model per §1.2, cash-sweep option.
2. Treat the **RSI(2)/Double-7/RSI(4) family on a basket of index + sector ETFs, next-open fills** as the primary mean-reversion sleeve; OOS start 2009-01-01; report 2001–2008 as "in-sample-ish" and 2009+ as OOS.
3. Test calendar overlays (TOM, pre-holiday, FOMC-eve) as **weight tilts within 1x** on an existing equity allocation rather than cash round trips; pre-register windows (canonical ones) and report the neighbor grid separately.
4. Keep Halloween and the overnight strategy as documented negatives (useful as sanity checks of the harness), unless auction-price validation changes the IWM overnight picture.
5. Always report: same_close (reference only), next_open, next_close; cost grid 0/1/2/4 bp per side; subperiods; trade counts; and a multiple-testing note (Sullivan–Timmermann–White; e.g., White's Reality Check / Hansen SPA over the grid actually searched).

---

## 10. References (with URLs)

Mean reversion
- Connors, L., & Alvarez, C. (2008). *Short Term Trading Strategies That Work.* TradingMarkets. ISBN 9780981923901. https://www.biblio.com/book/short-term-trading-strategies-work-larry/d/1510291032
- Connors, L., & Alvarez, C. (2009). *High Probability ETF Trading.* TradingMarkets. ISBN 9780615297415. https://www.biblio.com/9780615297415
- StockCharts ChartSchool, "RSI(2)". https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/rsi-2
- Alvarez, C. "Double 7's Strategy" (2016). https://alvarezquanttrading.com/blog/double-7s-strategy/ ; "Internal Bar Strength for Mean Reversion" (2022). https://alvarezquanttrading.com/blog/internal-bar-strength-for-mean-reversion/ ; "Mean Reversion Entry: At Open vs. Intraday Pullback vs Confirmation" (2021). https://alvarezquanttrading.com/blog/mean-reversion-entry-at-open-vs-intraday-pullback-vs-confirmation/
- Jegadeesh, N. (1990). JF 45(3): 881–898. https://onlinelibrary.wiley.com/doi/10.1111/j.1540-6261.1990.tb05110.x
- Lehmann, B. (1990). QJE 105(1): 1–28. https://academic.oup.com/qje/article-abstract/105/1/1/1928416 ; NBER w2533: https://www.nber.org/papers/w2533
- Nagel, S. (2012). "Evaporating Liquidity." RFS 25(7): 2005–2039. https://academic.oup.com/rfs/article-abstract/25/7/2005/1602153
- Baltussen, G., van Bekkum, S., & Da, Z. (2019). JFE 132(1): 26–48. https://www3.nd.edu/~zda/Indexing.pdf
- Micaletti, R. (2023). SSRN 4339128. https://www.ssrn.com/abstract=4339128
- Pagonidis, A. S. (2013/2014). "The IBS Effect: Mean Reversion in Equity ETFs." NAAIM. https://www.naaim.org/wp-content/uploads/2014/04/00V_Alexander_Pagonidis_The-IBS-Effect-Mean-Reversion-in-Equity-ETFs-1.pdf

Calendar
- Ariel, R. A. (1987). JFE 18(1): 161–174. https://www.sciencedirect.com/science/article/abs/pii/0304405X87900663
- Ariel, R. A. (1990). JF 45(5): 1611–1626. https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1540-6261.1990.tb03731.x
- Lakonishok, J., & Smidt, S. (1988). RFS 1(4): 403–425. https://academic.oup.com/rfs/article-abstract/1/4/403/1566965
- McConnell, J. J., & Xu, W. (2008). FAJ 64(2): 49–64. https://www.tandfonline.com/doi/abs/10.2469/faj.v64.n2.11 ; SSRN 917884; PDF: https://business.purdue.edu/faculty/mcconnell/publications/Equity-Returns-at-the-Turn-of-the-Month.pdf
- Han, L., Han, Y., & Tian, S. (2025). FRL 71: 106461. https://ideas.repec.org/a/eee/finlet/v71y2025ics1544612324014909.html
- Etula, E., Rinne, K., Suominen, M., & Vaittinen, L. (2020). RFS 33(1): 75–111. https://doi.org/10.1093/rfs/hhz054
- Chen, H., & Chua, A. (2011). Journal of Financial Planning (Apr). https://www.financialplanningassociation.org/article/journal/APR11-turn-month-anomaly-age-etfs-reexamination-return-enhancement-strategies
- Plastun, A., Sibande, X., Gupta, R., & Wohar, M. E. (2019). NAJEF 49: 181–205. https://ideas.repec.org/a/eee/ecofin/v49y2019icp181-205.html
- Pham, B. (2003?). "A Monthly Effect in Stock Returns: Revisited." SFU thesis. https://summit.sfu.ca/_flysystem/fedora/sfu_migrate/10272/etd2038.pdf
- Bouman, S., & Jacobsen, B. (2002). AER 92(5): 1618–1635. https://www.aeaweb.org/articles?id=10.1257%2F000282802762024683
- Zhang, C. Y., & Jacobsen, B. (2021). JIMF 110: 102268. https://ideas.repec.org/a/eee/jimfin/v110y2021ics0261560620302242.html ; SSRN 2154873 (2012 version PDF: https://www.bnains.org/backtest/periode/The_Halloween_Indicator_everywhere_and_all_the_time_-_Ben_Jacobsen_&_Cherry_Y._Zhang.pdf)
- Andrade, S., Chhaochharia, V., & Fuerst, M. (2013). FAJ 69(4). https://www.tandfonline.com/doi/abs/10.2469/faj.v69.n4.4
- Maberly, E. D., & Pierce, R. M. (2004). Econ Journal Watch 1(1): 29–46. https://econjwatch.org/file_download/24/2004-04-maberlypierce-com.pdf
- Witte, H. D. (2010). Econ Journal Watch 7: 91–98. https://econjwatch.org/authors/h-douglas-witte
- Dichtl, H., & Drobetz, W. (2015). IRFA 38: 29–43. https://www.sciencedirect.com/science/article/abs/pii/S1057521915000149
- Ko, K.-C., & Yang, N.-T. (2024). Critical Finance Review 13(3–4): 531–538. https://cfr.ivo-welch.info/published/papers/ko2021pre.pdf
- Chong, R., Hudson, R., Keasey, K., & Littler, K. (2005). JIMF 24(8). https://www.sciencedirect.com/science/article/abs/pii/S0261560605000938
- Sullivan, R., Timmermann, A., & White, H. (2001). "Dangers of data mining: The case of calendar effects in stock returns." J. Econometrics 105(1): 249–286. https://www.sciencedirect.com/science/article/abs/pii/S030440760100077X ; 1998 WP: https://escholarship.org/content/qt2z02z6d9/qt2z02z6d9.pdf

FOMC
- Lucca, D. O., & Moench, E. (2015). JF 70(1): 329–371. https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12196 ; SR512: https://www.newyorkfed.org/research/staff_reports/sr512.html ; draft PDF: https://conference.nber.org/confer/2013/MEs13/Lucca_Moench.pdf
- Kurov, A., Wolfe, M. H., & Gilbert, T. (2021). FRL 40: 101781. https://pmc.ncbi.nlm.nih.gov/articles/PMC7525326/
- Boguth, O., Grégoire, V., & Martineau, C. (2019). JFQA 54(6): 2327–2353. https://www.ssrn.com/abstract=2698477
- Ignatieva, K., & Ohashi, K. (2025). Applied Economics 57(17): 2021–2037. https://www.tandfonline.com/doi/full/10.1080/00036846.2024.2322573
- Knox, B., & Vissing-Jorgensen, A. (2026). FEDS 2026-023. https://www.federalreserve.gov/econres/feds/files/2026023pap.pdf
- Federal Reserve FOMC calendars: https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm ; historical: https://www.federalreserve.gov/monetarypolicy/fomc_historical_year.htm (per-year pages fomchistoricalYYYY.htm)
- Fed press release on 2 pm statement timing (2013-03-13): https://www.federalreserve.gov/newsevents/pressreleases/monetary20130313a.htm

Overnight / microstructure / costs
- Cliff, M., Cooper, M., & Gulen, H. (2008). SSRN 1004081. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1004081
- Kelly, M. A., & Clark, S. P. (2011). J. Asset Management 12(2). https://link.springer.com/article/10.1057/jam.2011.2
- Lou, D., Polk, C., & Skouras, S. (2019). JFE 134(1): 192–213. https://personal.lse.ac.uk/polk/research/TugOfWar.pdf
- Liu, Q., & Tse, Y. (2017). IREF 48: 440–451. https://ideas.repec.org/a/eee/reveco/v48y2017icp440-451.html
- Bondarenko, O., & Muravyev, D. (2023). JFQA 58(3): 939–967. https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3596245
- Boyarchenko, N., Larsen, L. C., & Whelan, P. (2023). RFS 36(9): 3502–3547. https://academic.oup.com/rfs/article-abstract/36/9/3502/7076616
- Boyarchenko, N., Larsen, L. C., & Whelan, P. (2026). "The Disappearing Overnight Drift." Liberty Street Economics. https://libertystreeteconomics.newyorkfed.org/2026/07/the-disappearing-overnight-drift/
- Bogousslavsky, V., & Muravyev, D. (2023). J. Financial Markets 66. https://www.ssrn.com/abstract=3485840
- Berkman, H., Koch, P. D., Tuttle, L., & Zhang, Y. J. (2012). JFQA 47(4). https://www.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/abs/paying-attention-overnight-returns-and-the-hidden-cost-of-buying-at-the-open/F9AAD159B512C651F09D5D52011D88E0
- Alpaca order docs (OPG/CLS cutoffs): https://docs.alpaca.markets/us/docs/orders-at-alpaca
- FINRA Section 31 fee notices: https://www.finra.org/rules-guidance/notices/information-notice-20250424 ; https://www.finra.org/rules-guidance/notices/information-notice-20260317
- SSGA, "SPY liquidity" (2026-08-28): https://www.ssga.com/us/en/institutional/insights/spy-liquidity-flexibility-to-navigate-any-market
- Chicago Fed (2003), "Decimalization and market liquidity": https://www.chicagofed.org/~/media/publications/economic-perspectives/2003/4qeppart1-pdf.pdf

## 11. Items I could not verify
- Primary text of both Connors books (exact thresholds for Cumulative RSI, RSI 25/75 exit, R3 details, reported win rates/periods). The core RSI(2) rules are consistent across multiple secondary sources; everything else is [SECONDARY].
- Whether the 2004 first edition of *How Markets Really Work* contained RSI(2) rules (affects the strict OOS date).
- Exact first SSRN posting dates for Cliff–Cooper–Gulen and Bouman–Jacobsen (SSRN blocked automated access).
- Whether Alpaca restricts OPG/CLS orders to certain account types; CLS cutoff on half-days.
- SPY's pre-2001 quoting increment on AMEX; Kelly & Clark's and CCG's transaction-cost conclusions.
- Whether vendor (Yahoo) "open" equals the primary-exchange opening auction price for SPY/IWM/QQQ.
