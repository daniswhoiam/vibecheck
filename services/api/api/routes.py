"""Versioned dashboard read endpoints."""

import datetime as dt
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from lib_db import queries
from psycopg import AsyncConnection

from api.aggregate import fold_buckets
from api.dependencies import ResolvedWindow, get_conn, resolve_window
from api.models import SentimentPoint, SentimentSeries, Tool

router = APIRouter(prefix="/api/v1")


@router.get("/tools", response_model=list[Tool])
async def list_tools(
    conn: AsyncConnection[Any] = Depends(get_conn),
) -> list[Tool]:
    rows = await queries.list_tools(conn)
    return [Tool(slug=r.slug, display_name=r.display_name, aliases=r.aliases) for r in rows]


@router.get(
    "/sentiment/{tool}",
    response_model=SentimentSeries,
    responses={404: {"description": "Tool not found"}},
)
async def tool_sentiment(
    tool: str,
    window: ResolvedWindow = Depends(resolve_window),
    conn: AsyncConnection[Any] = Depends(get_conn),
) -> SentimentSeries:
    if await queries.get_tool_by_slug(conn, slug=tool) is None:
        raise HTTPException(status_code=404, detail="tool not found")
    rows = await queries.get_sentiment_by_tool_bucket(
        conn, slug=tool, published_at_1=window.start, published_at_2=window.end
    )
    day_rows: list[tuple[dt.datetime, int, float]] = []
    for r in rows:
        if r.avg_score is None:  # avg() over a non-empty day bucket is never NULL
            raise RuntimeError(f"unexpected NULL avg_score for bucket {r.bucket!r}")
        day_rows.append((r.bucket, r.n, r.avg_score))
    points = [
        SentimentPoint(bucket_start=b, n=n, avg_score=avg)
        for b, n, avg in fold_buckets(day_rows, window.bucket)
    ]
    return SentimentSeries(
        tool=tool,
        period=window.period,
        bucket=window.bucket,
        start=window.start,
        end=window.end,
        series=points,
    )
