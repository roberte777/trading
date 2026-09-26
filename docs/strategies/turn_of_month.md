# Turn of the month (McConnell & Xu 2008)

Strategy `turn_of_month`, class `TurnOfTheMonth` in `src/trader/strategies/turn_of_month.py`, config `configs/strategies/turn_of_month.yaml`, results `results/turn_of_month/`.

## Summary

- A documented calendar anomaly, tested here as a negative control for the harness.
- Hold SPY over the turn-of-month window, trading day −1 (the last session of the month) through trading day +3. Hold T-bills (BIL) on every other session.
- The window depends only on the NYSE calendar, which is known in advance, so the strategy uses no price data beyond checking that SPY and BIL have a price.
- About 12 round trips a year, with SPY held on 19% of sessions.
- Result: the effect is visible in 2000–2006, but it is gone after publication. From July 2006 to September 2026 the strategy returned 0.79% a year net of costs (Sharpe −0.06). It also trails a static blend with the same SPY exposure, even before costs. This matches Han, Han & Tian (2025).

## Sources

- Ariel, R.A. (1987). "A Monthly Effect in Stock Returns." *Journal of Financial Economics* 18(1), 161–174. https://doi.org/10.1016/0304-405X(87)90066-3
  - CRSP 1963–1981: positive mean returns only from trading day −1 to +9, strongest from −1 to about +4.
- Lakonishok, J. & Smidt, S. (1988). "Are Seasonal Anomalies Real? A Ninety-Year Perspective." *Review of Financial Studies* 1(4), 403–425. https://doi.org/10.1093/rfs/1.4.403
  - DJIA 1897–1986. Defines the [−1, +3] window used here. The 4-day window returned 0.473% on average, against 0.349% for the whole month.
- McConnell, J.J. & Xu, W. (2008). "Equity Returns at the Turn of the Month." *Financial Analysts Journal* 64(2), 49–64. https://doi.org/10.2469/faj.v64.n2.11. First posted as SSRN 917884 in July 2006: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=917884
  - Defines the rule as implemented here.
- Critiques and post-publication evidence:
  - Han, L., Han, Y. & Tian, S. (2025). "The disappearing turn-of-month effect." *Finance Research Letters* 71, 106461. https://doi.org/10.1016/j.frl.2024.106461
  - Sullivan, R., Timmermann, A. & White, H. (2001). "Dangers of data mining: The case of calendar effects in stock returns." *Journal of Econometrics* 105(1), 249–286. https://doi.org/10.1016/S0304-4076(01)00077-X
  - Chen, H. & Chua, A. (2011). "The Turn-of-the-Month Anomaly in the Age of ETFs." *Journal of Financial Planning* (April). https://www.financialplanningassociation.org/article/journal/APR11-turn-month-anomaly-age-etfs-reexamination-return-enhancement-strategies
  - Etula, E., Rinne, K., Suominen, M. & Vaittinen, L. (2020). "Dash for Cash: Monthly Market Impact of Institutional Liquidity Needs." *Review of Financial Studies* 33(1), 75–111. https://doi.org/10.1093/rfs/hhz054
- **Publication date for the out-of-sample split: 2006-07-01**, the SSRN posting of McConnell & Xu.
  - The basic window was already public in 1987–88. By that stricter date, the whole backtest from 2000 is out of sample, including the period labelled "in-sample" below.

## Rules as implemented

- Universe: `SPY`, `BIL`.
- Schedule: `Daily()`. The strategy makes a decision at the close of every session.
- Params (published defaults): `days_before = 1`, `days_after = 3`.
- Orders placed at the close of session *t* fill at the open of the next session, `n = calendar.next_session(t)`. `n` is in the window if either of these holds:
  - `calendar.sessions_left_in_month(n) < days_before`. With the default of 1, this means `n` is the last session of the month (day −1).
  - `calendar.session_of_month(n) <= days_after`. With the default of 3, this means `n` is session 1, 2 or 3 of the month.
- If `n` is in the window and SPY has a price today, the target is `{"SPY": 1.0}`.
- Otherwise the target is `{"BIL": 1.0}`. If BIL has no price either, the target is `{}` (cash). A symbol without data never gets weight.
- Execution: `next_open`, with `rebalance_band: 0.02`.
  - Entries and exits always trade.
  - The band only suppresses tiny top-ups while a position is already held.
