# Defensive Asset Allocation (DAA-G12)

Registry name `keller_daa`, class `DefensiveAssetAllocation`, module `src/trader/strategies/keller_daa.py`, config `configs/strategies/keller_daa.yaml`.

## Summary

- A monthly relative-momentum rotation across 12 global asset-class ETFs. Crash protection comes only from a separate two-asset "canary" universe (VWO, BND).
- When both canaries have positive 13612W momentum, it holds the top 6 risky assets at 1/6 each.
- With one bad canary, half the portfolio moves into the single best bond "cash" asset (SHY, IEF or LQD). With two bad canaries, all of it does.
- The risky assets are ranked but never trend-filtered. Only the canaries decide how much is at risk.

## Sources

- Keller, W.J., Keuning, J.W. (2018). "Breadth Momentum and the Canary Universe: Defensive Asset Allocation (DAA)." SSRN Working Paper 3212862, posted 1 Aug 2018 (dated 12 Jul 2018, last revised 7 Sep 2021). https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3212862
- Keuning, J.W. (2018). "Announcing Defensive Asset Allocation." TrendXplorer blog (co-author; rules and result tables). https://indexswingtrader.blogspot.com/2018/07/announcing-defensive-asset-allocation.html
- CXO Advisory (2018). "Multi-class Momentum Portfolio with Canary Crash Protection." https://www.cxoadvisory.com/strategic-allocation/multi-class-momentum-portfolio-with-canary-crash-protection/
- Keller, W.J., Keuning, J.W. (2023). "Dual and Canary Momentum with Rising Yields/Inflation: Hybrid Asset Allocation (HAA)." SSRN Working Paper 4346906 (the authors' own later critique). https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4346906
- **Out-of-sample split: `publication_date = 2018-08-01`** (SSRN posting). The paper's sample ends 2018-03, and its parameters were chosen in-sample, so only data after 2018-08-01 is an honest test.

## Rules as implemented

Decisions are made at the close of the last session of each month (`MonthEnd()`). Orders fill at the next session's open.

1. **Momentum.** For every symbol, compute 13612W = `(12·r1 + 4·r3 + 2·r6 + 1·r12) / 4` with `r_k = p0/p_k − 1` on month-end total-return closes (`indicators.momentum_13612w`).
   - `p0` is the decision close and `p_k` is the close `k` month-ends earlier.
   - A symbol needs 13 month-end closes (p0 through p12) to have a value.
2. **Canary.** `b` = the number of {VWO, BND} with 13612W ≤ 0. A canary without a momentum value counts as bad.
3. **Cash fraction.** `CF = min(1, b / breadth)`, then "easy trading" rounding: `CF = floor(CF · top_n) / top_n`.
   - With the defaults (`top_n = 6`, `breadth = 2`): b = 0 → 0, b = 1 → 0.5, b = 2 → 1.
4. **Risky part.** The top `round((1 − CF) · top_n)` risky assets by 13612W, each at `1/top_n`.
   - Ranking uses a stable sort, so ties keep universe order.
   - There is no absolute-momentum filter on the risky assets.
5. **Cash part.** `1 − (number of risky assets held) / top_n` goes to the single best of {SHY, IEF, LQD} by 13612W, even if its momentum is negative.
   - In normal operation this equals CF.
   - If fewer risky assets are eligible than there are slots, the empty slots also go to the cash asset. This never happened in the backtest, because at least 10 risky assets were always eligible.
6. **LQD overlap.** LQD is both a risky and a cash asset. If it is picked in both roles, its weights are summed.
7. **Eligibility.** A symbol can be ranked only when it has a close at this decision (carried forward over at most 5 missing sessions) and a finite 13612W. Symbols without 12 months of history are never ranked, so they never get weight.
8. **Parameters.** `top_n = 6` (T) and `breadth = 2` (B) are the published DAA-G12 values. `param_grid = {"top_n": [4, 5], "breadth": [1]}`.

## ETF mapping and proxies

The universe is the published DAA-G12 one. Proxies come from `proxies_for`, and their returns extend each ETF backwards (`loader.splice`).

| Role | ETF | Proxy before ETF inception | Series starts | Real ETF from |
|---|---|---|---|---|
| Risky | SPY | VFINX | 1980-01 | 1993-01 |
| Risky | IWM | NAESX | 1980-01 | 2000-05 |
| Risky | QQQ | RYOCX | 1994-02 | 1999-03 |
| Risky | VGK | VEURX | 1990-06 | 2005-03 |
| Risky | EWJ | none | 1996-03 | 1996-03 |
| Risky + canary | VWO | VEIEX | 1994-05 | 2005-03 |
| Risky | VNQ | VGSIX | 1996-05 | 2004-09 |
| Risky | GSG | PCRIX | **2002-07** | 2006-07 |
| Risky | GLD | GC=F (front-month COMEX futures) | **2000-08** | 2004-11 |
| Risky | TLT | VUSTX | 1986-05 | 2002-07 |
| Risky | HYG | VWEHX | 1980-01 | 2007-04 |
| Risky + cash | LQD | VFICX | 1993-10 | 2002-07 |
| Cash | SHY | VFISX | 1991-10 | 2002-07 |
| Cash | IEF | VFITX | 1991-10 | 2002-07 |
| Canary (signal only) | BND | VBMFX | 1986-12 | 2007-04 |

- **Time-varying universe (flag).** No usable commodity or gold series exists on the data source before PCRIX (2002-07) and GC=F (2000-08). So:
  - GLD is first ranked at the 2001-08-31 decision, and GSG at 2003-07-31.
  - From 2000-01 to 2001-07, DAA ranks 10 risky assets. From 2001-08 to 2003-06, it ranks 11.
  - The first 3.5 years are therefore **not the published 12-asset universe**.
- Proxy data makes up 11.9% of the gross exposure-days held (`proxy_share`). Nothing is held on proxy data after 2007-04.

## Deviations from the source

- **Data.** The authors used their own synthetic "ETF" index series from Dec 1970. This backtest uses real ETFs, spliced to mutual-fund and futures proxies from 2000, with fund fees included.
  - Mutual-fund proxies are NAV-only, so a "next open" fill before the ETF existed is effectively the next day's NAV.
  - GC=F is a front-month futures price, not a spot gold total-return series.
- **Execution.** The paper trades at the month-end close with no costs. Here, fills happen at the next session's open with 5 bps slippage plus SEC/FINRA fees, whole shares only.
- **Missing month-end bars.** GC=F has no bar on some half-day month-ends (2002-11-29, 2003-11-28).
  - The strategy carries a close forward over at most 5 sessions. Otherwise, one missing month-end would knock GLD out of the ranking for the next 12 months.
  - A separate harness effect: the GLD proxy has no open on 2004-01-02, so one small GLD rebalance order was dropped. The effect is negligible, about 0.1% of equity left idle for a month.
- **First decision.** The run starts on 2000-01-03, which is not a month-end. The harness's initial rebalance uses that day's close as `p0` and 1999-12-31 as `p1`. Every later decision falls on a month-end.
- **Defensive defaults** (never triggered in the real backtest):
  - A missing canary counts as bad.
  - Unfilled risky slots go to the cash asset.
- **Timing-luck variants** (`shift_5`, `shift_10`). The decision moves earlier in the month, but `p1` through `p12` stay at month-ends. So on those runs `r1` covers less than a month.
  - A diagnostic run with every lookback anchored at 21-session multiples of the decision day gave the same picture (see Results).

## Known critiques and post-publication evidence

- **Heavy in-sample parameter choice.**
  - The canary pair VWO/BND was picked from alternatives using a simple S&P-only model on Dec 1926 – Dec 1970.
  - T = 6 was then chosen by a one-dimensional sweep over T = 1..6 on 1971–1993, maximizing the Keller ratio.
  - Several other choices were also made in-sample: the momentum metric (SMA12 → 13612W), B, the cash universe and the easy-trading rounding.
- **The authors concede the risk.** Their 2023 HAA paper says that with such complex rules "there is the risk of 'overfitting' where the in-sample results might be better than the future (out-of-sample) results".
  - It also says very high cash fractions were "considered risky in times of rising yields and inflation", and it replaces the canary with TIP.
  - 2022 is the case in point: DAA's cash assets (SHY, IEF, LQD) themselves lost money.
- **Rebalance-timing sensitivity.** The 40% weight on the last month makes results depend on the trading day chosen. AllocateSmartly found "substantial variation depending on exact trading dates" for the sister strategy VAA. This backtest confirms the effect strongly for DAA (see below).
- **CXO Advisory.**
  - DAA beat VAA on CAGR in 3 of 4 universes over 2008–2018, but had a worse max drawdown in all four.
  - CXO also warns about snooping bias, index simulations that ignore fund costs, trading frictions, and an out-of-sample period too short to be conclusive.
- **Judge DAA mainly on post-2018-08 data.**

## Results

Base run: 2000-01-03 → 2026-09-25 (26.7 years), `next_open` fills, default costs, proxies on. Source files: `results/keller_daa/summary.json` and `variants.json`.

### Headline metrics

| Metric | Full period | In-sample (2000-01 → 2018-08-01) | Out-of-sample (2018-08-02 → 2026-09) |
|---|---|---|---|
| CAGR | 9.57% | 10.62% | 7.22% |
| Volatility | 10.52% | 10.73% | 10.02% |
| Sharpe | 0.74 | 0.85 | 0.48 |
| Sortino | 1.05 | 1.21 | 0.66 |
| Max drawdown | −18.97% | −14.28% | −18.97% |
| Calmar | 0.50 | 0.74 | 0.38 |
| SPY buy & hold CAGR / Sharpe / MaxDD | 8.35% / 0.41 / −55.2% | 5.56% / 0.30 / −55.2% | 14.98% / 0.68 / −33.7% |

Trading statistics:

- Turnover: 5.81× per year, one-sided. That is about 48% of the portfolio per month, driven by canary flips (about 5 state changes a year) and top-6 churn.
- About 80 trades per year. Cost drag is 0.61% per year.
- Bootstrap Sharpe 90% CI: [0.48, 1.03]. Deflated Sharpe (local, 12 trials): 0.999.

Canary and cash fraction over the 321 decisions:

- Canary state: 0 bad 53%, 1 bad 36%, 2 bad 12%.
- **Average cash fraction: 29.6%** overall, 26.8% before 2018-08, and 36.1% after.
- The source reports 21.8% (1971–93) and 28.8% (1994–2018), so the canary triggers somewhat more often on real ETFs.

### Crisis returns

| Window | DAA |
|---|---|
| Dot-com bust (2000-03 → 2002-10) | +4.7% |
| GFC (2007-10 → 2009-03) | −0.5% |
| Euro/US downgrade (2011-04 → 2011-10) | +4.9% |
| Q4 2018 selloff | −6.7% |
| COVID crash (2020-02 → 2020-03) | −0.8% |
| 2022 inflation bear | −9.8% |
| 2025 tariff shock (2025-02 → 2025-04) | −10.5% |

The max drawdown ran from 2021-09 to 2023-02. This is the rising-yield regime the authors later flagged: the "safe" bond assets fell too, and a July 2022 re-risking whipsawed.

### Robustness suite (`variants.json`)

| Variant | Description | CAGR | Vol | Sharpe | Sortino | MaxDD | Calmar | Turnover | Cost drag |
|---|---|---|---|---|---|---|---|---|---|
| base | published params | 9.57% | 10.52% | 0.74 | 1.05 | −18.97% | 0.50 | 5.81× | 0.61% |
| `costs_0x` | all trading costs ×0 | 10.23% | 10.53% | 0.79 | 1.13 | −18.16% | 0.56 | 5.81× | 0.00% |
| `costs_2x` | all trading costs ×2 | 8.93% | 10.52% | 0.68 | 0.96 | −19.77% | 0.45 | 5.81× | 1.22% |
| `costs_4x` | all trading costs ×4 | 7.64% | 10.52% | 0.57 | 0.80 | −21.34% | 0.36 | 5.81× | 2.43% |
| `exec_next_close` | fill at next close | 8.89% | 10.51% | 0.68 | 0.96 | −19.98% | 0.44 | 5.81× | 0.61% |
| `delay_2` | one extra session of delay | 8.90% | 10.51% | 0.68 | 0.96 | −18.28% | 0.49 | 5.80× | 0.61% |
| `shift_5` | decide 5 sessions before month-end | 7.62% | 11.18% | 0.54 | 0.75 | −28.46% | 0.27 | 5.97× | 0.62% |
| `shift_10` | decide 10 sessions before month-end | 6.93% | 11.22% | 0.48 | 0.65 | −33.14% | 0.21 | 5.88× | 0.61% |
| `param_top_n=4` | T = 4 | 10.11% | 11.71% | 0.72 | 1.01 | −23.93% | 0.42 | 6.56× | 0.69% |
| `param_top_n=5` | T = 5 | 9.85% | 11.17% | 0.73 | 1.02 | −20.88% | 0.47 | 6.04× | 0.63% |
| `param_breadth=1` | B = 1 | 9.05% | 9.95% | 0.73 | 1.03 | −20.82% | 0.43 | 6.83× | 0.71% |
| `etf_era` | start 2008-05-27, no proxy data held | 8.45% | 10.63% | 0.69 | 0.97 | −18.96% | 0.45 | 6.06× | 0.62% |

What the suite shows:

- **Parameters.** The neighbours T = 4/5 and B = 1 are stable on Sharpe (0.72–0.73), but their drawdowns are deeper.
- **Costs and execution.** Results are moderately cost-sensitive because of the high turnover.
- **Timing luck is the big problem.** Deciding 5 or 10 sessions earlier cuts Sharpe from 0.74 to 0.54 or 0.48 and deepens the max drawdown to −28% or −33%.
  - Almost all of that is COVID. The month-end schedule de-risked at the 2020-02-28 close, after the crash week had already flipped the VWO canary, and lost 0.8%.
  - Deciding a week or two earlier kept the portfolio fully risk-on through the crash, losing 28% or 30%.

### Timing-luck ensemble (diagnostic; not committed as a variant)

The base run was repeated with the decision day shifted 0–20 sessions before month-end (`schedule_shift` = 0..20), everything else unchanged:

| 21 decision offsets | Mean | Min | Max | Month-end (offset 0) |
|---|---|---|---|---|
| CAGR, full | 8.2% | 6.7% | 9.8% | 9.6% |
| Sharpe, full | 0.60 | 0.47 | 0.77 | 0.74 (3rd of 21) |
| MaxDD, full | −25.5% | −33.8% | −15.8% | −19.0% |
| Sharpe, OOS | 0.41 | 0.12 | 0.70 | 0.48 |

- The published month-end timing is one of the luckiest offsets in this sample.
- A realistic expectation for a single-tranche implementation is a Sharpe of about 0.6 over the full period and about 0.4 after publication, with drawdowns of 25–30%.
- A variant with every lookback anchored at 21-session multiples of the decision day gives nearly the same ensemble (mean Sharpe 0.60, mean MaxDD −22.6%). So the dispersion is genuine timing luck, not an artifact of mixing a mid-month `p0` with month-end `p1..p12`.

### Comparison with the source

| Period | Source (synthetic indices, no costs, monthly data) | This backtest (costs ×0) | This backtest (default costs) |
|---|---|---|---|
| Mar 2008 – Mar 2018 | R 11.1%, MaxDD 8.2% | R 10.4%, MaxDD −12.6% | R 9.8%, MaxDD −12.8% |
| "OS" Dec 1993 – Mar 2018 | R 14.1%, MaxDD 8.2% | 2000-01 → 2018-03: R 11.5%, MaxDD −14.0% | R 10.8%, MaxDD −14.3% |
| IS Dec 1970 – Dec 1993 | R 20.4%, MaxDD 10.5% | not covered | not covered |

- **2008–2018.** Returns are close to the published 11.1%. The gap of about 0.7 points is consistent with fund expense ratios and next-open fills.
- **Drawdowns.** They are 4–6 points deeper here, partly because this backtest measures drawdowns on daily data while the blog uses month-end data.
- **"OS" period.** The published 14.1% includes the 1994–1999 bull market, which this backtest cannot cover with the full universe. It also relies on the authors' synthetic ETF histories. The shortfall is expected.
- **After publication.** DAA returned 7.2% a year with a 0.48 Sharpe, against 15.0% and 0.68 for SPY. It still delivered much smaller drawdowns (−19% vs −34%). The in-sample → out-of-sample Sharpe drop from 0.85 to 0.48 matches the overfitting concern.

### Assessment

- DAA does what it promises in equity crashes when the timing is lucky. Its defensive value is real but fragile:
  - it depends heavily on which day of the month it trades;
  - it failed in 2022, when bonds were not a safe haven.
- After publication it has clearly lagged SPY on return and on Sharpe.
- It is not a strong stand-alone live candidate. Two ways it could still be worth using:
  - as a low-beta (β ≈ 0.24) diversifying sleeve;
  - split into several tranches that trade on different days, to average away timing luck.
- It is superseded by the authors' own HAA redesign, which uses a TIP canary.
