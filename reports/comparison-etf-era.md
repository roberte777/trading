# ETF-Era Backtest

Common window **2008-07-01 → 2026-09-25** (18.2 years). Execution: `next_open`; slippage tiered 2/4/6 bps by liquidity (5.0 bps otherwise). Deflated Sharpe uses 162 trials (≈70 effective at average correlation 0.57).

| Strategy | CAGR | Vol | Sharpe (90% CI) | Max DD | Calmar | OOS Sharpe | DSR | Turnover | Score |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|
| Adaptive Asset Allocation (top 5, min-variance) | 9.9% | 9.7% | 0.89 (0.55–1.30) | -19.2% | 0.52 | 0.83 | 0.97 | 5.4× | 5/7 |
| Defensive Asset Allocation (DAA-G12) | 9.1% | 10.6% | 0.74 (0.43–1.08) | -18.5% | 0.49 | 0.50 | 0.90 | 6.1× | 5/7 |
| Volatility-managed SPY (Moreira-Muir, unlevered) | 8.9% | 10.5% | 0.74 (0.40–1.09) | -14.4% | 0.62 | 0.75 | 0.89 | 2.4× | 6/7 |
| 60/40 SPY/AGG *(benchmark)* | 8.7% | 11.9% | 0.65 (0.28–1.04) | -30.4% | 0.29 | – | 0.80 | 0.1× | 2/3 |
| Buy & hold SPY *(benchmark)* | 12.4% | 19.7% | 0.62 (0.27–1.00) | -47.1% | 0.26 | – | 0.77 | 0.0× | 2/3 |
| Time-series momentum (long/flat, inverse-vol) | 4.2% | 5.1% | 0.56 (0.23–0.92) | -10.3% | 0.40 | 0.53 | 0.69 | 1.4× | 5/7 |
| Antonacci Global Equities Momentum (dual momentum) | 8.8% | 16.2% | 0.52 (0.22–0.89) | -33.7% | 0.26 | 0.41 | 0.62 | 1.6× | 4/7 |
| Sector momentum rotation (Moskowitz-Grinblatt) | 8.7% | 18.2% | 0.47 (0.14–0.82) | -46.2% | 0.19 | 0.47 | 0.55 | 3.8× | 5/7 |
| Equal risk contribution (MRT 2010) | 4.4% | 7.1% | 0.45 (0.07–0.82) | -19.1% | 0.23 | 0.45 | 0.51 | 0.3× | 5/7 |
| Risk parity + 10-month trend filter (Clare et al. 2016) | 4.1% | 6.6% | 0.43 (0.11–0.77) | -11.3% | 0.36 | 0.59 | 0.48 | 2.0× | 5/7 |
| Connors RSI(2) mean reversion (ETF basket) | 3.8% | 6.3% | 0.41 (0.12–0.73) | -14.1% | 0.27 | 0.41 | 0.44 | 17.1× | 3/7 |
| Faber GTAA-5 (10-month SMA timing) | 4.3% | 8.1% | 0.39 (0.07–0.70) | -15.3% | 0.28 | 0.39 | 0.41 | 1.9× | 5/7 |
| Country equity momentum (AMP 2013, top tercile) | 5.5% | 21.5% | 0.29 (-0.08–0.66) | -54.1% | 0.10 | 0.50 | 0.26 | 2.4× | 4/7 |
| Turn of the month (McConnell & Xu 2008) | 2.4% | 8.2% | 0.16 (-0.20–0.54) | -18.3% | 0.13 | 0.16 | 0.12 | 24.0× | 2/7 |

## Scorecards

**Adaptive Asset Allocation (top 5, min-variance)**
- ✅ Holds up after publication — Sharpe 1.06 before → 0.83 after 2012-05-01
- ✅ Significant after multiple testing — Deflated Sharpe 0.97 over 70 effective trials (need ≥ 0.95)
- ✅ Survives 2× trading costs — Sharpe 0.89 → 0.85 at 2× costs
- ❌ Stable across parameter neighbours — worst neighbour Sharpe 0.48 vs 0.89
- ❌ Insensitive to execution timing — worst timing variant Sharpe 0.45 vs 0.89
- ✅ Better risk-adjusted than SPY — Sharpe 0.89 vs SPY 0.62
- ✅ Shallower max drawdown than SPY — -19.2% vs SPY -47.1%

