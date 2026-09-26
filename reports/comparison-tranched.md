# Tranched Strategy Backtest

Common window **2000-01-03 → 2026-09-25** (26.7 years). Execution: `next_open`; slippage tiered 2/4/6 bps by liquidity (5.0 bps otherwise). Deflated Sharpe uses 151 trials (≈48 effective at average correlation 0.69).

| Strategy | CAGR | Vol | Sharpe (90% CI) | Max DD | Calmar | OOS Sharpe | DSR | Turnover | Score |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|
| Adaptive Asset Allocation (top 5, min-variance) (4 tranches) | 9.4% | 9.3% | 0.80 (0.47–1.14) | -22.8% | 0.41 | 0.66 | 0.99 | 5.4× | 7/7 |
| Time-series momentum (long/flat, inverse-vol) (4 tranches) | 5.5% | 5.1% | 0.69 (0.36–1.03) | -14.2% | 0.39 | 0.48 | 0.97 | 1.5× | 7/7 |
| Defensive Asset Allocation (DAA-G12) (4 tranches) | 8.6% | 9.9% | 0.69 (0.37–1.01) | -23.2% | 0.37 | 0.44 | 0.97 | 5.8× | 7/7 |
| Equal risk contribution (MRT 2010) (4 tranches) | 6.3% | 6.8% | 0.65 (0.31–0.99) | -19.2% | 0.33 | 0.44 | 0.96 | 0.4× | 6/7 |
| Antonacci Global Equities Momentum (dual momentum) (4 tranches) | 10.1% | 14.5% | 0.61 (0.31–0.91) | -32.3% | 0.31 | 0.52 | 0.93 | 1.4× | 6/7 |
| Risk parity + 10-month trend filter (Clare et al. 2016) (4 tranches) | 5.8% | 6.6% | 0.60 (0.29–0.92) | -14.5% | 0.40 | 0.41 | 0.93 | 2.0× | 6/7 |
| Faber GTAA-5 (10-month SMA timing) (4 tranches) | 6.2% | 7.4% | 0.59 (0.27–0.90) | -14.2% | 0.44 | 0.44 | 0.92 | 1.8× | 5/7 |
| 60/40 SPY/AGG *(benchmark)* | 6.8% | 11.5% | 0.46 (0.17–0.75) | -35.6% | 0.19 | – | 0.79 | 0.1× | 2/3 |
| Volatility-managed SPY (Moreira-Muir, unlevered) (4 tranches) | 6.2% | 10.5% | 0.45 (0.14–0.73) | -29.0% | 0.22 | 0.70 | 0.76 | 2.2× | 6/7 |
| Buy & hold SPY *(benchmark)* | 8.4% | 19.0% | 0.42 (0.13–0.69) | -54.6% | 0.15 | – | 0.71 | 0.0× | 2/3 |
| Sector momentum rotation (Moskowitz-Grinblatt) (4 tranches) | 7.7% | 18.1% | 0.39 (0.10–0.68) | -48.3% | 0.16 | 0.39 | 0.67 | 3.7× | 5/7 |
| Country equity momentum (AMP 2013, top tercile) (4 tranches) | 6.6% | 20.4% | 0.32 (0.01–0.65) | -62.2% | 0.11 | 0.51 | 0.52 | 2.4× | 4/7 |

## Scorecards

**Adaptive Asset Allocation (top 5, min-variance) (4 tranches)**
- ✅ Holds up after publication — Sharpe 0.96 before → 0.66 after 2012-05-01
- ✅ Significant after multiple testing — Deflated Sharpe 0.99 over 48 effective trials (need ≥ 0.95)
- ✅ Survives 2× trading costs — Sharpe 0.80 → 0.76 at 2× costs
- ✅ Stable across parameter neighbours — worst neighbour Sharpe 0.66 vs 0.80
- ✅ Insensitive to execution timing — worst timing variant Sharpe 0.77 vs 0.80
- ✅ Better risk-adjusted than SPY — Sharpe 0.80 vs SPY 0.42
- ✅ Shallower max drawdown than SPY — -22.8% vs SPY -54.6%

**Time-series momentum (long/flat, inverse-vol) (4 tranches)**
- ✅ Holds up after publication — Sharpe 0.92 before → 0.48 after 2011-12-11
- ✅ Significant after multiple testing — Deflated Sharpe 0.97 over 48 effective trials (need ≥ 0.95)
- ✅ Survives 2× trading costs — Sharpe 0.69 → 0.67 at 2× costs
- ✅ Stable across parameter neighbours — worst neighbour Sharpe 0.58 vs 0.69
- ✅ Insensitive to execution timing — worst timing variant Sharpe 0.68 vs 0.69
- ✅ Better risk-adjusted than SPY — Sharpe 0.69 vs SPY 0.42
- ✅ Shallower max drawdown than SPY — -14.2% vs SPY -54.6%

**Defensive Asset Allocation (DAA-G12) (4 tranches)**
- ✅ Holds up after publication — Sharpe 0.80 before → 0.44 after 2018-08-01
- ✅ Significant after multiple testing — Deflated Sharpe 0.97 over 48 effective trials (need ≥ 0.95)
- ✅ Survives 2× trading costs — Sharpe 0.69 → 0.65 at 2× costs
- ✅ Stable across parameter neighbours — worst neighbour Sharpe 0.60 vs 0.69
- ✅ Insensitive to execution timing — worst timing variant Sharpe 0.65 vs 0.69
- ✅ Better risk-adjusted than SPY — Sharpe 0.69 vs SPY 0.42
- ✅ Shallower max drawdown than SPY — -23.2% vs SPY -54.6%

