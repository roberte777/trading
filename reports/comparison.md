# Twelve-Strategy Backtest

Common window **2000-01-03 → 2026-09-25** (26.7 years). Execution: `next_open`; slippage tiered 2/4/6 bps by liquidity (5.0 bps otherwise). Deflated Sharpe uses 175 trials (≈77 effective at average correlation 0.56).

| Strategy | CAGR | Vol | Sharpe (90% CI) | Max DD | Calmar | OOS Sharpe | DSR | Turnover | Score |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|
| Adaptive Asset Allocation (top 5, min-variance) | 10.7% | 9.5% | 0.91 (0.61–1.23) | -19.2% | 0.56 | 0.83 | 0.99 | 5.4× | 5/7 |
| Defensive Asset Allocation (DAA-G12) | 9.9% | 10.5% | 0.77 (0.49–1.07) | -18.6% | 0.53 | 0.51 | 0.94 | 5.8× | 5/7 |
| Time-series momentum (long/flat, inverse-vol) | 5.7% | 5.1% | 0.74 (0.43–1.04) | -10.4% | 0.55 | 0.53 | 0.93 | 1.4× | 6/7 |
| Equal risk contribution (MRT 2010) | 6.3% | 6.7% | 0.65 (0.32–1.01) | -19.1% | 0.33 | 0.45 | 0.85 | 0.3× | 5/7 |
| Risk parity + 10-month trend filter (Clare et al. 2016) | 6.2% | 6.7% | 0.65 (0.35–0.96) | -11.3% | 0.55 | 0.59 | 0.84 | 1.8× | 6/7 |
| Faber GTAA-5 (10-month SMA timing) | 6.3% | 7.6% | 0.58 (0.29–0.89) | -15.4% | 0.41 | 0.41 | 0.75 | 1.7× | 5/7 |
| Antonacci Global Equities Momentum (dual momentum) | 9.7% | 15.1% | 0.56 (0.26–0.87) | -33.7% | 0.29 | 0.41 | 0.70 | 1.3× | 6/7 |
| Volatility-managed SPY (Moreira-Muir, unlevered) | 6.9% | 10.4% | 0.51 (0.22–0.80) | -23.3% | 0.30 | 0.76 | 0.61 | 2.2× | 6/7 |
| Connors RSI(2) mean reversion (ETF basket) | 4.7% | 5.8% | 0.49 (0.22–0.76) | -14.1% | 0.33 | 0.41 | 0.56 | 16.3× | 4/7 |
| 60/40 SPY/AGG *(benchmark)* | 6.8% | 11.5% | 0.46 (0.17–0.75) | -35.6% | 0.19 | – | 0.52 | 0.1× | 2/3 |
| Buy & hold SPY *(benchmark)* | 8.4% | 19.0% | 0.42 (0.13–0.69) | -54.6% | 0.15 | – | 0.42 | 0.0× | 2/3 |
| Sector momentum rotation (Moskowitz-Grinblatt) | 8.1% | 18.2% | 0.41 (0.12–0.70) | -51.3% | 0.16 | 0.41 | 0.41 | 3.6× | 5/7 |
| Country equity momentum (AMP 2013, top tercile) | 6.2% | 20.5% | 0.30 (-0.01–0.63) | -62.8% | 0.10 | 0.50 | 0.21 | 2.3× | 4/7 |
| Turn of the month (McConnell & Xu 2008) | 3.3% | 8.1% | 0.20 (-0.08–0.48) | -22.0% | 0.15 | 0.11 | 0.09 | 24.0× | 2/7 |

## Scorecards

**Adaptive Asset Allocation (top 5, min-variance)**
- ✅ Holds up after publication — Sharpe 1.00 before → 0.83 after 2012-05-01
- ✅ Significant after multiple testing — Deflated Sharpe 0.99 over 77 effective trials (need ≥ 0.95)
- ✅ Survives 2× trading costs — Sharpe 0.91 → 0.88 at 2× costs
- ❌ Stable across parameter neighbours — worst neighbour Sharpe 0.58 vs 0.91
- ❌ Insensitive to execution timing — worst timing variant Sharpe 0.61 vs 0.91
- ✅ Better risk-adjusted than SPY — Sharpe 0.91 vs SPY 0.42
- ✅ Shallower max drawdown than SPY — -19.2% vs SPY -54.6%