**Defensive Asset Allocation (DAA-G12)**
- ✅ Holds up after publication — Sharpe 0.91 before → 0.50 after 2018-08-01
- ❌ Significant after multiple testing — Deflated Sharpe 0.90 over 70 effective trials (need ≥ 0.95)
- ✅ Survives 2× trading costs — Sharpe 0.74 → 0.71 at 2× costs
- ✅ Stable across parameter neighbours — worst neighbour Sharpe 0.69 vs 0.74
- ❌ Insensitive to execution timing — worst timing variant Sharpe 0.49 vs 0.74
- ✅ Better risk-adjusted than SPY — Sharpe 0.74 vs SPY 0.62
- ✅ Shallower max drawdown than SPY — -18.5% vs SPY -47.1%

**Volatility-managed SPY (Moreira-Muir, unlevered)**
- ✅ Holds up after publication — Sharpe 0.72 before → 0.75 after 2015-09-12
- ❌ Significant after multiple testing — Deflated Sharpe 0.89 over 70 effective trials (need ≥ 0.95)
- ✅ Survives 2× trading costs — Sharpe 0.74 → 0.73 at 2× costs
- ✅ Stable across parameter neighbours — worst neighbour Sharpe 0.76 vs 0.74
- ✅ Insensitive to execution timing — worst timing variant Sharpe 0.63 vs 0.74
- ✅ Better risk-adjusted than SPY — Sharpe 0.74 vs SPY 0.62
- ✅ Shallower max drawdown than SPY — -14.4% vs SPY -47.1%

**Time-series momentum (long/flat, inverse-vol)**
- ✅ Holds up after publication — Sharpe 0.69 before → 0.53 after 2011-12-11
- ❌ Significant after multiple testing — Deflated Sharpe 0.69 over 70 effective trials (need ≥ 0.95)
- ✅ Survives 2× trading costs — Sharpe 0.56 → 0.55 at 2× costs
- ✅ Stable across parameter neighbours — worst neighbour Sharpe 0.45 vs 0.56
- ✅ Insensitive to execution timing — worst timing variant Sharpe 0.46 vs 0.56
- ❌ Better risk-adjusted than SPY — Sharpe 0.56 vs SPY 0.62
- ✅ Shallower max drawdown than SPY — -10.3% vs SPY -47.1%

**Antonacci Global Equities Momentum (dual momentum)**
- ✅ Holds up after publication — Sharpe 0.72 before → 0.41 after 2014-11-21
- ❌ Significant after multiple testing — Deflated Sharpe 0.62 over 70 effective trials (need ≥ 0.95)
- ✅ Survives 2× trading costs — Sharpe 0.52 → 0.51 at 2× costs
- ❌ Stable across parameter neighbours — worst neighbour Sharpe 0.37 vs 0.52
- ✅ Insensitive to execution timing — worst timing variant Sharpe 0.50 vs 0.52
- ❌ Better risk-adjusted than SPY — Sharpe 0.52 vs SPY 0.62
- ✅ Shallower max drawdown than SPY — -33.7% vs SPY -47.1%

**Sector momentum rotation (Moskowitz-Grinblatt)**
- ✅ Holds up after publication — post-publication Sharpe 0.47
- ❌ Significant after multiple testing — Deflated Sharpe 0.55 over 70 effective trials (need ≥ 0.95)
- ✅ Survives 2× trading costs — Sharpe 0.47 → 0.46 at 2× costs
- ✅ Stable across parameter neighbours — worst neighbour Sharpe 0.45 vs 0.47
- ✅ Insensitive to execution timing — worst timing variant Sharpe 0.46 vs 0.47
- ❌ Better risk-adjusted than SPY — Sharpe 0.47 vs SPY 0.62
- ✅ Shallower max drawdown than SPY — -46.2% vs SPY -47.1%