**Equal risk contribution (MRT 2010) (4 tranches)**
- ❌ Holds up after publication — Sharpe 1.20 before → 0.44 after 2008-06-01
- ✅ Significant after multiple testing — Deflated Sharpe 0.96 over 48 effective trials (need ≥ 0.95)
- ✅ Survives 2× trading costs — Sharpe 0.65 → 0.64 at 2× costs
- ✅ Stable across parameter neighbours — worst neighbour Sharpe 0.63 vs 0.65
- ✅ Insensitive to execution timing — worst timing variant Sharpe 0.64 vs 0.65
- ✅ Better risk-adjusted than SPY — Sharpe 0.65 vs SPY 0.42
- ✅ Shallower max drawdown than SPY — -19.2% vs SPY -54.6%

**Antonacci Global Equities Momentum (dual momentum) (4 tranches)**
- ✅ Holds up after publication — Sharpe 0.68 before → 0.52 after 2014-11-21
- ❌ Significant after multiple testing — Deflated Sharpe 0.93 over 48 effective trials (need ≥ 0.95)
- ✅ Survives 2× trading costs — Sharpe 0.61 → 0.60 at 2× costs
- ✅ Stable across parameter neighbours — worst neighbour Sharpe 0.55 vs 0.61
- ✅ Insensitive to execution timing — worst timing variant Sharpe 0.60 vs 0.61
- ✅ Better risk-adjusted than SPY — Sharpe 0.61 vs SPY 0.42
- ✅ Shallower max drawdown than SPY — -32.3% vs SPY -54.6%

**Risk parity + 10-month trend filter (Clare et al. 2016) (4 tranches)**
- ✅ Holds up after publication — Sharpe 0.72 before → 0.41 after 2016-01-15
- ❌ Significant after multiple testing — Deflated Sharpe 0.93 over 48 effective trials (need ≥ 0.95)
- ✅ Survives 2× trading costs — Sharpe 0.60 → 0.58 at 2× costs
- ✅ Stable across parameter neighbours — worst neighbour Sharpe 0.55 vs 0.60
- ✅ Insensitive to execution timing — worst timing variant Sharpe 0.58 vs 0.60
- ✅ Better risk-adjusted than SPY — Sharpe 0.60 vs SPY 0.42
- ✅ Shallower max drawdown than SPY — -14.5% vs SPY -54.6%

**Faber GTAA-5 (10-month SMA timing) (4 tranches)**
- ❌ Holds up after publication — Sharpe 1.16 before → 0.44 after 2007-02-11
- ❌ Significant after multiple testing — Deflated Sharpe 0.92 over 48 effective trials (need ≥ 0.95)
- ✅ Survives 2× trading costs — Sharpe 0.59 → 0.57 at 2× costs
- ✅ Stable across parameter neighbours — worst neighbour Sharpe 0.50 vs 0.59
- ✅ Insensitive to execution timing — worst timing variant Sharpe 0.57 vs 0.59
- ✅ Better risk-adjusted than SPY — Sharpe 0.59 vs SPY 0.42
- ✅ Shallower max drawdown than SPY — -14.2% vs SPY -54.6%

**Volatility-managed SPY (Moreira-Muir, unlevered) (4 tranches)**
- ✅ Holds up after publication — Sharpe 0.26 before → 0.70 after 2015-09-12
- ❌ Significant after multiple testing — Deflated Sharpe 0.76 over 48 effective trials (need ≥ 0.95)
- ✅ Survives 2× trading costs — Sharpe 0.45 → 0.44 at 2× costs
- ✅ Stable across parameter neighbours — worst neighbour Sharpe 0.44 vs 0.45
- ✅ Insensitive to execution timing — worst timing variant Sharpe 0.44 vs 0.45
- ✅ Better risk-adjusted than SPY — Sharpe 0.45 vs SPY 0.42
- ✅ Shallower max drawdown than SPY — -29.0% vs SPY -54.6%

**Sector momentum rotation (Moskowitz-Grinblatt) (4 tranches)**
- ✅ Holds up after publication — post-publication Sharpe 0.39
- ❌ Significant after multiple testing — Deflated Sharpe 0.67 over 48 effective trials (need ≥ 0.95)
- ✅ Survives 2× trading costs — Sharpe 0.39 → 0.38 at 2× costs
- ✅ Stable across parameter neighbours — worst neighbour Sharpe 0.32 vs 0.39
- ✅ Insensitive to execution timing — worst timing variant Sharpe 0.38 vs 0.39
- ❌ Better risk-adjusted than SPY — Sharpe 0.39 vs SPY 0.42
- ✅ Shallower max drawdown than SPY — -48.3% vs SPY -54.6%

**Country equity momentum (AMP 2013, top tercile) (4 tranches)**
- ✅ Holds up after publication — Sharpe 0.02 before → 0.51 after 2009-03-20
- ❌ Significant after multiple testing — Deflated Sharpe 0.52 over 48 effective trials (need ≥ 0.95)
- ✅ Survives 2× trading costs — Sharpe 0.32 → 0.31 at 2× costs
- ✅ Stable across parameter neighbours — worst neighbour Sharpe 0.25 vs 0.32
- ✅ Insensitive to execution timing — worst timing variant Sharpe 0.32 vs 0.32
- ❌ Better risk-adjusted than SPY — Sharpe 0.32 vs SPY 0.42
- ❌ Shallower max drawdown than SPY — -62.2% vs SPY -54.6%