**Defensive Asset Allocation (DAA-G12)**
- ✅ Holds up after publication — Sharpe 0.87 before → 0.51 after 2018-08-01
- ❌ Significant after multiple testing — Deflated Sharpe 0.94 over 77 effective trials (need ≥ 0.95)
- ✅ Survives 2× trading costs — Sharpe 0.77 → 0.74 at 2× costs
- ✅ Stable across parameter neighbours — worst neighbour Sharpe 0.74 vs 0.77
- ❌ Insensitive to execution timing — worst timing variant Sharpe 0.51 vs 0.77
- ✅ Better risk-adjusted than SPY — Sharpe 0.77 vs SPY 0.42
- ✅ Shallower max drawdown than SPY — -18.6% vs SPY -54.6%

**Time-series momentum (long/flat, inverse-vol)**
- ✅ Holds up after publication — Sharpe 0.96 before → 0.53 after 2011-12-11
- ❌ Significant after multiple testing — Deflated Sharpe 0.93 over 77 effective trials (need ≥ 0.95)
- ✅ Survives 2× trading costs — Sharpe 0.74 → 0.72 at 2× costs
- ✅ Stable across parameter neighbours — worst neighbour Sharpe 0.59 vs 0.74
- ✅ Insensitive to execution timing — worst timing variant Sharpe 0.63 vs 0.74
- ✅ Better risk-adjusted than SPY — Sharpe 0.74 vs SPY 0.42
- ✅ Shallower max drawdown than SPY — -10.4% vs SPY -54.6%

**Equal risk contribution (MRT 2010)**
- ❌ Holds up after publication — Sharpe 1.21 before → 0.45 after 2008-06-01
- ❌ Significant after multiple testing — Deflated Sharpe 0.85 over 77 effective trials (need ≥ 0.95)
- ✅ Survives 2× trading costs — Sharpe 0.65 → 0.65 at 2× costs
- ✅ Stable across parameter neighbours — worst neighbour Sharpe 0.64 vs 0.65
- ✅ Insensitive to execution timing — worst timing variant Sharpe 0.63 vs 0.65
- ✅ Better risk-adjusted than SPY — Sharpe 0.65 vs SPY 0.42
- ✅ Shallower max drawdown than SPY — -19.1% vs SPY -54.6%

**Risk parity + 10-month trend filter (Clare et al. 2016)**
- ✅ Holds up after publication — Sharpe 0.69 before → 0.59 after 2016-01-15
- ❌ Significant after multiple testing — Deflated Sharpe 0.84 over 77 effective trials (need ≥ 0.95)
- ✅ Survives 2× trading costs — Sharpe 0.65 → 0.63 at 2× costs
- ✅ Stable across parameter neighbours — worst neighbour Sharpe 0.59 vs 0.65
- ✅ Insensitive to execution timing — worst timing variant Sharpe 0.51 vs 0.65
- ✅ Better risk-adjusted than SPY — Sharpe 0.65 vs SPY 0.42
- ✅ Shallower max drawdown than SPY — -11.3% vs SPY -54.6%

**Faber GTAA-5 (10-month SMA timing)**
- ❌ Holds up after publication — Sharpe 1.23 before → 0.41 after 2007-02-11
- ❌ Significant after multiple testing — Deflated Sharpe 0.75 over 77 effective trials (need ≥ 0.95)
- ✅ Survives 2× trading costs — Sharpe 0.58 → 0.57 at 2× costs
- ✅ Stable across parameter neighbours — worst neighbour Sharpe 0.51 vs 0.58
- ✅ Insensitive to execution timing — worst timing variant Sharpe 0.53 vs 0.58
- ✅ Better risk-adjusted than SPY — Sharpe 0.58 vs SPY 0.42
- ✅ Shallower max drawdown than SPY — -15.4% vs SPY -54.6%

