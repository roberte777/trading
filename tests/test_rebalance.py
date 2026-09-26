from __future__ import annotations

import pytest

from trader.execution.costs import CostModel
from trader.execution.rebalance import RebalanceRules, WeightError, plan_rebalance, validate_weights


def test_whole_share_sizing_and_sell_first():
    orders = plan_rebalance(
        {"A": 0.5, "B": 0.5}, {"C": 10}, {"A": 30.0, "B": 70.0, "C": 5.0}, 10_000
    )
    assert [o.symbol for o in orders] == ["C", "A", "B"]
    assert orders[0].qty == -10
    assert orders[1].qty == 166  # floor(5000/30)
    assert orders[2].qty == 71  # floor(5000/70)


def test_fractional_sizing():
    orders = plan_rebalance({"A": 1.0}, {}, {"A": 300.0}, 1000, RebalanceRules(fractional=True))
    assert orders[0].qty == pytest.approx(3.333333, abs=1e-6)


def test_band_skips_small_adjustments_but_not_exits():
    rules = RebalanceRules(rebalance_band=0.05)
    orders = plan_rebalance({"A": 0.52}, {"A": 50, "B": 1}, {"A": 100.0, "B": 10.0}, 10_000, rules)
    assert [o.symbol for o in orders] == ["B"]


def test_missing_price_leaves_position():
    orders = plan_rebalance({"A": 1.0}, {"B": 5}, {"A": 10.0, "B": float("nan")}, 1000)
    assert [o.symbol for o in orders] == ["A"]


def test_validate_weights():
    rules = RebalanceRules()
    with pytest.raises(WeightError):
        validate_weights({"A": -0.1}, rules)
    with pytest.raises(WeightError):
        validate_weights({"Z": 0.1}, rules, universe={"A"})
    with pytest.raises(WeightError):
        validate_weights({"A": float("nan")}, rules)
    scaled = validate_weights({"A": 0.8, "B": 0.4}, rules)
    assert sum(scaled.values()) == pytest.approx(1.0)


def test_cost_model_fees_only_on_sells():
    c = CostModel(
        slippage_bps=10, sec_fee_rate=20e-6, taf_per_share=0.0002, taf_max=10, cat_per_share=0.0
    )
    assert c.fill_price(100, 1) == pytest.approx(100.1)
    assert c.fill_price(100, -1) == pytest.approx(99.9)
    assert c.fees(100, 50) == 0
    assert c.fees(-100, 50) == pytest.approx(100 * 50 * 20e-6 + 100 * 0.0002)
    assert c.fees(-1_000_000, 1) == pytest.approx(1_000_000 * 20e-6 + 10)
    assert c.scaled(2).slippage_bps == 20
    assert CostModel().fees(100, 50) == pytest.approx(100 * 0.000003)


def test_default_slippage_is_tiered_by_liquidity():
    c = CostModel()
    assert c.slippage_for("SPY") == 2.0
    assert c.slippage_for("EEM") == 4.0
    assert c.slippage_for("DBC") == 6.0
    assert c.slippage_for("ZZZZ") == 5.0
