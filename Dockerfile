FROM ghcr.io/astral-sh/uv:0.12.5 AS uv
FROM python:3.12-slim

# The agent CLI is installed from its official installer; this repository redistributes no binary.
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
# No BuildKit cache mounts: Cloud Build's default builder does not support them, and
# it would not persist them between builds anyway.
RUN uv sync --locked --no-dev --no-editable --python /usr/local/bin/python
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1

RUN useradd --create-home --uid 10001 worker && mkdir /workspace && chown worker /workspace /opt
USER worker

# The agents' own scientific Python, owned by `worker` so an agent can add to it at run
# time. It is deliberately separate from the orchestrator's environment above. A Cloud Run
# sandbox inherits no environment, so runtime/sandbox.py puts this directory on PATH when
# it launches an agent; without that the agent would get the bare system interpreter.
COPY --chown=worker deploy/analysis-requirements.txt /opt/analysis-requirements.txt
RUN uv venv --seed /opt/analysis --python /usr/local/bin/python \
    && uv pip install --python /opt/analysis/bin/python -r /opt/analysis-requirements.txt

WORKDIR /workspace
ENTRYPOINT ["urithiru"]