- Sessions come from the exchange calendar, not calendar days, so month-end holidays are handled. When Good Friday falls on the 29th (2013, 2024), Thursday the 28th is day −1. The unit tests cover this.
- Verification: `weights.parquet` holds SPY at the close of exactly these sessions: the last session of each month and sessions 1–3 of the next month.
  - This covers all 6,722 sessions from 2000-01-04 to 2026-09-25, with zero mismatches.
  - Example: SPY is held at the closes of 2008-09-30, 10-01, 10-02 and 10-03, then BIL from 10-06.
  - Example: 2024-03-28 (Good Friday was the 29th), 04-01, 04-02 and 04-03.

## ETF mapping and proxies

| Symbol | Role | Real data from | Proxy before that |
|---|---|---|---|
| SPY | S&P 500 (stands in for CRSP VW / DJIA) | 1993-01-29 | VFINX (not used: the backtest starts in 2000) |
| BIL | T-bills | 2007-05-30 | `@tbill`: a synthetic T-bill index accrued from ^IRX, net of a 0.10% fee |

- 22% of the backtest's holdings are in proxy data. All of it is the synthetic BIL from 2000 to 2007.
- The `etf_era` variant starts on 2007-05-31 and uses no proxy data.

## Deviations from the source

- **Half-day shift from next-open fills.**
  - The paper window is close-to-close. It is entered at the close of day −2 and exited at the close of day +3.
  - With next-open fills, the harness holds SPY from the **open of day −1 to the open of day +4**.
  - As a result, it misses the overnight gap into day −1 and earns the overnight gap into day +4.
  - The replication below shows that this shift barely changes the per-day averages.
- **The robustness variants shift the window.**
  - `exec_next_close` holds SPY from the close of day −1 to the close of day +4. That earns days +1 to +4, which is a different window, not the canonical close-to-close one.
  - `delay_2` moves the whole window one session later.
- **The index is SPY, not CRSP VW or the DJIA.** SPY bars are total-return adjusted.
- **T-bills are held as the BIL ETF.**
  - The strategy rotates SPY into BIL on every exit, as the spec requires.
  - This doubles the number of fills compared with holding idle cash.
  - Idle cash left over from share rounding earns 0%.
- **Costs.**
  - Each fill pays 5 bps of slippage plus SEC/TAF/CAT fees.
  - Orders are whole shares.
  - Each month has 4 fills (sell BIL, buy SPY, sell SPY, buy BIL). That is 48 fills and about 2.4% of cost drag a year.
  - The source papers ignore costs.
- **Long-only and unlevered, as in the source.** There is no short leg on the non-turn-of-month days.

## Known critiques and post-publication evidence

- **McConnell & Xu already found the effect weakening.**
  - CRSP VW 1987–2005: turn-of-month days averaged 0.15%/day against −0.00% on other days (t = 3.78).
  - The difference fell from 0.17 pp (t = 3.63) in 1987–mid-1996 to 0.14 pp (t = 2.00) in mid-1996–2005.
- **Maberly & Waggoner (2000), cited by McConnell & Xu:** the effect in S&P futures disappeared after 1990.
- **Han, Han & Tian (2025):** the effect "disappears entirely after 2001". They attribute this to lower transaction costs after decimalization.
- **Chen & Chua (2011):** after ETFs arrived, the effect "migrated toward the first day of the month". Switching between T-bills and the index underperformed buy-and-hold by about 1.40%/yr after costs. (This comes from a secondary summary.)
- **Sullivan, Timmermann & White (2001):** calendar rules, turn of the month included, lose significance once you correct for the universe of calendar rules searched.
  - Wider windows such as [−4, +3] look better after 2006, but they were chosen after looking at the data.
  - Etula et al. (2020) offer a payment-cycle explanation, but it does not justify widening the window ex ante.
