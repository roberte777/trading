"""Passive benchmarks. They run through the same engine and costs as every
strategy, so "beats the benchmark" is an apples-to-apples statement."""

from __future__ import annotations

from dataclasses import dataclass, field

from trader.strategy import Context, Daily, MonthEnd, Reference, Strategy, register


@register
class BuyAndHold(Strategy):
    name = "buy_and_hold"
    title = "Buy & hold SPY"
    description = "100% in one instrument, bought once and never rebalanced."

    @dataclass(frozen=True)
    class Params:
        symbol: str = "SPY"

    def universe(self) -> list[str]:
        return [self.params.symbol]

    def warmup(self) -> int:
        return 1

    def schedule(self):
        # Only the initial rebalance trades; afterwards the targets are unchanged
        # and whole-share rounding keeps the position fixed.
        return Daily()

    def target_weights(self, ctx: Context):
        if ctx.holding(self.params.symbol):
            return None
        return {self.params.symbol: 1.0}


@register
class SixtyForty(Strategy):
    name = "sixty_forty"
    title = "60/40 SPY/AGG"
    description = "Classic 60% US equities / 40% US aggregate bonds, rebalanced monthly."
    references = (
        Reference(
            "DeMiguel, Garlappi & Uppal (2009), Optimal Versus Naive Diversification, Review of Financial Studies 22(5)",
            "https://doi.org/10.1093/rfs/hhm075",
        ),
    )
    proxies = {"AGG": "VBMFX"}

    @dataclass(frozen=True)
    class Params:
        weights: dict[str, float] = field(default_factory=lambda: {"SPY": 0.6, "AGG": 0.4})

    def universe(self) -> list[str]:
        return list(self.params.weights)

    def warmup(self) -> int:
        return 1

    def schedule(self):
        return MonthEnd()

    def target_weights(self, ctx: Context):
        live = {s: w for s, w in self.params.weights.items() if ctx.is_tradable(s)}
        total = sum(live.values())
        return {s: w / total for s, w in live.items()} if total > 0 else {}
