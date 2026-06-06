"""FastAPI dependencies: a pooled DB connection and an injectable clock.

`get_now` is injectable so tests can pin "now" via app.dependency_overrides,
keeping time-based assertions deterministic without widening the public API.
"""

import datetime as dt
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, HTTPException, Request
from psycopg import AsyncConnection

from api.periods import parse_period, validate_bucket


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
    period: str = "30d",
    bucket: str = "day",
    now: dt.datetime = Depends(get_now),
) -> ResolvedWindow:
    """Validate query params and compute the [start, end) UTC window.

    Invalid period/bucket -> 422. The window ends at the injected `now`.
    """
    try:
        delta = parse_period(period)
        validate_bucket(bucket)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ResolvedWindow(period=period, bucket=bucket, start=now - delta, end=now)
