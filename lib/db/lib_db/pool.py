"""Async connection pool factory for vibecheck's data layer.

Adds the one piece psycopg3 won't do implicitly - dict -> jsonb adaptation -
and otherwise leaves pool lifecycle to the calling service.
"""

from typing import Any

from psycopg import AsyncConnection
from psycopg.types.json import JsonbDumper
from psycopg_pool import AsyncConnectionPool


async def _configure(conn: AsyncConnection[Any]) -> None:
    """Register dict -> jsonb adaptation (psycopg3 will not do it implicitly)."""
    conn.adapters.register_dumper(dict, JsonbDumper)


def create_pool(dsn: str) -> AsyncConnectionPool[AsyncConnection[Any]]:
    """Create an unopened async pool. The caller owns ``open()`` / ``close()``."""
    return AsyncConnectionPool(dsn, configure=_configure, open=False)
