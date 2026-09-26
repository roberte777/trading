# Faber GTAA-5 (10-month SMA timing)

Registry name `faber_gtaa`. Code: `src/trader/strategies/faber_gtaa.py`. Config: `configs/strategies/faber_gtaa.yaml`. Results: `results/faber_gtaa/`.

## Summary

The portfolio has five asset-class sleeves at 20% each: US large caps, foreign developed equities, US 10-year Treasuries, commodities and REITs. At every month end each sleeve is timed on its own. If the sleeve's month-end total-return price is above its 10-month simple moving average, the sleeve is held. Otherwise its 20% sits in T-bills (BIL) until the next month end. The strategy is long-only and unlevered, and it trades once a month.

## Sources

- Faber, M.T. (2007). "A Quantitative Approach to Tactical Asset Allocation." *Journal of Wealth Management* 9(4), 69–79. DOI [10.3905/jwm.2007.674809](https://doi.org/10.3905/jwm.2007.674809). SSRN 962461: <https://papers.ssrn.com/sol3/papers.cfm?abstract_id=962461>
- Faber, M.T. (2013). February 2013 update of the same paper: <https://mebfaber.com/wp-content/uploads/2016/05/SSRN-id962461.pdf>
- Faber, M. (2018). "A Quantitative Approach to Tactical Asset Allocation Revisited 10 Years Later." *Journal of Portfolio Management* 44(2), 156–167. DOI [10.3905/jpm.2018.44.2.156](https://doi.org/10.3905/jpm.2018.44.2.156)

**Publication date used for the out-of-sample split: 2007-02-11**, the SSRN posting. The working-paper draft circulated in May 2006 with data to the end of 2005, and Faber himself treats **2006 onwards** as out-of-sample. The harness split (2007-02-11) therefore counts 2006 and January 2007 as in-sample, although Faber treats them as out-of-sample. Both splits are reported below.

## Rules as implemented

- **Schedule.** Decide at the close of the last NYSE session of each month (`MonthEnd()`).
- **Monthly series.** For each sleeve, take the total-return-adjusted close on the last session of each calendar month. At the decision close, the current session is the current month's observation.
- **SMA.** SMA10 is the mean of the last 10 month-end closes, **including** the current one.
- **Signal.** A sleeve is held at 20% if `close_month_end > SMA10`. The comparison is strict, so a price exactly equal to its SMA is out.
- **Cash.** Every sleeve that is out, or not yet eligible, puts its 20% into BIL. Total weight is always 100%: `BIL = 1 − 0.2 × (sleeves held)`.
- **Eligibility.** A sleeve needs 10 non-missing month-end closes and a price on the decision day. Until then it holds its 20% in BIL (see "Partial universe" below).
- **Rebalancing.** At every month end the portfolio trades back to exact targets (20% per held sleeve, the rest in BIL) in whole shares. Each sleeve is timed independently. There is no ranking and no leverage.
- **Parameters** (the published defaults): `sma_months = 10`, `commodity = "GSG"`. Robustness grid: `sma_months ∈ {6, 8, 12}`, `commodity = "DBC"`.
- `warmup() = sma_months × 23 + 5` sessions.

## ETF mapping and proxies

| Sleeve | Faber's index | ETF (real data from) | Pre-inception proxy (data from) |
|---|---|---|---|
| US large cap | S&P 500 TR | SPY (1993-01-29) | VFINX (1980) |
| Foreign developed | MSCI EAFE | EFA (2001-08-27) | VTMGX (1999-08-17) |
| US 10-year Treasuries | GFD US 10-year govt | IEF (2002-07-30) | VFITX (1991-10-28) |
| Commodities | GSCI TR | GSG (2006-07-21); DBC (2006-02-06) as a variant | PCRIX (2002-07-01). **None earlier.** |
| REITs | NAREIT | VNQ (2004-09-29) | VGSIX (1996-05-13) |
| T-bills | 90-day T-bills | BIL (2007-05-30) | `@tbill`: synthetic index from ^IRX, net of a 0.10% fee |

Proxies come from `proxies_for(...)`. They are spliced on returns, so each ETF's own history is extended backwards.

**Partial universe (2000-01 → 2003-04), partially proxied.** The backtest starts 2000-01-03. Two sleeves were not yet eligible in the early years:

- EFA (via VTMGX) first had 10 month-ends on 2000-05-31. Before that its 20% sat in BIL.
- The commodity sleeve (via PCRIX) first had 10 month-ends on 2003-04-30. From 2000-01 to 2003-04 its 20% sat in BIL.

Over those 40 months the results reflect a 4-sleeve timing model with a fixed 20% in T-bills, not GTAA-5. From January to May 2000 it was a 3-sleeve model with 40% fixed in T-bills. In 2002 this cost the most: the GSCI rose roughly 30% that year, and the backtest had no way to hold it.

About 15.8% of gross exposure-days are held in proxy data (`proxy_share`). The `etf_era` variant starts on 2008-05-16 and holds no proxy data at all.

## Deviations from the source

- **Execution.** Faber fills at the signal close. The harness decides at the close and fills at the **next session's open**, with 5 bps adverse slippage plus SEC/FINRA fees. Mutual-fund proxies are NAV-only, so a "next open" fill before the ETF era is the next day's NAV. The `exec_next_close` and `delay_2` variants cover this.
- **Investable ETFs, not indices.** Performance is net of ETF expense ratios: GSG charges about 0.75%, the others about 0.09% to 0.35%. The instruments also differ from Faber's indices:
  - IEF holds 7–10-year Treasuries, which is shorter duration than a 10-year constant-maturity series.
  - VNQ tracks an MSCI REIT or real-estate index, not NAREIT.
  - GSG tracks the GSCI, but with its own roll and collateral handling.
  - PCRIX, the pre-2006 commodity proxy, is actively managed on the Bloomberg Commodity Index with TIPS collateral. Its correlation with DBC is only about 0.91.
- **Cash.** Cash is BIL (1–3-month bills). Before 2007 it is a synthetic T-bill index with a 0.10% fee. Faber uses 90-day bills. Un-invested cash earns 0%, but in practice this only applies to whole-share rounding residue.
- **Initial rebalance.** The first decision is on 2000-01-03, which is not a month end, because the harness trades to targets on its first session. The 2000-01-03 close serves as January's observation. Every later decision falls on a true month end.
- **Whole shares and monthly rebalancing.** Every month end the portfolio trades back to exact 20% sleeves in whole shares. This produces about 54 small trades a year.
- **Time-varying universe** in 2000–2003, described above.
- **Signal-only DBC.** DBC is loaded as a never-traded signal symbol by default, and GSG is loaded the same way when `commodity="DBC"`. This works around a harness limitation (see below) so that the `commodity=DBC` robustness variant can run. It does not affect any decision.

## Known critiques and post-publication evidence

- **Returns roughly halved after publication, but drawdown control held.**
  - Faber's JPM 2018 update: 1972–2005 QTAA returned 11.73%. For 2006–2016 it returned 4.88% with vol 6.55%, Sharpe 0.59 and max drawdown −9.45%. Buy & hold over the same period returned 3.51% with a max drawdown of −46%.
  - This backtest shows the same pattern: 10.2% CAGR for 2000–2005 against 5.1% for 2006–2026.
- **Lags V-shaped recoveries.** It re-enters only after the price has climbed back above a 10-month average.
  - 2009: +12.2% against SPY's +26.4%.
  - 2020: +3.8% against SPY's +18.3%.
- **Joint stock/bond selloffs (2022).** Diversification into bonds does not help when stocks and bonds fall together, so only the SMA exits and commodities protect.
  - Here 2022 lost 4.1% against SPY's −18.2%. IEF and EFA exited at the end of January 2022, and SPY and VNQ at the end of February. SPY and VNQ whipsawed back in for April 2022. From May to August only the commodity sleeve was invested, and it added about +5% over the year.
  - The protection depends on declines being gradual enough for a monthly signal to catch them.
- **Rebalance timing luck.** Hoffstein, Faber & Braun, "Rebalance Timing Luck: The (Dumb) Luck of Smart Beta," SSRN 3673910 (<https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3673910>). A month-end-only check is exposed to where in the month the signal is sampled.
  - In this backtest, deciding 5 or 10 sessions earlier barely changes CAGR (6.26% and 5.84% against 6.21%).
  - It does deepen the maximum drawdown from −15.4% to about −20.5%, around COVID in 2020.
- **Data-mining bias.** Zakamulin, V. (2014), "The real-life performance of market timing with moving average and time-series momentum rules," *Journal of Asset Management* 15, argues that published moving-average timing results are inflated by data-mining bias and by ignoring frictions. Faber shows that 3–12-month SMAs all work similarly, which partly answers this. The parameter grid below shows the same flat profile.

## Results

Run with `trader backtest configs/strategies/faber_gtaa.yaml --suite --offline --workers 2 --out results/faber_gtaa`, from 2000-01-03 to 2026-09-25 (26.7 years). Execution is next open, with 5 bps slippage and SEC/FINRA fees. The benchmark is SPY buy & hold.

### Headline metrics (`summary.json`)

| Metric | GTAA-5 | SPY |
|---|---|---|
| CAGR | 6.21% | 8.31% |
| Volatility (daily, annualized) | 7.64% | |
| Sharpe | 0.58 | |
| Sortino | 0.80 | |
| Max drawdown (daily) | −15.38% (2011-04-29 → 2011-08-08) | |
| Max drawdown (month-end sampled) | −11.49% (trough 2012-05) | |
| Calmar | 0.40 | |
| Turnover (one-way, per year) | 1.66× | |
| Trades per year | 54 | |
| Cost drag | 0.18%/yr | |
| Beta to SPY | 0.21 | |
| Average invested in risk sleeves | 67% (70% from 2003-05, once all five sleeves exist) | |
| Bootstrap 90% CI: Sharpe | 0.30 – 0.88 | |
| Deflated Sharpe (13 trials) | 0.99 | |

### In-sample vs out-of-sample

| Split | Period | CAGR | Vol | Sharpe | Max DD |
|---|---|---|---|---|---|
| Harness in-sample (`metrics.oos`) | 2000-01-03 → 2007-02-09 | 10.97% | 6.20% | 1.22 | −7.78% |
| Harness out-of-sample (`metrics.oos`) | 2007-02-12 → 2026-09-25 | 4.54% | 8.09% | 0.40 | −15.38% |
| Faber's own split, before | 2000-01-03 → 2005-12-30 | 10.20% | 5.90% | 1.22 | −7.78% |
| Faber's own split, after | 2006-01-03 → 2026-09-25 | 5.08% | 8.07% | 0.45 | −15.38% |

The in-sample window is short (7 years) and partly runs on the partial 4-sleeve universe.

### Crisis returns

| Episode | Window | GTAA-5 | SPY |
|---|---|---|---|
| Dot-com bust | 2000-03-24 → 2002-10-09 | +12.3% | −47.2% |
| GFC | 2007-10-09 → 2009-03-09 | −1.2% | −54.8% |
| Euro crisis / US downgrade | 2011-04-29 → 2011-10-03 | −7.6% | −18.4% |
| Q4 2018 selloff | 2018-09-20 → 2018-12-24 | −6.3% | −18.7% |
| COVID crash | 2020-02-19 → 2020-03-23 | −5.4% | −33.4% |
| 2022 inflation bear | 2022-01-03 → 2022-10-12 | −3.0% | −24.1% |
| 2025 tariff shock | 2025-02-19 → 2025-04-08 | −6.4% | −18.6% |

### Robustness suite (`variants.json`)

| Variant | Description | CAGR | Vol | Sharpe | Max DD | Calmar | Turnover | Cost drag |
|---|---|---|---|---|---|---|---|---|
| **base** | published defaults | 6.21% | 7.64% | 0.58 | −15.38% | 0.40 | 1.66× | 0.18% |
| `costs_0x` | all trading costs ×0 | 6.39% | 7.64% | 0.60 | −15.33% | 0.42 | 1.66× | 0.00% |
| `costs_2x` | all trading costs ×2 | 6.03% | 7.64% | 0.55 | −15.43% | 0.39 | 1.66× | 0.36% |
| `costs_4x` | all trading costs ×4 | 5.67% | 7.64% | 0.51 | −15.54% | 0.36 | 1.66× | 0.71% |
| `exec_next_close` | fill at next close | 5.99% | 7.65% | 0.55 | −15.14% | 0.40 | 1.66× | 0.18% |
| `delay_2` | fill one extra session later | 6.10% | 7.66% | 0.56 | −14.87% | 0.41 | 1.65× | 0.18% |
| `shift_5` | decide 5 sessions before month end | 6.26% | 7.85% | 0.57 | −20.48% | 0.31 | 1.71× | 0.18% |
| `shift_10` | decide 10 sessions before month end | 5.84% | 7.73% | 0.52 | −20.21% | 0.29 | 1.67× | 0.17% |
| `param_sma_months=6` | 6-month SMA | 5.50% | 7.41% | 0.50 | −12.92% | 0.43 | 2.33× | 0.24% |
| `param_sma_months=8` | 8-month SMA | 5.85% | 7.53% | 0.54 | −19.46% | 0.30 | 1.80× | 0.19% |
| `param_sma_months=12` | 12-month SMA | 6.38% | 7.43% | 0.61 | −13.86% | 0.46 | 1.44× | 0.16% |
| `param_commodity=DBC` | DBC instead of GSG | 6.44% | 7.53% | 0.61 | −14.49% | 0.44 | 1.63× | 0.18% |
| `etf_era` | start 2008-05-16, no proxy data | 4.05% | 8.09% | 0.36 | −15.37% | 0.26 | 1.96× | 0.20% |

The results are flat across SMA lengths, costs, execution timing and the commodity ETF: Sharpe stays between 0.50 and 0.61. The weak spot is drawdown sensitivity to timing luck and to SMA length. The 8-month SMA has a −19.5% drawdown (2008-05 → 2009-07), and the shifted schedules have about −20.5% (COVID 2020).

### Comparison with the published numbers

| Period | Source | CAGR | Vol | Sharpe | Max DD |
|---|---|---|---|---|---|
| 1973–2012 | Faber 2013, GTAA-5 | 10.48% | 6.99% | 0.73 | −9.54% |
| 2006–2012 | Faber 2013, GTAA-5 | 6.01% | 7.27% | | −9.42% |
| 2006–2012 | this backtest (monthly stats) | 4.66% | 7.76% | 0.38 | −11.49% |
| 2006–2016 | Faber JPM 2018, QTAA | 4.88% | 6.55% | 0.59 | −9.45% |
| 2006–2016 | this backtest (monthly stats) | 3.76% | 6.94% | 0.39 | −11.49% |
| 2000–2026 | this backtest (monthly stats) | 6.21% | 6.53% | 0.67 | −11.49% |

Faber's statistics are computed on monthly data. On overlapping periods this backtest trails the published GTAA-5 by about 1.1–1.4%/yr, with similar volatility and a slightly deeper month-end drawdown (−11.5% against about −9.5%). The gap is plausible and explained by:

- ETF expense ratios: about 0.29% on average across the five sleeves, or roughly 0.2%/yr at 70% average invested.
- Trading costs: 0.18%/yr.
- Fill timing: the next-close variant is 0.2%/yr worse than next-open, so fill timing is not clearly a drag.
- IEF being shorter duration than Faber's 10-year series during a falling-rate decade.
- GSG and PCRIX against the GSCI TR index.
- BIL's fee against 90-day bills.

The largest daily-data drawdown, −15.4%, came in August 2011, when all five sleeves were invested going into the US downgrade selloff. A month-end sample hides most of it, which is also why Faber's month-end drawdowns look shallower than a daily ledger. No drawdown in any variant comes close to −25%.

Sanity checks performed:

- All 320 month-end target vectors match an independent recomputation from the raw panel (calendar month ends, rolling 10-month mean, strict `>`).
- No sleeve is ever held on a day without a price, or before it has 10 month-end closes. EFA is first held 2000-07-03, and the commodity sleeve 2003-05-01.
- Each sleeve switches between 1.4 and 2.0 times a year.
- Proxy splice dates show no jumps.
- The large 2026 commodity contribution is confirmed independently by both GSG and DBC, with no daily move over 7%.

## Harness limitation found

The robustness suite loads market data once, for the base strategy's `data_symbols()` (`src/trader/backtest/runner.py`, `backtest()` → `load_market_data(strategy, run)`), and reuses that panel for every `param_grid` variant.

- A parameter that changes `universe()`, such as `commodity: DBC`, then fails in `Backtester.__init__` (`src/trader/backtest/engine.py`, "data is missing symbols ['DBC']").
- `_run_variant` swallows the error, and the suite reports it as `"error: ..."`.

The workaround here is local: `signal_symbols()` returns the non-selected commodity ETF, so both are always loaded.