**Equal risk contribution (MRT 2010)**
- ✅ Holds up after publication — post-publication Sharpe 0.45
- ❌ Significant after multiple testing — Deflated Sharpe 0.51 over 70 effective trials (need ≥ 0.95)
- ✅ Survives 2× trading costs — Sharpe 0.45 → 0.45 at 2× costs
- ✅ Stable across parameter neighbours — worst neighbour Sharpe 0.44 vs 0.45
- ✅ Insensitive to execution timing — worst timing variant Sharpe 0.44 vs 0.45
- ❌ Better risk-adjusted than SPY — Sharpe 0.45 vs SPY 0.62
- ✅ Shallower max drawdown than SPY — -19.1% vs SPY -47.1%

**Risk parity + 10-month trend filter (Clare et al. 2016)**
- ✅ Holds up after publication — Sharpe 0.26 before → 0.59 after 2016-01-15
- ❌ Significant after multiple testing — Deflated Sharpe 0.48 over 70 effective trials (need ≥ 0.95)
- ✅ Survives 2× trading costs — Sharpe 0.43 → 0.42 at 2× costs
- ✅ Stable across parameter neighbours — worst neighbour Sharpe 0.34 vs 0.43
- ✅ Insensitive to execution timing — worst timing variant Sharpe 0.33 vs 0.43
- ❌ Better risk-adjusted than SPY — Sharpe 0.43 vs SPY 0.62
- ✅ Shallower max drawdown than SPY — -11.3% vs SPY -47.1%

**Connors RSI(2) mean reversion (ETF basket)**
- ✅ Holds up after publication — post-publication Sharpe 0.41
- ❌ Significant after multiple testing — Deflated Sharpe 0.44 over 70 effective trials (need ≥ 0.95)
- ❌ Survives 2× trading costs — Sharpe 0.41 → 0.26 at 2× costs
- ❌ Stable across parameter neighbours — worst neighbour Sharpe 0.17 vs 0.41
- ✅ Insensitive to execution timing — worst timing variant Sharpe 0.36 vs 0.41
- ❌ Better risk-adjusted than SPY — Sharpe 0.41 vs SPY 0.62
- ✅ Shallower max drawdown than SPY — -14.1% vs SPY -47.1%

**Faber GTAA-5 (10-month SMA timing)**
- ✅ Holds up after publication — post-publication Sharpe 0.39
- ❌ Significant after multiple testing — Deflated Sharpe 0.41 over 70 effective trials (need ≥ 0.95)
- ✅ Survives 2× trading costs — Sharpe 0.39 → 0.37 at 2× costs
- ✅ Stable across parameter neighbours — worst neighbour Sharpe 0.42 vs 0.39
- ✅ Insensitive to execution timing — worst timing variant Sharpe 0.35 vs 0.39
- ❌ Better risk-adjusted than SPY — Sharpe 0.39 vs SPY 0.62
- ✅ Shallower max drawdown than SPY — -15.3% vs SPY -47.1%

**Country equity momentum (AMP 2013, top tercile)**
- ✅ Holds up after publication — post-publication Sharpe 0.50
- ❌ Significant after multiple testing — Deflated Sharpe 0.26 over 70 effective trials (need ≥ 0.95)
- ✅ Survives 2× trading costs — Sharpe 0.29 → 0.28 at 2× costs
- ✅ Stable across parameter neighbours — worst neighbour Sharpe 0.22 vs 0.29
- ✅ Insensitive to execution timing — worst timing variant Sharpe 0.30 vs 0.29
- ❌ Better risk-adjusted than SPY — Sharpe 0.29 vs SPY 0.62
- ❌ Shallower max drawdown than SPY — -54.1% vs SPY -47.1%

**Turn of the month (McConnell & Xu 2008)**
- ❌ Holds up after publication — post-publication Sharpe 0.16
- ❌ Significant after multiple testing — Deflated Sharpe 0.12 over 70 effective trials (need ≥ 0.95)
- ❌ Survives 2× trading costs — Sharpe 0.16 → 0.04 at 2× costs
- ❌ Stable across parameter neighbours — worst neighbour Sharpe 0.10 vs 0.16
- ✅ Insensitive to execution timing — worst timing variant Sharpe 0.19 vs 0.16
- ❌ Better risk-adjusted than SPY — Sharpe 0.16 vs SPY 0.62
- ✅ Shallower max drawdown than SPY — -18.3% vs SPY -47.1%

