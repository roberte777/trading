"""Curated pre-inception proxies (Yahoo tickers) for common ETFs.

Each proxy's *returns* extend an ETF's history backwards (see ``loader.splice``).
Chosen and checked against each ETF over their overlap (monthly correlation,
tracking error) during strategy research, 2026-09:

* Vanguard/Fidelity/PIMCO mutual funds report NAV only (open = close), so a
  "next open" fill in the proxy era is effectively the next day's NAV.
* No usable total-return commodity series exists on Yahoo before PCRIX
  (2002-07); ^SPGSCI is a spot index without roll yield and must not be used.
* Gold before GLD uses front-month COMEX futures (GC=F, from 2000-08-30).
* ``@tbill`` is a synthetic T-bill index accrued from ^IRX, net of a 0.10% fee.
"""

from __future__ import annotations

DEFAULT_PROXIES: dict[str, str] = {
    # US equity
    "SPY": "VFINX",  # corr 0.998, TE 0.8%
    "VOO": "VFINX",
    "IVV": "VFINX",
    "VTI": "VTSMX",
    "IWM": "NAESX",  # corr 0.988, TE 3.1%
    "QQQ": "RYOCX",  # corr 0.999, ~1.3%/yr fee drag
    "IWD": "VIVAX",
    "IWN": "VISVX",
    # International equity
    "EFA": "VTMGX",  # corr 0.994, TE 1.8%
    "VEA": "VTMGX",
    "VEU": "VGTSX",  # corr 0.998, TE 1.2%
    "ACWX": "VGTSX",
    "VXUS": "VGTSX",
    "VGK": "VEURX",
    "EZU": "VEURX",
    "EEM": "VEIEX",  # corr 0.978-0.992
    "VWO": "VEIEX",
    # Bonds
    "TLT": "VUSTX",  # corr 0.992, TE 2.3%
    "IEF": "VFITX",  # corr 0.982, TE 2.2%
    "SHY": "VFISX",
    "AGG": "VBMFX",  # corr 0.978, TE 0.9%
    "BND": "VBMFX",
    "LQD": "VFICX",
    "HYG": "VWEHX",
    "TIP": "VIPSX",  # corr 0.993
    "BWX": "RPIBX",
    # Real assets
    "VNQ": "VGSIX",  # corr 0.999
    "IYR": "VGSIX",
    "RWX": "FIREX",
    "DBC": "PCRIX",  # corr 0.907, TE 8.1% — the only usable commodity proxy
    "GSG": "PCRIX",
    "GLD": "GC=F",  # corr 0.992
    "IAU": "GC=F",
    # Cash
    "BIL": "@tbill",
    "SHV": "@tbill",
    "SGOV": "@tbill",
}


def proxies_for(symbols) -> dict[str, str]:
    """The default proxies for the given symbols (symbols without one are omitted)."""
    return {s: DEFAULT_PROXIES[s] for s in symbols if s in DEFAULT_PROXIES}
