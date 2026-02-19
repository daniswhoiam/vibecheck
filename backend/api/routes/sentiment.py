"""Sentiment time-series query endpoints for VibeCheck API.

Provides endpoints for querying sentiment trends over time for entities.
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from db.models import Entity, SentimentTimeseries
from api.schemas.sentiment import SentimentPointSchema, SentimentTimeseriesResponse
from db.session import get_session


router = APIRouter(prefix="/entities", tags=["sentiment"])


@router.get("/{entity_id}/sentiment", response_model=SentimentTimeseriesResponse)
async def get_entity_sentiment(
    entity_id: int,
    start_date: Optional[datetime] = Query(None, description="Filter to data on or after this ISO 8601 timestamp"),
    end_date: Optional[datetime] = Query(None, description="Filter to data on or before this ISO 8601 timestamp"),
    cursor: Optional[str] = Query(None, description="ISO 8601 timestamp for pagination (fetch data before this time)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of data points to return"),
    period: str = Query("daily", regex="^(hourly|daily)$", description="Aggregation period"),
    session: AsyncSession = Depends(get_session)
):
    """Get sentiment time-series data for a specific entity.

    Query sentiment trends over time with configurable granularity and date filtering.
    Returns paginated results with cursor-based pagination for large datasets.

    Args:
        entity_id: Unique entity identifier
        start_date: Optional ISO 8601 timestamp to filter data (inclusive)
        end_date: Optional ISO 8601 timestamp to filter data (inclusive)
        cursor: Optional ISO 8601 timestamp for pagination
        limit: Maximum results per page (1-1000, default 100)
        period: Aggregation period - "hourly" or "daily" (default "daily")

    Returns:
        SentimentTimeseriesResponse with data array and pagination metadata

    Raises:
        HTTPException: 404 if entity not found

    Example:
        GET /entities/1/sentiment?period=daily&limit=10

        Response:
        {
            "entity_id": 1,
            "period": "daily",
            "data": [
                {
                    "timestamp": "2025-01-15T00:00:00Z",
                    "period": "daily",
                    "sentiment_mean": 0.5,
                    "sentiment_min": -0.2,
                    "sentiment_max": 1.0,
                    "sentiment_std": 0.3,
                    "article_count": 150,
                    "reddit_sentiment": 0.7,
                    "reddit_thread_count": 45
                }
            ],
            "next_cursor": "2025-01-14T00:00:00Z",
            "has_more": true
        }
    """
    # Verify entity exists
    entity_query = select(Entity).where(Entity.id == entity_id)
    entity_result = await session.execute(entity_query)
    entity = entity_result.scalar_one_or_none()

    if entity is None:
        raise HTTPException(
            status_code=404,
            detail=f"Entity {entity_id} not found"
        )

    # Build base query for sentiment time-series
    query = select(SentimentTimeseries).where(
        SentimentTimeseries.entity_id == entity_id,
        SentimentTimeseries.period == period
    )

    # Apply date range filters
    if start_date:
        query = query.where(SentimentTimeseries.timestamp >= start_date)
    if end_date:
        query = query.where(SentimentTimeseries.timestamp <= end_date)

    # Apply cursor pagination
    if cursor:
        try:
            cursor_time = datetime.fromisoformat(cursor.replace('Z', '+00:00'))
            query = query.where(SentimentTimeseries.timestamp < cursor_time)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid cursor format: {cursor}. Use ISO 8601 format."
            )

    # Order by timestamp descending (newest first) and limit
    query = query.order_by(SentimentTimeseries.timestamp.desc()).limit(limit)

    # Execute query
    result = await session.execute(query)
    time_series_data = result.scalars().all()

    # Convert to Pydantic schemas
    points = [SentimentPointSchema.model_validate(ts) for ts in time_series_data]

    # Calculate pagination metadata
    next_cursor = points[-1].timestamp.isoformat() if points else None
    has_more = len(points) == limit

    return SentimentTimeseriesResponse(
        entity_id=entity_id,
        period=period,
        data=points,
        next_cursor=next_cursor,
        has_more=has_more
    )

