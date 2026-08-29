FROM ghcr.io/astral-sh/uv:0.12.5 AS uv
FROM python:3.12-slim

# The agent CLI is installed from its official installer; this repository redistributes no binary.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && curl -fsSL https://antigravity.google/cli/install.sh | bash \
    && mv /root/.local/bin/agy /usr/local/bin/agy \
    && chmod 0755 /usr/local/bin/agy \
    && apt-get purge -y curl && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable --python /usr/local/bin/python \
    && rm -rf /root/.cache/uv
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
RUN useradd --create-home --uid 10001 worker && mkdir /workspace && chown worker /workspace
USER worker
WORKDIR /workspace
ENTRYPOINT ["urithiru"]
