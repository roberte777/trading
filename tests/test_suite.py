from __future__ import annotations


def test_suite_loads_symbols_needed_by_parameter_variants():
    from dataclasses import dataclass

    from trader.backtest.runner import suite_symbols
    from trader.strategy import MonthEnd, Strategy

    class Pick(Strategy):
        name = "test_pick"

        @dataclass(frozen=True)
        class Params:
            asset: str = "GSG"

        param_grid = {"asset": ["DBC"]}

        def universe(self):
            return [self.params.asset, "BIL"]

        def schedule(self):
            return MonthEnd()

        def target_weights(self, ctx):
            return {self.params.asset: 1.0}

    assert suite_symbols(Pick()) == ["DBC"]