- **Plastun, Sibande, Gupta & Wohar (2019, *NAJEF* 49):** DJIA calendar anomalies, including this one, "disappeared" from the 1980s on.
- **Research replication (the spec's sanity check):** SPY turn-of-month days against other days, 2006–2026, t = 0.24. SPY in the window and cash otherwise returned a 2.5% CAGR, against 11.2% for buy-and-hold.

## Results

Backtest period: 2000-01-03 to 2026-09-25 (26.7 years), `next_open`, default costs. Source: `results/turn_of_month/summary.json`.

### Headline metrics

| Metric | Full period | In-sample (2000-01-03 → 2006-06-30) | Out-of-sample (2006-07-03 → 2026-09-25) |
|---|---|---|---|
| CAGR | 1.79% | 4.96% | 0.79% |
| Volatility | 8.13% | 8.20% | 8.11% |
| Sharpe | 0.02 | 0.28 | −0.06 |
| Sortino | 0.03 | 0.41 | −0.08 |
| Max drawdown | −27.6% | −15.3% | −27.6% |
| Calmar | 0.06 | 0.32 | 0.03 |
| SPY CAGR (benchmark) | 8.31% | −0.67% | 11.35% |
| Beta to SPY | 0.18 | 0.19 | 0.18 |

Trading and statistical metrics:

- Turnover: 24.0x a year, with 48.2 fills a year (24 SPY and 24 BIL).
- Cost drag: 2.45% a year.
- SPY exposure: 19.0% on average.
- Longest drawdown: 3,946 days.
- Bootstrap 90% CI for the Sharpe ratio: [−0.25, 0.32].
- P(Sharpe > SPY's Sharpe) = 0.01.
- Deflated Sharpe ratio over the 10 suite trials: 0.007.

Trade count check: there are 24 SPY and 24 BIL fills in every full year. Across 26 years there are 4 extra fills: 2001-04, 2009-03, 2020-03 and 2020-04. Each is a band top-up after a buy that the harness scaled down on a gap-up open.

### Crisis returns

| Episode | Return |
|---|---|
| Dot-com bust (2000-03 → 2002-10) | +0.3% |
| GFC (2007-10 → 2009-03) | −21.5% |
| Euro/US downgrade (2011-04 → 2011-10) | −12.9% |
| Q4 2018 selloff | −0.4% |
| COVID crash (2020-02 → 2020-03) | +5.5% |
| 2022 inflation bear | +1.5% |
| 2025 tariff shock (2025-02 → 2025-04) | −6.3% |

- Holding SPY for only 4 sessions does not protect against crashes. The 7 worst days of the backtest all fall inside the window (or in the overnight gap into day +4). The worst was 2008-12-01 (−8.8%, day +1), followed by 2025-04-03 (−4.9%, day +3) and 2020-04-01 (−4.5%, day +1).
- With about 1/5 exposure, the GFC loss of −21.5% is disproportionately large.

### Daily-return replication (SPY, mean return per session)

| Period | Paper window: close-to-close [−1, +3], turn of month / other days (t) | As traded: open −1 → open +4 (t) |
|---|---|---|
| 1993-02 → 2005-12 | 11.5 / 2.8 bp (1.72) | 11.8 / 2.9 bp (1.78) |
| 2000-01 → 2006-06 (in-sample) | 9.3 / −1.7 bp (1.48) | 10.3 / −1.9 bp (1.63) |
| 2006-07 → 2026-09 (out-of-sample) | 5.7 / 4.8 bp (0.21) | 4.8 / 5.0 bp (−0.06) |
| 2016-01 → 2026-09 | 7.1 / 6.0 bp (0.21) | 8.2 / 5.7 bp (0.47) |

- The paper-window numbers match the research replication: 11.5 / 2.8 bp (t = 1.72) and 5.7 / 4.8 bp (t = 0.24).
- The half-day shift from next-open fills does not change the conclusion.
- After publication, turn-of-month sessions earn the same as any other session.

### Exposure-adjusted comparison

| Period | Strategy, net | Strategy, 0x costs | 25% × SPY CAGR | Static 25% SPY / 75% BIL | Static 19% SPY / 81% BIL | SPY | BIL |
|---|---|---|---|---|---|---|---|
| Full, 2000–2026 | 1.79% | 4.31% | 2.08% | 3.79% | 3.34% | 8.31% | 1.85% |
| In-sample, 2000 → 2006-06 | 4.96% | 7.58% | −0.17% | 2.26% | 2.41% | −0.67% | 2.79% |
| Out-of-sample, 2006-07 → 2026 | 0.79% | 3.29% | 2.84% | 4.28% | 3.64% | 11.35% | 1.55% |

- All numbers are CAGRs.
- The static blends are rebalanced daily with no costs. Their volatility is 3.6% (19% SPY) and 4.8% (25% SPY), against 8.1% for the strategy.
- **In-sample**, the timing adds real value: 7.6% gross against 2.4% for the exposure-matched blend.
- **Out-of-sample**, the strategy trails the exposure-matched blend even gross of costs (3.29% against 3.64%).
  - It also trails 25% × SPY after costs (0.79% against 2.84%).
  - It carries more than twice the blend's volatility.
  - The timing adds only risk: the strategy bears full SPY volatility on 4 sessions instead of 19% volatility on every session.

### Robustness suite (`variants.json`)

| Variant | Description | CAGR | Vol | Sharpe | Sortino | Max DD | Calmar | Turnover | Cost drag |
|---|---|---|---|---|---|---|---|---|---|
| base | published params | 1.79% | 8.13% | 0.02 | 0.03 | −27.6% | 0.06 | 24.0x | 2.45% |
| `costs_0x` | all trading costs x0 | 4.31% | 8.11% | 0.32 | 0.45 | −20.6% | 0.21 | 24.0x | 0.00% |
| `costs_2x` | all trading costs x2 | −0.68% | 8.18% | −0.28 | −0.37 | −45.4% | −0.02 | 24.0x | 4.91% |
| `costs_4x` | all trading costs x4 | −5.43% | 8.35% | −0.86 | −1.11 | −80.5% | −0.07 | 23.9x | 9.83% |
| `exec_next_close` | fill at next close (window becomes [+1, +4]) | 2.32% | 8.52% | 0.09 | 0.12 | −30.3% | 0.08 | 24.0x | 2.45% |
| `delay_2` | fill one session later (window shifts +1) | 1.62% | 8.39% | 0.00 | 0.01 | −22.7% | 0.07 | 24.0x | 2.45% |
| `param_days_before=2` | window [−2, +3] | 2.58% | 8.97% | 0.11 | 0.16 | −29.3% | 0.09 | 24.0x | 2.45% |
| `param_days_after=2` | window [−1, +2] | 1.06% | 7.11% | −0.09 | −0.12 | −28.9% | 0.04 | 24.0x | 2.45% |
| `param_days_after=4` | window [−1, +4] | 2.19% | 9.37% | 0.07 | 0.10 | −26.4% | 0.08 | 24.0x | 2.45% |
| `etf_era` | start 2007-05-31, no proxy data | 0.61% | 8.25% | −0.06 | −0.09 | −27.6% | 0.02 | 24.0x | 2.45% |

- Every neighbouring window has a Sharpe ratio between −0.09 and 0.11 after costs.
- Even with zero costs, the full-period Sharpe is only 0.32, and nearly all of it comes from 2000–2006.

### Comparison with the sources

- **McConnell & Xu, CRSP VW 1987–2005:** a 15 bp/day spread (t = 3.78).
  - On SPY over the overlapping 1993–2005 period, the spread is 8.7 bp (t = 1.72).
  - That is smaller, but consistent with the decline they report for mid-1996–2005 (14 bp, t = 2.00). SPY is a large-cap index, where the effect was always weaker than in equal-weighted CRSP.
- **Hensel & Ziemba (1996), cited by McConnell & Xu:** S&P 500 in the window and T-bills otherwise beat buy-and-hold by 0.63 pp/yr in 1928–93.
  - Here the strategy trails SPY by 6.5 pp/yr over the full period and by 10.6 pp/yr out of sample.
  - Most of that gap is the equity premium earned outside the window, which now accrues on ordinary days.
- **Research replication, 2006–2026:** SPY in the window and 0% cash otherwise returned a 2.5% CAGR, with no costs.
  - This backtest returns 3.29% out of sample with zero costs. The difference is the roughly 1.25%/yr of BIL yield (1.55% earned 81% of the time).
  - After costs it returns 0.79%.
- **Costs:**
  - Half of the 2.45% annual cost drag comes from the BIL legs. That nearly cancels BIL's yield: about 1.2%/yr in costs against about 1.25–1.5%/yr of T-bill return.
  - At the 1–2 bps slippage that SPY and BIL actually trade at, the drag would be about 0.5–1%/yr.
  - Even then, the out-of-sample result would trail the exposure-matched blend, because the gross result already does.

## Assessment

- **This is not a live candidate.**
- The turn-of-month edge is statistically indistinguishable from zero in SPY after 2006 (t ≈ 0 as traded). This matches Han, Han & Tian (2025) and the spec's expectation for a negative control.
- The harness passes this negative-control test: the timing is verified session by session, and it shows no spurious post-publication edge.
- The 2000–2006 in-sample edge (Sharpe 0.28, 4.96% CAGR while SPY lost money) is real in the data, but it did not persist.
