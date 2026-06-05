"""Vibecheck API service.

A FastAPI app that serves dashboard data from the shared ``lib_db`` data layer.
The app owns the async connection pool's lifecycle via the lifespan hook; the
``/health`` endpoint is deliberately DB-free so liveness never depends on a
reachable database.
"""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from lib_db import create_pool

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


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe — does not touch the database."""
    return {"status": "ok"}
