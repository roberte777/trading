"""Transaction cost model for simulated fills.

Costs come in two parts:

* **Slippage** (bps of price, adverse): bid-ask half-spread plus auction/market
  impact. Applied to the fill price, so it shows up in returns exactly like it
  would live.
* **Fees** (cash): commissions and regulatory pass-through fees. Alpaca charges no
  commission for US equities via API, but passes through the SEC Section 31 fee
  and FINRA Trading Activity Fee on sales.

Defaults are deliberately a little conservative for liquid ETFs; the robustness
suite also re-runs every strategy at 0x, 2x and 4x these costs.
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
    sec_fee_rate: float = 0.0
    #: FINRA TAF, dollars per share sold, capped per trade.
    taf_per_share: float = 0.000195
    taf_max: float = 9.79
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
        regulatory = 0.0
        if qty < 0:
            regulatory = notional * self.sec_fee_rate + min(
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
            borrow_rate=self.borrow_rate * multiplier,
        )
