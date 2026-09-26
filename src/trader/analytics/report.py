"""Strategy comparison reports.

``trader compare results/*`` loads any number of result folders, aligns them on
their common date window (so every number is apples to apples), recomputes all
metrics on that window, and writes:

* ``comparison.html`` – self-contained interactive report (no external assets)
* ``comparison.md``   – leaderboard + scorecard for PRs and terminals
* ``comparison.json`` – the full payload, for further analysis

The Deflated Sharpe Ratio here is *global*: the trial count is every strategy
and every robustness variant that was run, which is the honest number of
configurations looked at before picking winners.
"""

from __future__ import annotations

import html
import json
import math
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from trader.analytics.metrics import (
    crisis_returns,
    drawdown,
    equity_curve,
    monthly_returns,
    performance_metrics,
    rolling_sharpe,
    split_metrics,
    trading_metrics,
    yearly_returns,
)
from trader.analytics.stats import bootstrap_ci, deflated_sharpe
from trader.backtest.result import BacktestResult

BENCHMARKS = ("buy_and_hold", "sixty_forty")
MAX_POINTS = 1400


# -- loading ---------------------------------------------------------------------------
def find_result_dirs(paths: list[str | Path]) -> list[Path]:
    found: list[Path] = []
    for p in map(Path, paths):
        if (p / "summary.json").exists():
            found.append(p)
        elif p.is_dir():
            found.extend(sorted(q.parent for q in p.glob("*/summary.json")))
    unique = list(dict.fromkeys(found))
    if not unique:
        raise FileNotFoundError(f"no result folders (with summary.json) under {paths}")
    return unique


def load_results(paths: list[str | Path]) -> list[BacktestResult]:
    return [BacktestResult.load(p) for p in find_result_dirs(paths)]


def common_window(results: list[BacktestResult]) -> tuple[pd.Timestamp, pd.Timestamp]:
    start = max(r.start for r in results)
    end = min(r.end for r in results)
    if end <= start:
        raise ValueError("results do not overlap in time")
    return start, end


# -- helpers ---------------------------------------------------------------------------
def _clean(obj: Any) -> Any:
    """JSON-safe: NaN/inf -> None, numpy scalars -> python."""
    if isinstance(obj, dict):
        return {str(k): _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, (np.floating, float)):
        f = float(obj)
        return f if math.isfinite(f) else None
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, (pd.Timestamp, datetime)):
        return str(obj.date()) if hasattr(obj, "date") else str(obj)
    return obj


def _sample_positions(n: int, max_points: int = MAX_POINTS) -> np.ndarray:
    step = max(1, math.ceil(n / max_points))
    pos = np.arange(0, n, step)
    if pos[-1] != n - 1:
        pos = np.r_[pos, n - 1]
    return pos


def _variant_sharpes(res: BacktestResult) -> list[float]:
    out = []
    for v in res.variants.values():
        m = v.get("metrics")
        if isinstance(m, dict) and m.get("sharpe_daily") is not None:
            out.append(float(m["sharpe_daily"]))
    return out


