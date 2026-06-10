# Build context is the repo ROOT (ingestion depends on the lib/db workspace
# member), so this Dockerfile is referenced as:
#   build: { context: ., dockerfile: services/ingestion/Dockerfile }
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Workspace metadata first, for a cached dependency layer. The lockfile lives at
# the root and references every workspace member, so each member needs at least
# its manifest present for `uv sync` to resolve a coherent workspace.
COPY pyproject.toml uv.lock ./
COPY lib/db/ lib/db/
COPY services/ingestion/ services/ingestion/
COPY services/api/pyproject.toml services/api/
COPY services/worker/pyproject.toml services/worker/

# Install only the ingestion package (+ lib-db) into /app/.venv, without dev deps.
RUN uv sync --frozen --package ingestion --no-dev

ENV PATH="/app/.venv/bin:$PATH"

# Drop privileges: run as a dedicated unprivileged user to limit blast radius
# if the process is compromised.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

CMD ["python", "-m", "ingestion.main"]
