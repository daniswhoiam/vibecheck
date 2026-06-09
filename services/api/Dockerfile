# Build context is the repo ROOT (the API depends on the lib/db workspace
# member), so this Dockerfile is referenced as:
#   build: { context: ., dockerfile: services/api/Dockerfile }
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
COPY services/api/ services/api/
COPY services/worker/pyproject.toml services/worker/
COPY services/ingestion/pyproject.toml services/ingestion/

# Install only the api package (+ lib-db) into /app/.venv, without dev deps.
RUN uv sync --frozen --package api --no-dev

ENV PATH="/app/.venv/bin:$PATH"

# Drop privileges: run uvicorn as a dedicated unprivileged user to limit blast
# radius if the process is compromised. Port 8000 is unprivileged, so no caps.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
