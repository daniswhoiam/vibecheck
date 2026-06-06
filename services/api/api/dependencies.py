"""FastAPI dependencies: a pooled DB connection and an injectable clock.

`get_now` is injectable so tests can pin "now" via app.dependency_overrides,
keeping time-based assertions deterministic without widening the public API.
"""

import datetime as dt
from collections.abc import AsyncIterator
from typing import Any

from fastapi import Request
from psycopg import AsyncConnection


async def get_conn(request: Request) -> AsyncIterator[AsyncConnection[Any]]:
    """Yield one connection from the app's pool for the duration of a request."""
    async with request.app.state.pool.connection() as conn:
        yield conn


def get_now() -> dt.datetime:
    """Current UTC time. Overridden in tests for deterministic windows."""
    return dt.datetime.now(dt.UTC)
