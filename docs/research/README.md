# Strategy research

Four research dossiers informed which strategies were implemented and how they were tested. Each dossier cites primary sources with links, marks every claim as verified against the original, secondary, or unverified, and records the first public date of each idea. Results after that date count as out-of-sample.

| Dossier | Covers |
|---|---|
| [trend-and-momentum.md](trend-and-momentum.md) | Time-series momentum (Moskowitz–Ooi–Pedersen 2012; Hurst–Ooi–Pedersen 2017), Faber GTAA, Antonacci dual momentum, industry/sector momentum, Keller–Keuning PAA/VAA/DAA, Adaptive Asset Allocation, value and momentum everywhere; ETF inception dates and pre-inception proxies |
| [risk-based-allocation.md](risk-based-allocation.md) | Volatility-managed portfolios (Moreira–Muir 2017) and volatility targeting, risk parity (inverse-vol, ERC), minimum variance / low volatility, static baselines, risk parity plus trend (Clare et al. 2016) |
| [mean-reversion-and-calendar.md](mean-reversion-and-calendar.md) | Connors RSI(2) and siblings, turn of the month, Halloween, pre-FOMC drift, pre-holiday, overnight returns, IBS; realistic ETF auction costs |
| [backtest-methodology-and-alpaca.md](backtest-methodology-and-alpaca.md) | Probabilistic and Deflated Sharpe, PBO, multiple-testing hurdles, post-publication decay, bootstrap methods, rebalance timing luck; Alpaca order types, fees, account rules, data feeds, paper-trading limits |

## Selection

These strategies were implemented (one worktree and branch each, `u/ewilkes/strat-*`). Each has a write-up in `docs/strategies/`.

| Strategy | Source | Why it made the cut |
|---|---|---|
| `faber_gtaa` | Faber (2007) *J. Wealth Mgmt* | Simplest well-documented trend model, with 10+ years of published out-of-sample results |
| `antonacci_gem` | Antonacci (2014) book; SSRN 2012/2013 | The most widely followed dual-momentum model; three ETFs |
| `tsmom_longflat` | Moskowitz, Ooi & Pedersen (2012) *JFE* | The canonical academic trend paper, adapted to long/flat and unlevered |
| `sector_momentum` | Moskowitz & Grinblatt (1999) *JF* | Industry momentum; the whole sector-ETF era is out-of-sample |
| `country_momentum` | Asness, Moskowitz & Pedersen (2013) *JF* | Cross-sectional momentum on 15–17 country ETFs, with history from 1996 |
| `keller_daa` | Keller & Keuning (2018) SSRN | A popular breadth/canary model, included to test a heavily tuned model out-of-sample |
| `adaptive_asset_allocation` | Butler et al. (2012) SSRN | Momentum selection plus minimum-variance weighting |
| `vol_managed_spy` | Moreira & Muir (2017) *JF* | Volatility timing; the only ETF-faithful factor in the paper |
| `risk_parity_trend` | Clare, Seaton, Smith & Thomas (2016) *JBEF* | Inverse-vol risk parity combined with a trend filter |
| `risk_parity_erc` | Maillard, Roncalli & Teiletche (2010) *JPM* | Equal risk contribution, the reference risk-parity construction |
| `connors_rsi2` | Connors & Alvarez (2008); Baltussen et al. (2019) *JFE* | Short-term mean reversion; the strongest surviving high-turnover idea |
| `turn_of_month` | McConnell & Xu (2008) *FAJ* | A calendar anomaly the literature says has disappeared; a negative control for the harness |

Benchmarks: `buy_and_hold` (SPY) and `sixty_forty` (SPY/AGG, monthly).

## Considered and not implemented

| Idea | Reason |
|---|---|
| Betting Against Beta (Frazzini & Pedersen 2014) | Needs shorting and leverage by design. A long-only ETF version keeps only half of the trade. |
| Stock-level minimum variance / idiosyncratic-vol anomalies | Stock-level. A backtest on today's constituents would be survivorship-biased. |
| Overnight vs intraday returns (Lou, Polk & Skouras 2019) | Needs a market-on-close entry and market-on-open exit every day. The edge on SPY/QQQ is gone after costs, and the NY Fed reports the overnight drift near zero since 2021. |
| Pre-FOMC drift (Lucca & Moench 2015) | The part that survives is only the overnight leg (MOC entry, MOO exit). It needs mixed order types and has 8 events a year. Worth revisiting as an overlay. |
| Halloween / Sell in May (Bouman & Jacobsen 2002) | Not significant for US large caps since publication, with far lower CAGR than buy-and-hold. |
| Pre-holiday effect (Ariel 1990) | Survives only in small caps (Ko & Yang 2024). |
| Keller PAA / VAA | DAA represents the family. VAA-G4 is a single-asset model with extreme timing luck. |
| Levered risk parity / volatility targeting | Financing costs decide the outcome (Anderson, Bianchi & Goldberg 2012). The harness supports `max_gross > 1` for later tests. |
