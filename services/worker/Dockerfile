# Build context is the repo ROOT (the worker depends on the lib/db workspace
# member), so this Dockerfile is referenced as:
#   build: { context: ., dockerfile: services/worker/Dockerfile }
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/app/hf-cache

WORKDIR /app

# Manifests-only first: deps (torch ~1GB installed) and the model snapshot
# (~500MB) land in layers that survive source-code rebuilds.
COPY pyproject.toml uv.lock ./
COPY lib/db/pyproject.toml lib/db/
COPY services/api/pyproject.toml services/api/
COPY services/worker/pyproject.toml services/worker/
COPY services/ingestion/pyproject.toml services/ingestion/

RUN uv sync --frozen --package worker --no-dev --no-install-workspace

ENV PATH="/app/.venv/bin:$PATH"

# Bake the model into the image so container startup needs no network and no
# per-container download. HF_HUB_OFFLINE at runtime (below) pins us to this
# snapshot; bump by rebuilding the image.
RUN python - <<'EOF'
from transformers import pipeline

pipeline(
    "text-classification",
    model="cardiffnlp/twitter-roberta-base-sentiment-latest",
    top_k=None,
)
EOF

COPY lib/db/ lib/db/
COPY services/worker/ services/worker/
RUN uv sync --frozen --package worker --no-dev

# Serve the baked snapshot only; never phone home for revision checks.
ENV HF_HUB_OFFLINE=1

# Drop privileges: run as a dedicated unprivileged user to limit blast radius
# if the process is compromised.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

CMD ["python", "-m", "worker.main"]
