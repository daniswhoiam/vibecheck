"""Sentiment time-series query endpoints for VibeCheck API v2.

Phase 7: Queries SentimentRollup table (replaces v1.0 SentimentTimeseries).
Returns daily rollups with per-source sentiment breakdown.
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from db.models import Entity, SentimentRollup
from api.schemas.sentiment import SentimentPointSchema, SentimentTimeseriesResponse
from db.session import get_session


router = APIRouter(prefix="/entities", tags=["sentiment"])


@router.get("/{entity_id}/sentiment", response_model=SentimentTimeseriesResponse)
async def get_entity_sentiment(
    entity_id: int,
    start_date: Optional[datetime] = Query(None, description="Filter to data on or after this ISO 8601 date"),
    end_date: Optional[datetime] = Query(None, description="Filter to data on or before this ISO 8601 date"),
    cursor: Optional[str] = Query(None, description="ISO 8601 timestamp for pagination (fetch data before this time)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of data points to return"),
    session: AsyncSession = Depends(get_session),
):
    """Get daily sentiment time-series for an entity, with per-source breakdown.

    Returns daily rollup rows from sentiment_rollup table. Each data point includes
    the overall sentiment mean and a source_breakdown dict showing per-source stats.

    Args:
        entity_id: Unique entity identifier
        start_date: Optional ISO 8601 filter (inclusive)
        end_date: Optional ISO 8601 filter (inclusive)
        cursor: Optional ISO 8601 timestamp for pagination (fetch data before this time)
        limit: Max results per page (1-1000, default 100)

    Returns:
        SentimentTimeseriesResponse with data array and pagination metadata

    Raises:
        HTTPException: 404 if entity not found
    """
    # Verify entity exists
    entity_result = await session.execute(
        select(Entity).where(Entity.id == entity_id)
    )
    if entity_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail=f"Entity {entity_id} not found")

    # Build rollup query
    query = select(SentimentRollup).where(SentimentRollup.entity_id == entity_id)

    if start_date:
        query = query.where(SentimentRollup.rollup_date >= start_date)
    if end_date:
        query = query.where(SentimentRollup.rollup_date <= end_date)

    if cursor:
        try:
            cursor_time = datetime.fromisoformat(cursor.replace("Z", "+00:00"))
            query = query.where(SentimentRollup.rollup_date < cursor_time)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid cursor format: {cursor}. Use ISO 8601 format.",
            )

    query = query.order_by(SentimentRollup.rollup_date.desc()).limit(limit)

    result = await session.execute(query)
    rollups = result.scalars().all()

    # Convert ORM rows to response schema
    points = [
        SentimentPointSchema(
            rollup_date=r.rollup_date,
            sentiment_mean=r.sentiment_mean,
            post_count=r.post_count,
            source_breakdown=r.source_breakdown,
        )
        for r in rollups
    ]

    next_cursor = points[-1].rollup_date.isoformat() if points else None
    has_more = len(points) == limit

    return SentimentTimeseriesResponse(
        entity_id=entity_id,
        data=points,
        next_cursor=next_cursor,
        has_more=has_more,
    )
