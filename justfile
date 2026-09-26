# Common tasks. Run `just` to list them.

default:
    @just --list

# Run the test suite
test *args:
    pytest {{args}}

# Lint and format-check
lint:
    ruff check src tests
    ruff format --check src tests

# Auto-format
fmt:
    ruff format src tests
    ruff check --fix src tests

# List registered strategies with their sources
list:
    trader list -v

# Backtest one strategy with the full robustness suite -> results/<name>
backtest name *args:
    trader backtest {{name}} --suite {{args}}

# Backtest every strategy that has a config in configs/strategies/
backtest-all *args:
    for cfg in configs/strategies/*.yaml; do trader backtest "$cfg" --suite {{args}} || exit 1; done

# Compare every result folder under results/ -> reports/comparison.{html,md,json}
compare *args:
    trader compare results {{args}}

# Build the strategy container image
docker-build:
    docker build -t trader:latest .

# What would a strategy trade right now? (no orders sent)
live-dry name:
    trader live run {{name}} --once --dry-run --broker local

# Re-run every configured strategy (with proxies) and write the main comparison report
compare-all workers="4":
    for cfg in configs/strategies/*.yaml; do name=$(basename "$cfg" .yaml); trader backtest "$cfg" --suite --offline --workers {{workers}} --out "results/$name" > /dev/null || exit 1; done
    trader compare results --out reports/comparison.html --title "Twelve-Strategy Backtest" --fragment

# Same, on real ETF data only (no pre-inception proxies), from 2008-07 when every ETF
# (incl. BIL, VEU, HYG, BND) has a year of history: a check on the proxy splicing
compare-etf-era workers="4":
    for cfg in configs/strategies/*.yaml; do name=$(basename "$cfg" .yaml); trader backtest "$cfg" --suite --offline --no-proxies --start 2008-07-01 --workers {{workers}} --out "results-etf/$name" > /dev/null || exit 1; done
    trader compare results-etf --out reports/comparison-etf-era.html --title "ETF-Era Backtest"
