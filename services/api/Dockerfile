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

EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
