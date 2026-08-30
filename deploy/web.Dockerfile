# The operator console. It ships the CLI as well as the page, because its one server
# route starts and cancels runs by calling `urithiru` -- the browser never holds a
# credential, a bucket name or a project id.
#
# Launching is refused unless URITHIRU_LAUNCH_TOKEN is set on the service, so a
# deployment with no token configured serves the same pages read-only. See web/README.md.

FROM oven/bun:1.4 AS page
WORKDIR /web
COPY web/package.json web/bun.lock ./
RUN bun install --frozen-lockfile
COPY web/ ./
# The node adapter emits a server that still imports its dependencies, so the runtime
# needs them present. Reinstalling without dev dependencies after the build keeps astro
# and what it imports (devalue among them) and drops the toolchain.
RUN bun run build \
    && rm -rf node_modules \
    && bun install --frozen-lockfile --production

FROM ghcr.io/astral-sh/uv:0.12.5 AS uv
FROM node:22-bookworm-slim AS node

FROM python:3.12-slim

# Only the Node binary: bun already built the page, so the server needs a runtime, not a
# package manager. Both images are bookworm, so the one file is enough.
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --locked --no-dev --no-editable --python /usr/local/bin/python
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1

WORKDIR /srv
COPY --from=page /web/dist ./dist
COPY --from=page /web/node_modules ./node_modules
COPY --from=page /web/package.json ./package.json

# `urithiru` is already on PATH, so the route calls it directly instead of through uv,
# which would look for a project to sync. Runs published while the server is up land in
# the directory it already serves, so they appear without a rebuild.
ENV URITHIRU_CLI=urithiru \
    URITHIRU_ROOT=/srv \
    URITHIRU_RUNS=/srv/dist/client/runs \
    URITHIRU_WORK=/srv/.work/web \
    HOST=0.0.0.0 \
    PORT=8080

RUN useradd --create-home --uid 10001 console \
    && mkdir -p /srv/.work/web /srv/dist/client/runs \
    && chown -R console /srv
USER console

EXPOSE 8080
CMD ["node", "./dist/server/entry.mjs"]