def _scorecard(entry: dict[str, Any], spy: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Pass/fail robustness checks. Criteria are stated so a reader can disagree."""
    m, v = entry["metrics"], entry["variants"]
    base = m.get("sharpe")
    # Variants were run over the strategy's full window; compare them with the
    # base run over that same window, not with the common-window Sharpe.
    vbase = entry.get("variants_base", {}).get("sharpe") or base
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool | None, detail: str) -> None:
        checks.append({"check": name, "pass": ok, "detail": detail})

    oos = entry["oos"]
    if oos.get("in_sample") and oos.get("out_of_sample"):
        is_sr, oos_sr = oos["in_sample"]["sharpe"], oos["out_of_sample"]["sharpe"]
        add(
            "Holds up after publication",
            oos_sr >= 0.5 * is_sr and oos_sr > 0,
            f"Sharpe {is_sr:.2f} before → {oos_sr:.2f} after {oos['split']}",
        )
    elif oos.get("out_of_sample"):
        oos_sr = oos["out_of_sample"]["sharpe"]
        add("Holds up after publication", oos_sr > 0.3, f"post-publication Sharpe {oos_sr:.2f}")
    dsr = entry.get("dsr", {}).get("dsr")
    if dsr is not None:
        add(
            "Significant after multiple testing",
            dsr >= 0.95,
            f"Deflated Sharpe {dsr:.2f} over {entry['dsr']['n_trials']} trials (need ≥ 0.95)",
        )
    c2 = v.get("costs_2x", {}).get("sharpe")
    if c2 is not None and vbase:
        add(
            "Survives 2× trading costs",
            c2 >= vbase - 0.1,
            f"Sharpe {vbase:.2f} → {c2:.2f} at 2× costs",
        )
    params = [
        x["sharpe"] for k, x in v.items() if k.startswith("param_") and x.get("sharpe") is not None
    ]
    if params and vbase:
        worst = min(params)
        add(
            "Stable across parameter neighbours",
            worst >= 0.75 * vbase,
            f"worst neighbour Sharpe {worst:.2f} vs {vbase:.2f}",
        )
    shifts = [
        x["sharpe"]
        for k, x in v.items()
        if (k.startswith("shift_") or k.startswith("delay_") or k.startswith("exec_"))
        and x.get("sharpe") is not None
    ]
    if shifts and vbase:
        worst = min(shifts)
        add(
            "Insensitive to execution timing",
            worst >= vbase - 0.15,
            f"worst timing variant Sharpe {worst:.2f} vs {vbase:.2f}",
        )
    if spy is not None and not entry["is_benchmark"]:
        add(
            "Better risk-adjusted than SPY",
            (base or 0) > spy["sharpe"],
            f"Sharpe {base:.2f} vs SPY {spy['sharpe']:.2f}",
        )
        add(
            "Shallower max drawdown than SPY",
            m["max_drawdown"] > spy["max_drawdown"],
            f"{m['max_drawdown']:.1%} vs SPY {spy['max_drawdown']:.1%}",
        )
    return checks


# -- payload -----------------------------------------------------------------------------
def build_payload(
    results: list[BacktestResult],
    benchmarks: tuple[str, ...] = BENCHMARKS,
    title: str = "Strategy comparison",
) -> dict[str, Any]:
    start, end = common_window(results)
    all_trials: list[float] = []
    for res in results:
        r = res.returns.loc[start:end]
        ex = (r - res.rf.reindex(r.index).fillna(0.0)).dropna()
        all_trials.append(float(ex.mean() / ex.std(ddof=1)))
        all_trials.extend(_variant_sharpes(res))

    entries: list[dict[str, Any]] = []
    rets: dict[str, pd.Series] = {}
    for res in results:
        r = res.returns.loc[start:end].copy()
        r.iloc[0] = 0.0  # every curve starts at 1 on the common start date
        rf = res.rf.loc[start:end]
        b = res.benchmark_returns.loc[start:end]
        daily = res.daily.loc[start:end]
        trades = res.trades
        if not trades.empty:
            td = pd.to_datetime(trades["date"])
            trades = trades[(td >= start) & (td <= end)]
        m = performance_metrics(r, rf, b)
        m.update(trading_metrics(daily, trades))
        ex = (r - rf).dropna()
        variants = {
            k: v["metrics"] for k, v in res.variants.items() if isinstance(v.get("metrics"), dict)
        }
        entries.append(
            {
                "id": res.strategy,
                "title": res.title,
                "is_benchmark": res.strategy in benchmarks,
                "description": res.meta.get("description", ""),
                "references": res.meta.get("references", []),
                "publication_date": res.meta.get("publication_date"),
                "schedule": res.meta.get("schedule"),
                "universe": res.meta.get("universe", []),
                "params": res.params,
                "execution": (res.config or {}).get("execution")
                if isinstance(res.config, dict)
                else None,
                "full_window": {"start": str(res.start.date()), "end": str(res.end.date())},
                "proxy_share": res.meta.get("proxy_share", 0.0),
                "data_first_real": res.meta.get("data_first_real", {}),
                "metrics": m,
                "bootstrap": bootstrap_ci(r, rf, b, n_boot=600),
                "dsr": deflated_sharpe(ex, all_trials),
                "oos": split_metrics(r, rf, b, res.meta.get("publication_date")),
                "crises": crisis_returns(r),
                "yearly": {str(k): float(v) for k, v in yearly_returns(r).items()},
                "variants": variants,
                "variants_base": {
                    k: res.metrics.get(k)
                    for k in ("sharpe", "cagr", "max_drawdown", "start", "end")
                },
                "variant_notes": {k: v.get("description", "") for k, v in res.variants.items()},
                "latest_targets": _latest_targets(res),
            }
        )
        rets[res.strategy] = r

    spy_entry = next((e for e in entries if e["id"] == "buy_and_hold"), None)
    spy = spy_entry["metrics"] if spy_entry else None
    for e in entries:
        e["scorecard"] = _scorecard(e, spy)
        e["score"] = sum(1 for c in e["scorecard"] if c["pass"])
        e["score_of"] = len(e["scorecard"])

    frame = pd.DataFrame(rets).fillna(0.0)
    pos = _sample_positions(len(frame))
    dates = [str(d.date()) for d in frame.index[pos]]
    series = {
        "dates": dates,
        "equity": {k: equity_curve(frame[k]).to_numpy()[pos].round(5).tolist() for k in frame},
        "drawdown": {k: drawdown(frame[k]).to_numpy()[pos].round(5).tolist() for k in frame},
        "rolling_sharpe": {
            k: rolling_sharpe(
                frame[k], next(res.rf for res in results if res.strategy == k).loc[start:end]
            )
            .to_numpy()[pos]
            .round(4)
            .tolist()
            for k in frame
        },
    }
    monthly = pd.DataFrame({k: monthly_returns(frame[k]) for k in frame})
    corr = monthly.corr()
    first = results[0]
    cfg = first.config if isinstance(first.config, dict) else {}
    payload = {
        "title": title,
        "generated_at": datetime.now(UTC).isoformat(timespec="minutes"),
        "window": {"start": str(start.date()), "end": str(end.date()), "years": len(frame) / 252},
        "assumptions": {
            "execution": cfg.get("execution"),
            "delay": cfg.get("delay"),
            "costs": cfg.get("costs"),
            "rules": cfg.get("rules"),
            "initial_capital": cfg.get("initial_capital"),
            "cash_interest": cfg.get("cash_interest"),
            "data_provider": first.meta.get("data_provider"),
            "use_proxies": first.meta.get("use_proxies"),
        },
        "n_trials": len(all_trials),
        "strategies": entries,
        "series": series,
        "correlation": {"ids": list(corr.columns), "matrix": corr.round(3).to_numpy().tolist()},
    }
    return _clean(payload)


def _latest_targets(res: BacktestResult) -> dict[str, Any]:
    if res.targets.empty:
        return {}
    last = res.targets.iloc[-1]
    return {
        "date": str(res.targets.index[-1].date()),
        "weights": {k: float(v) for k, v in last.items() if abs(v) > 1e-9},
    }


# -- renderers ---------------------------------------------------------------------------
def render_html(payload: dict[str, Any]) -> str:
    template = resources.files("trader.analytics").joinpath("templates/report.html").read_text()
    data = json.dumps(payload, separators=(",", ":")).replace("</", "<\\/")
    return template.replace("__TITLE__", html.escape(payload["title"])).replace("__PAYLOAD__", data)


def _pct(x: Any, d: int = 1) -> str:
    return "–" if x is None else f"{100 * x:.{d}f}%"


def _num(x: Any, d: int = 2) -> str:
    return "–" if x is None else f"{x:.{d}f}"


def render_markdown(payload: dict[str, Any]) -> str:
    w = payload["window"]
    lines = [
        f"# {payload['title']}",
        "",
        f"Common window **{w['start']} → {w['end']}** ({w['years']:.1f} years). Execution: `{payload['assumptions'].get('execution')}`; "
        f"slippage {(payload['assumptions'].get('costs') or {}).get('slippage_bps')} bps per side. "
        f"Deflated Sharpe uses {payload['n_trials']} trials.",
        "",
        "| Strategy | CAGR | Vol | Sharpe (90% CI) | Max DD | Calmar | OOS Sharpe | DSR | Turnover | Score |",
        "|---|---:|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    ordered = sorted(payload["strategies"], key=lambda e: -(e["metrics"].get("sharpe") or -9))
    for e in ordered:
        m, ci = e["metrics"], e["bootstrap"]["sharpe"]
        oos = (e["oos"].get("out_of_sample") or {}).get("sharpe")
        name = e["title"] + (" *(benchmark)*" if e["is_benchmark"] else "")
        lines.append(
            f"| {name} | {_pct(m.get('cagr'))} | {_pct(m.get('volatility'))} | {_num(m.get('sharpe'))} ({_num(ci['lo'])}–{_num(ci['hi'])}) | "
            f"{_pct(m.get('max_drawdown'))} | {_num(m.get('calmar'))} | {_num(oos)} | {_num(e['dsr'].get('dsr'))} | "
            f"{_num(m.get('turnover_annual'), 1)}× | {e['score']}/{e['score_of']} |"
        )
    lines += ["", "## Scorecards", ""]
    for e in ordered:
        if e["is_benchmark"]:
            continue
        lines.append(f"**{e['title']}**")
        for c in e["scorecard"]:
            mark = "✅" if c["pass"] else "❌"
            lines.append(f"- {mark} {c['check']} — {c['detail']}")
        lines.append("")
    return "\n".join(lines) + "\n"


def write_reports(
    results: list[BacktestResult],
    out: str | Path,
    title: str = "Strategy comparison",
    benchmarks: tuple[str, ...] = BENCHMARKS,
) -> dict[str, Path]:
    out = Path(out)
    stem = out.with_suffix("") if out.suffix == ".html" else out / "comparison"
    stem.parent.mkdir(parents=True, exist_ok=True)
    payload = build_payload(results, benchmarks=benchmarks, title=title)
    paths = {
        "html": stem.with_suffix(".html"),
        "md": stem.with_suffix(".md"),
        "json": stem.with_suffix(".json"),
    }
    paths["html"].write_text(render_html(payload))
    paths["md"].write_text(render_markdown(payload))
    paths["json"].write_text(json.dumps(payload, indent=1))
    return paths


# -- CLI -------------------------------------------------------------------------------
def _cmd_compare(args) -> int:
    results = load_results(args.results)
    benchmarks = tuple(b.strip() for b in args.benchmarks.split(",") if b.strip())
    paths = write_reports(results, args.out, title=args.title, benchmarks=benchmarks)
    print(Path(paths["md"]).read_text())
    for kind, p in paths.items():
        print(f"{kind:5s} → {p}")
    return 0


def register_cli(sub) -> None:
    sp = sub.add_parser("compare", help="compare backtest results side by side")
    sp.add_argument("results", nargs="+", help="result folders, or a parent folder containing them")
    sp.add_argument("--out", default="reports/comparison.html")
    sp.add_argument("--title", default="Strategy comparison")
    sp.add_argument(
        "--benchmarks",
        default=",".join(BENCHMARKS),
        help="comma-separated strategy ids treated as benchmarks",
    )
    sp.set_defaults(func=_cmd_compare)
