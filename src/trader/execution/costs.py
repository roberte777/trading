"""Transaction cost model for simulated fills.

Costs come in two parts:

* **Slippage** (bps of price, adverse): bid-ask half-spread plus auction/market
  impact. Applied to the fill price, so it shows up in returns exactly like it
  would live.
* **Fees** (cash): commissions and regulatory pass-through fees. Alpaca charges no
  commission for US equities on standard accounts, but passes through (per its fee
  schedule dated 2026-09-17): SEC Section 31 at $20.60 per $1M sold (since
  2026-04-04), FINRA TAF at $0.000195/share sold capped at $9.79 per trade, and
  the Consolidated Audit Trail fee of $0.000003/share on buys and sells.

Default slippage is 5 bps per fill. That covers a market order queued before the
open measured against the official open: about 2 bps for SPY/QQQ/TLT-class ETFs,
4 bps for EFA/EEM/sector ETFs and 6 bps for thinner funds such as DBC. The
robustness suite also re-runs every strategy at 0x, 2x and 4x these costs.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass


@dataclass(frozen=True)
class CostModel:
    slippage_bps: float = 5.0
    commission_per_share: float = 0.0
    commission_min: float = 0.0
    commission_bps: float = 0.0
    #: SEC Section 31 fee, dollars per dollar of sale proceeds.
    sec_fee_rate: float = 20.60e-6
    #: FINRA TAF, dollars per share sold, capped per trade.
    taf_per_share: float = 0.000195
    taf_max: float = 9.79
    #: Consolidated Audit Trail fee, dollars per share on buys and sells.
    cat_per_share: float = 0.000003
    #: Annual borrow fee on short market value.
    borrow_rate: float = 0.0

    def fill_price(self, ref_price: float, qty: float) -> float:
        slip = self.slippage_bps / 1e4
        return ref_price * (1.0 + slip) if qty > 0 else ref_price * (1.0 - slip)

    def fees(self, qty: float, price: float) -> float:
        shares = abs(qty)
        notional = shares * price
        commission = shares * self.commission_per_share + notional * self.commission_bps / 1e4
        if commission > 0:
            commission = max(commission, self.commission_min)
        regulatory = shares * self.cat_per_share
        if qty < 0:
            regulatory += notional * self.sec_fee_rate + min(
                shares * self.taf_per_share, self.taf_max
            )
        return commission + regulatory

    def scaled(self, multiplier: float) -> CostModel:
        """Every cost component multiplied by ``multiplier`` (for sensitivity runs)."""
        return dataclasses.replace(
            self,
            slippage_bps=self.slippage_bps * multiplier,
            commission_per_share=self.commission_per_share * multiplier,
            commission_min=self.commission_min * multiplier,
            commission_bps=self.commission_bps * multiplier,
            sec_fee_rate=self.sec_fee_rate * multiplier,
            taf_per_share=self.taf_per_share * multiplier,
            taf_max=self.taf_max * multiplier,
            cat_per_share=self.cat_per_share * multiplier,
            borrow_rate=self.borrow_rate * multiplier,
        )
