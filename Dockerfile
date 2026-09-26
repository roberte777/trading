# One image, many strategies: the strategy is chosen at run time with
# TRADER_STRATEGY (a name from configs/strategies/) or TRADER_CONFIG (a path).
#
#   docker build -t trader .
#   docker run --rm -e TRADER_STRATEGY=sixty_forty -e TRADER_BROKER=local \
#       -v trader-state:/state trader live run --once --dry-run

FROM python:3.12-slim-bookworm AS build
COPY --from=ghcr.io/astral-sh/uv:0.12.17 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.12-slim-bookworm
RUN useradd --create-home --uid 10001 trader \
    && mkdir -p /state \
    && chown trader /state
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY configs ./configs
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    TZ=America/New_York \
    TRADER_STATE_DIR=/state \
    TRADER_CACHE_DIR=/state/cache \
    TRADER_CONFIG_DIR=/app/configs/strategies
USER trader
VOLUME ["/state"]
HEALTHCHECK --interval=5m --timeout=20s --start-period=2m CMD ["trader", "live", "health"]
ENTRYPOINT ["trader"]
CMD ["live", "run"]
