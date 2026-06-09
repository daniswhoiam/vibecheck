"""FastAPI dependencies: a pooled DB connection and an injectable clock.

`get_now` is injectable so tests can pin "now" via app.dependency_overrides,
keeping time-based assertions deterministic without widening the public API.
"""

import datetime as dt
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated, Any, Literal

from fastapi import Depends, Query, Request
from psycopg import AsyncConnection

from api.periods import PERIOD_PATTERN, parse_period


async def get_conn(request: Request) -> AsyncIterator[AsyncConnection[Any]]:
    """Yield one connection from the app's pool for the duration of a request."""
    async with request.app.state.pool.connection() as conn:
        yield conn


def get_now() -> dt.datetime:
    """Current UTC time. Overridden in tests for deterministic windows."""
    return dt.datetime.now(dt.UTC)


@dataclass(frozen=True)
class ResolvedWindow:
    period: str
    bucket: str
    start: dt.datetime
    end: dt.datetime


def resolve_window(
    period: Annotated[str, Query(pattern=PERIOD_PATTERN)] = "30d",
    bucket: Literal["day", "week", "month"] = "day",
    now: dt.datetime = Depends(get_now),
) -> ResolvedWindow:
    """Compute the [start, end) UTC window from validated query params.

    `period`/`bucket` are validated natively by FastAPI, so anything malformed
    is rejected with the standard 422 (HTTPValidationError) before this runs.
    The bounded period pattern also makes the timedelta overflow-proof. The
    window ends at the injected `now`.
    """
    return ResolvedWindow(period=period, bucket=bucket, start=now - parse_period(period), end=now)
