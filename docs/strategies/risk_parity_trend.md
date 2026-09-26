# Risk parity + 10-month trend filter (`risk_parity_trend`)

## Summary

Clare, Seaton, Smith & Thomas (2016) combine two simple ideas across five global asset classes. The first is **risk parity**: weight each asset by the inverse of its volatility (Asness, Frazzini & Pedersen 2012). The second is **trend following**: hold an asset only while its month-end price is above its 10-month simple moving average, otherwise hold T-bills (Faber 2007). Their "RPTF" portfolio earned 6.92% a year at 4.05% volatility (Sharpe 1.06, max drawdown 4.9%) over 1994–2015, with no transaction costs.

This implementation maps the five index classes onto six US-listed ETFs (SPY, EFA, EEM, IEF, DBC, VNQ) with BIL as cash. It rebalances at each month-end, fills at the next open, and is fully invested and unlevered.

## Sources

- Clare, A., Seaton, J., Smith, P.N., Thomas, S. (2016). "The trend is our friend: Risk parity, momentum and trend following in global asset allocation." *Journal of Behavioral and Experimental Finance* 9, 63–80. DOI [10.1016/j.jbef.2016.01.002](https://doi.org/10.1016/j.jbef.2016.01.002). Article page: https://www.sciencedirect.com/science/article/abs/pii/S2214635016000083. SSRN 2126478: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2126478.
- Asness, C., Frazzini, A., Pedersen, L.H. (2012). "Leverage Aversion and Risk Parity." *Financial Analysts Journal* 68(1), 47–59. DOI [10.2469/faj.v68.n1.1](https://doi.org/10.2469/faj.v68.n1.1). The source of the inverse-volatility weighting rule.
- Faber, M. (2007). "A Quantitative Approach to Tactical Asset Allocation." *Journal of Wealth Management* 9(4), 69–79. SSRN 962461: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=962461. The source of the 10-month SMA rule.
- **Out-of-sample split: `publication_date = 2016-01-15`** (JBEF online date; the paper's sample ends in 2015).
  - A concept version was posted on SSRN in 2012 (month not verified), so data from about 2012-09 is arguably out-of-sample for the *idea*.
  - The harness split uses the published-spec date, which is the more conservative choice.

## Rules as implemented

At the close of the last trading session of each month (`MonthEnd()`):

- **Month-end closes.** Take the total-return-adjusted close on the last session of each calendar month; the current session counts as the current month-end.
- **Eligible assets.** A risky asset (SPY, EFA, EEM, IEF, DBC, VNQ) is eligible if it has a price today and at least `max(vol_months, sma_months) + 1` = **13** consecutive month-end closes.
- **Inverse-vol weights.** For each eligible asset, `σ_i` is the sample standard deviation (ddof = 1) of its last `vol_months` = **12** monthly total returns. Weights are `w_i = (1/σ_i) / Σ_j (1/σ_j)`, summed over eligible assets only (BIL is not part of the risk-parity set).
- **Trend filter.** An asset is in trend only if its month-end close is **strictly above** the mean of its last `sma_months` = **10** month-end closes (including the current one). Out-of-trend assets get 0.
- **Cash.** BIL gets `1 − Σ w_i` over the in-trend assets. If BIL has no price, the remainder is left as idle cash.
- **Execution.** Orders fill at the next session's open (`next_open`), in whole shares. The harness applies 5 bps slippage and SEC/FINRA fees.

Parameters: `sma_months = 10` and `vol_months = 12` (published values). Sensitivity grid: `sma_months ∈ {6, 8, 12}` and `vol_months ∈ {6, 36}`.

## ETF mapping and proxies

| Clare asset class | ETF | Real ETF data from | Pre-inception proxy (first bar) | First month-end eligible |
|---|---|---|---|---|
| World equities (MSCI World) | SPY | 1993-01-29 | VFINX (1980-01-02) | before 2000 |
| World equities (MSCI World) | EFA | 2001-08-27 | VTMGX (1999-08-17) | 2000-08-31 |
| EM equities (MSCI EM) | EEM | 2003-04-14 | VEIEX (1994-05-04) | before 2000 |
| Government bonds (Citi WGBI) | IEF | 2002-07-30 | VFITX (1991-10-28) | before 2000 |
| Commodities (DJ-UBS / BCOM) | DBC | 2006-02-06 | PCRIX (2002-07-01) | 2003-07-31 |
| REITs (FTSE EPRA/NAREIT Global) | VNQ | 2004-09-29 | VGSIX (1996-05-13) | before 2000 |
| Cash (US 3-month T-bills) | BIL | 2007-05-30 | `@tbill`: ^IRX accrual net of 0.10% (1970) | always |

Proxies come from `proxies_for(...)`. Their returns are spliced onto the ETF history (see `trader.data.loader.splice`). Over the full backtest, 14.4% of gross exposure-days are held in proxy data.

**Time-varying universe (flagged):** the backtest starts on 2000-01-03, before every asset has 13 month-ends of history.

- **Before 2000-08:** weights are computed over SPY, EEM, IEF and VNQ only.
- **2000-08 to 2003-07:** EFA joins, so there are five assets. EFA was below its SMA until 2002-03, so it held nothing until then.
- **From 2003-07-31:** DBC is eligible and all six assets compete. DBC was first in trend, and first held, from 2003-08-29.

## Deviations from the source

- **Universe.**
  - Clare et al. use five global total-return indices. Following the spec, MSCI World is split into **two separate assets**, SPY and EFA. This gives equities two inverse-vol sleeves instead of one, so the portfolio holds more equity risk than the paper.
  - Global government bonds become **IEF** (US 7–10y Treasuries, vol about 6–7%). The paper's Citi WGBI had 2.99% vol and was probably currency-hedged.
  - Commodities become **DBC** (DBIQ Optimum Yield index, not BCOM).
  - Global REITs become **VNQ** (US only).
- **Long-only, unlevered, fully invested.** This matches the paper's unlevered RP + TF.
- **Next-open fills.** Signals are computed at the month-end close and fill at the next session's open, whereas the paper implicitly trades at the month-end close. The pre-inception proxies are mutual funds (NAV only, so open = close), so fills in the proxy era happen at the next day's NAV.
- **Costs.** The harness charges 5 bps slippage plus fees; the paper deducts none. The `costs_0x` variant is the like-for-like comparison.
- **Volatility frequency.** The paper says "one year's worth of data" without giving a frequency. This implementation uses 12 monthly returns, per the spec.
- **Signal price.** Total-return-adjusted closes are used for both the SMA and the volatility.
- **Sample.** The backtest covers 2000-01 to 2026-09. The paper covers 1994–2015.
- **Initial rebalance and timing-shift variants.** The first decision (2000-01-03) and the `shift_*` variants decide mid-month. The latest close then stands in for the current month-end, so the last "monthly" return is a partial month.

## Known critiques and post-publication evidence

- **Bond-friendly sample.** Clare et al. themselves cite Inker (2010, GMO), who argues that post-1981 data flatters bonds because yields fell for three decades. Inverse-vol weighting puts the largest weight on the lowest-volatility asset, which is bonds. Asness et al. (2012) answer that 1926–2010 includes a near-complete round trip in yields.
- **2022.** The stock/bond correlation turned positive and bonds fell with equities. RPAR, a levered risk-parity ETF, lost **−22.8%** (SPY −18.2%, IEF −15.2%, TLT −31.2%). The trend filter is exactly what should help here, and it did: IEF fell below its SMA in January 2022 and this strategy spent most of 2022 in BIL, losing −3.7% for the calendar year.
- **No transaction costs in the paper.** Here, turnover is about 1.8× a year and costs 0.20%/yr at 5 bps. That is modest, but 4× costs remove about 0.8%/yr of CAGR.
- **Start and end-date sensitivity.** Anderson, Bianchi & Goldberg (2012), "Will My Risk Parity Strategy Outperform?", *FAJ* 68(6), 75–93 (https://www.ssrn.com/abstract=2101898), show that risk-parity rankings depend materially on the backtest window, even over decades, and that costs can reverse them. This shows up here as the gap between the full-period and `etf_era` results.
- **Heuristic comparisons.** Chaves, Hsu, Li & Shakernia (2011, *J. of Investing* 20(1)) find that risk parity does not consistently beat equal weight or 60/40 on a risk-adjusted basis.
- **Rebalance-date luck (found in this backtest).** A monthly trend filter only reacts once a month. When the decision is moved 5 or 10 sessions earlier, the portfolio enters the February–March 2020 crash fully risk-on and does not exit until late March. Max drawdown doubles from −11% to −20/−21%.

## Results

> **Note:** the numbers in this section come from the strategy's own branch run, which used a flat 5 bps slippage on every fill and an earlier harness version. The final numbers, from the tiered 2/4/6 bps cost model with the harness fixes applied, are in [`reports/comparison.md`](../../reports/comparison.md) and `results/<strategy>/summary.json` on the comparison branch. Conclusions are unchanged unless noted there.

Command: `trader backtest configs/strategies/risk_parity_trend.yaml --suite --offline --workers 2 --out results/risk_parity_trend`. Next-open fills, 5 bps slippage, whole shares, 2000-01-03 → 2026-09-25 (26.7 years). All numbers are from `results/risk_parity_trend/summary.json` and `variants.json`.

### Headline metrics

| Metric | Full period | In-sample (2000-01-03 → 2016-01-15) | Out-of-sample (2016-01-19 → 2026-09-25) |
|---|---|---|---|
| CAGR | 6.12% | 6.40% | 5.70% |
| Volatility | 6.65% | 7.06% | 5.99% |
| Sharpe | 0.64 | 0.67 | 0.58 |
| Sortino | 0.89 | 0.95 | 0.79 |
| Max drawdown | −11.37% | −11.37% | −8.40% |
| Calmar | 0.54 | 0.56 | 0.68 |
| SPY CAGR (benchmark) | 8.31% | 3.45% | 16.03% |
| Turnover | 1.84×/yr | | |
| Cost drag | 0.20%/yr | | |
| Trades per year | 62 | | |
| Beta to SPY | 0.18 | 0.17 | 0.19 |

Other points:

- **Worst stretch.** The max drawdown ran from 2011-04-29 to 2011-08-08, during the US downgrade selloff, when the portfolio was fully risk-on.
- **Average targets.** IEF 25%, SPY 12%, EFA 9%, VNQ 9%, EEM 7%, DBC 7% and BIL 30%.
- **Trade count.** Trades run at about 5 per monthly rebalance, because inverse-vol weights drift a little every month and each held position gets resized.

### Crisis returns

| Episode | Strategy |
|---|---|
| Dot-com bust (2000-03 → 2002-10) | +17.6% |
| GFC (2007-10 → 2009-03) | +3.3% |
| Euro / US downgrade (2011-04 → 2011-10) | −5.8% |
| Q4 2018 selloff | −3.4% |
| COVID crash (2020-02 → 2020-03) | −5.5% |
| 2022 inflation bear | −3.2% |
| 2025 tariff shock (2025-02 → 2025-04) | −8.1% |

In 2008 the portfolio held no SPY or EFA from January, and no risky asset other than IEF from the end of October. Before that, EEM (9%) and VNQ (10–13%) briefly re-entered in spring and late summer, and DBC was held until September. The rest was IEF (33–46%) and BIL. It returned +2.3% for the year, against −36.8% for SPY. In 2022 it was in BIL from February and returned −3.7%, against −18.2% for SPY.

### Robustness suite

| Variant | Description | CAGR | Vol | Sharpe | Max DD | Turnover | Cost drag |
|---|---|---|---|---|---|---|---|
| base | published parameters | 6.12% | 6.65% | 0.64 | −11.4% | 1.84× | 0.20% |
| `costs_0x` | all trading costs ×0 | 6.32% | 6.65% | 0.67 | −11.3% | 1.84× | 0.00% |
| `costs_2x` | all trading costs ×2 | 5.92% | 6.65% | 0.61 | −11.4% | 1.83× | 0.39% |
| `costs_4x` | all trading costs ×4 | 5.52% | 6.65% | 0.55 | −11.5% | 1.83× | 0.78% |
| `exec_next_close` | fill at next close | 5.90% | 6.67% | 0.60 | −11.3% | 1.83× | 0.19% |
| `delay_2` | fill one extra session later | 5.93% | 6.69% | 0.61 | −11.2% | 1.83× | 0.19% |
| `shift_5` | decide 5 sessions early | 5.70% | 7.11% | 0.55 | −21.1% | 1.90× | 0.20% |
| `shift_10` | decide 10 sessions early | 5.25% | 6.89% | 0.50 | −20.1% | 1.98× | 0.21% |
| `param_sma_months=6` | SMA 6 months | 5.71% | 6.32% | 0.61 | −10.1% | 2.49× | 0.26% |
| `param_sma_months=8` | SMA 8 months | 5.96% | 6.43% | 0.63 | −10.0% | 1.96× | 0.21% |
| `param_sma_months=12` | SMA 12 months | 6.34% | 6.58% | 0.68 | −10.8% | 1.67× | 0.18% |
| `param_vol_months=6` | vol window 6 months | 5.76% | 6.77% | 0.58 | −11.9% | 2.13× | 0.23% |
| `param_vol_months=36` | vol window 36 months | 6.35% | 6.50% | 0.68 | −9.5% | 1.76× | 0.19% |
| `etf_era` | start 2008-08-01, no proxy data held | 4.12% | 6.64% | 0.43 | −11.4% | 2.05× | 0.21% |

- **Parameters.** Every neighbour lands in a narrow Sharpe band (0.58–0.68). The published 10/12 sits mid-pack and is not the best cell, which is what an untuned default should look like.
- **Execution and costs.** Fill timing costs about 0.2%/yr. Doubling costs costs about 0.4%/yr.
- **Rebalance-date luck.** This is the largest sensitivity. Both shift variants take the 2020 crash almost unhedged: −16.8% (`shift_5`) and −18.3% (`shift_10`) from 2020-02-15 to 2020-04-15, against −5.4% for the base.
- **`etf_era`.** It is weaker (Sharpe 0.43) mainly because it skips 2000–2007, when the trend filter avoided the dot-com bust and the risk-on sleeve caught the 2003–2007 rally. After 2008, T-bill yields were near zero for years and whipsaws cost money (2011, 2015 −4.4%, 2018).

### Comparison with the paper

| | CAGR | Vol | Sharpe | Max DD |
|---|---|---|---|---|
| Clare et al. RP + TF, 1994–2015, indices, no costs (monthly data) | 6.92% | 4.05% | 1.06 | 4.9% |
| This backtest, 2000–2015, `costs_0x` (monthly returns) | 6.71% | 6.12% | — | −8.5% |
| This backtest, in-sample 2000-01-03 → 2016-01-15, base with costs (daily returns, `summary.json`) | 6.40% | 7.06% | 0.67 | −11.4% |

The **return replicates**: 6.7% before costs against the paper's 6.9%. The **risk does not**: volatility is about 50% higher, drawdowns are about twice as deep, and Sharpe is about 0.65 against 1.06. The main reasons, roughly in order of importance:

1. **Bond volatility.** Inverse-vol weighting rewards the lowest-volatility asset. The paper's government bond index had 2.99% vol, so it took most of the risk-parity budget and dragged portfolio vol down. IEF has about 6–7% vol, so the bond sleeve is much smaller here.
2. **More equity sleeves.** Splitting world equities into SPY and EFA, with EEM and equity-like VNQ alongside, makes four of the six risky assets equity-like, against three of five in the paper.
3. **Measurement.** The paper's drawdown and vol come from monthly index data. Daily data shows deeper intra-month troughs (−11.4% daily vs −8.5% monthly here).
4. **Sample.** The paper's 1994–2015 window adds the strong 1994–1999 years and ends before the post-2016 low-return period for diversified portfolios.
5. **Implementation.** Next-open fills, 5 bps slippage and whole-share rounding cost roughly 0.4%/yr combined.

The spec's expectations hold: vol 5–8% (6.65%), max drawdown between −10% and −15% (−11.4%), mostly bonds and BIL in 2008, and a negative 2022 (−3.7%).

### Assessment

This is a defensive, low-beta allocation (beta 0.18). It gained through the 2000–2002 bust (+17.6%) and the GFC (+3.3%), and its worst drawdown was −11%, against SPY's −55% since 2000.

As a return engine it is modest:

- **Out-of-sample:** Sharpe 0.58 and CAGR 5.7%, against 16% for SPY.
- **ETF era (2008-08 onward):** Sharpe 0.43.
- **Timing risk:** monthly rebalancing leaves real crash risk inside the month. The shift variants show the max drawdown doubling in 2020.

The published Sharpe of 1.06 does not carry over to investable US ETFs. The strategy is a reasonable candidate as a capital-preservation sleeve, or as a replacement for a bond-heavy balanced fund. It is not a candidate if the goal is to beat equities.
