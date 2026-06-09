"""Vibecheck API service.

A FastAPI app that serves dashboard data from the shared ``lib_db`` data layer.
The app owns the async connection pool's lifecycle via the lifespan hook; the
``/health`` endpoint is deliberately DB-free so liveness never depends on a
reachable database.
"""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from lib_db import create_pool

from api.routes import router

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgres://vibecheck:vibecheck@127.0.0.1:5432/vibecheck?sslmode=disable",
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Open the connection pool on startup and close it on shutdown."""
    pool = create_pool(DATABASE_URL)
    await pool.open()
    app.state.pool = pool
    try:
        yield
    finally:
        await pool.close()


app = FastAPI(title="Vibecheck API", lifespan=lifespan)
app.include_router(router)


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe — does not touch the database."""
    return {"status": "ok"}


_HTTP_METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace"}

# Advisory caps documented in the OpenAPI contract so array responses are
# bounded in the spec (CKV_OPENAPI_21). They are NOT enforced at runtime — real
# pagination/limits are a deferred phase (see the Phase 2 design doc, "Out of
# scope"). Generous so they never misrepresent a realistic response.
_MAX_ALIASES = 100
_MAX_SERIES = 10_000
_MAX_TOOLS = 1_000

_base_openapi = app.openapi


def custom_openapi() -> dict[str, Any]:
    """Augment the generated spec: mark endpoints public and bound array sizes.

    Wraps FastAPI's own ``openapi()`` (and its cache) so the base schema always
    matches what FastAPI would emit; we only layer on two documentation facts.
    """
    schema = _base_openapi()

    # These are read-only, intentionally public dashboard endpoints (auth/rate
    # limiting are deferred). ``security: []`` states "no auth required"
    # explicitly rather than leaving the policy unstated.
    for path_item in schema["paths"].values():
        for method, operation in path_item.items():
            if method in _HTTP_METHODS:
                operation.setdefault("security", [])

    schemas = schema.get("components", {}).get("schemas", {})
    aliases = schemas.get("Tool", {}).get("properties", {}).get("aliases")
    if aliases is not None:
        aliases["maxItems"] = _MAX_ALIASES
    series = schemas.get("SentimentSeries", {}).get("properties", {}).get("series")
    if series is not None:
        series["maxItems"] = _MAX_SERIES
    tools_array = (
        schema["paths"]
        .get("/api/v1/tools", {})
        .get("get", {})
        .get("responses", {})
        .get("200", {})
        .get("content", {})
        .get("application/json", {})
        .get("schema")
    )
    if tools_array is not None and tools_array.get("type") == "array":
        tools_array["maxItems"] = _MAX_TOOLS

    return schema


app.openapi = custom_openapi  # type: ignore[method-assign]
