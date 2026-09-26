from __future__ import annotations

import json

from trader.analytics.report import (
    build_payload,
    find_result_dirs,
    load_results,
    render_html,
    render_markdown,
)
from trader.backtest.engine import BacktestConfig, Backtester
from trader.backtest.result import BacktestResult
from trader.backtest.runner import evaluate, run_suite
from trader.strategies.benchmarks import BuyAndHold, SixtyForty

from .conftest import make_market_data


def _results(tmp_path):
    data, cal = make_market_data(["SPY", "AGG"], start="2003-01-02", end="2012-12-31")
    cfg = BacktestConfig(start="2004-01-02")
    out = []
    for strat in (BuyAndHold(), SixtyForty()):
        res = Backtester(strat, data, cal, cfg).run()
        res.metrics = evaluate(res, bootstrap=False)
        res.variants = run_suite(strat, data, cal, cfg, workers=1)
        res.save(tmp_path / strat.name)
        out.append(tmp_path / strat.name)
    return out


def test_round_trip_and_compare(tmp_path):
    paths = _results(tmp_path)
    assert find_result_dirs([tmp_path]) == sorted(paths)
    loaded = load_results([tmp_path])
    assert {r.strategy for r in loaded} == {"buy_and_hold", "sixty_forty"}
    original = BacktestResult.load(paths[0])
    assert len(original.returns) == len(loaded[0].returns)

    payload = build_payload(loaded)
    json.dumps(payload, allow_nan=False)  # strictly valid JSON: no NaN/inf
    assert payload["n_trials"] >= 2
    ids = {s["id"] for s in payload["strategies"]}
    assert ids == {"buy_and_hold", "sixty_forty"}
    for s in payload["strategies"]:
        assert s["is_benchmark"]
        assert {"sharpe", "cagr", "max_drawdown"} <= set(s["metrics"])
        assert "costs_2x" in s["variants"]
    n = len(payload["series"]["dates"])
    assert all(len(v) == n for v in payload["series"]["equity"].values())

    html = render_html(payload)
    assert "__PAYLOAD__" not in html and "</script>" in html
    assert html.count("<script") == 2
    md = render_markdown(payload)
    assert "| Strategy |" in md
