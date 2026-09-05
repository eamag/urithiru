FROM ghcr.io/astral-sh/uv:0.12.5 AS uv
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl mdbtools \
    && curl -fsSL https://antigravity.google/cli/install.sh | bash \
    && mv /root/.local/bin/agy /usr/local/bin/agy \
    && chmod 0755 /usr/local/bin/agy \
    && apt-get purge -y curl && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --locked --no-dev --no-editable --python /usr/local/bin/python
ENV PATH="/opt/analysis/bin:/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1

RUN useradd --create-home --uid 10001 worker && mkdir /workspace && chown worker /workspace /opt
USER worker

COPY --chown=worker deploy/analysis-requirements.txt /opt/analysis-requirements.txt
RUN uv venv --seed /opt/analysis --python /usr/local/bin/python \
    && uv pip install --python /opt/analysis/bin/python -r /opt/analysis-requirements.txt

WORKDIR /workspace
ENTRYPOINT ["urithiru"]