**Antonacci Global Equities Momentum (dual momentum)**
- ✅ Holds up after publication — Sharpe 0.70 before → 0.41 after 2014-11-21
- ❌ Significant after multiple testing — Deflated Sharpe 0.70 over 77 effective trials (need ≥ 0.95)
- ✅ Survives 2× trading costs — Sharpe 0.56 → 0.55 at 2× costs
- ✅ Stable across parameter neighbours — worst neighbour Sharpe 0.51 vs 0.56
- ✅ Insensitive to execution timing — worst timing variant Sharpe 0.56 vs 0.56
- ✅ Better risk-adjusted than SPY — Sharpe 0.56 vs SPY 0.42
- ✅ Shallower max drawdown than SPY — -33.7% vs SPY -54.6%

**Volatility-managed SPY (Moreira-Muir, unlevered)**
- ✅ Holds up after publication — Sharpe 0.34 before → 0.76 after 2015-09-12
- ❌ Significant after multiple testing — Deflated Sharpe 0.61 over 77 effective trials (need ≥ 0.95)
- ✅ Survives 2× trading costs — Sharpe 0.51 → 0.50 at 2× costs
- ✅ Stable across parameter neighbours — worst neighbour Sharpe 0.50 vs 0.51
- ✅ Insensitive to execution timing — worst timing variant Sharpe 0.38 vs 0.51
- ✅ Better risk-adjusted than SPY — Sharpe 0.51 vs SPY 0.42
- ✅ Shallower max drawdown than SPY — -23.3% vs SPY -54.6%

**Connors RSI(2) mean reversion (ETF basket)**
- ✅ Holds up after publication — Sharpe 0.71 before → 0.41 after 2008-11-01
- ❌ Significant after multiple testing — Deflated Sharpe 0.56 over 77 effective trials (need ≥ 0.95)
- ❌ Survives 2× trading costs — Sharpe 0.49 → 0.33 at 2× costs
- ❌ Stable across parameter neighbours — worst neighbour Sharpe 0.25 vs 0.49
- ✅ Insensitive to execution timing — worst timing variant Sharpe 0.42 vs 0.49
- ✅ Better risk-adjusted than SPY — Sharpe 0.49 vs SPY 0.42
- ✅ Shallower max drawdown than SPY — -14.1% vs SPY -54.6%

**Sector momentum rotation (Moskowitz-Grinblatt)**
- ✅ Holds up after publication — post-publication Sharpe 0.41
- ❌ Significant after multiple testing — Deflated Sharpe 0.41 over 77 effective trials (need ≥ 0.95)
- ✅ Survives 2× trading costs — Sharpe 0.41 → 0.40 at 2× costs
- ✅ Stable across parameter neighbours — worst neighbour Sharpe 0.38 vs 0.41
- ✅ Insensitive to execution timing — worst timing variant Sharpe 0.35 vs 0.41
- ❌ Better risk-adjusted than SPY — Sharpe 0.41 vs SPY 0.42
- ✅ Shallower max drawdown than SPY — -51.3% vs SPY -54.6%

**Country equity momentum (AMP 2013, top tercile)**
- ✅ Holds up after publication — Sharpe -0.02 before → 0.50 after 2009-03-20
- ❌ Significant after multiple testing — Deflated Sharpe 0.21 over 77 effective trials (need ≥ 0.95)
- ✅ Survives 2× trading costs — Sharpe 0.30 → 0.29 at 2× costs
- ✅ Stable across parameter neighbours — worst neighbour Sharpe 0.24 vs 0.30
- ✅ Insensitive to execution timing — worst timing variant Sharpe 0.30 vs 0.30
- ❌ Better risk-adjusted than SPY — Sharpe 0.30 vs SPY 0.42
- ❌ Shallower max drawdown than SPY — -62.8% vs SPY -54.6%

**Turn of the month (McConnell & Xu 2008)**
- ❌ Holds up after publication — Sharpe 0.46 before → 0.11 after 2006-07-01
- ❌ Significant after multiple testing — Deflated Sharpe 0.09 over 77 effective trials (need ≥ 0.95)
- ❌ Survives 2× trading costs — Sharpe 0.20 → 0.07 at 2× costs
- ❌ Stable across parameter neighbours — worst neighbour Sharpe 0.12 vs 0.20
- ✅ Insensitive to execution timing — worst timing variant Sharpe 0.18 vs 0.20
- ❌ Better risk-adjusted than SPY — Sharpe 0.20 vs SPY 0.42
- ✅ Shallower max drawdown than SPY — -22.0% vs SPY -54.6%

