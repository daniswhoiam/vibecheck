"""Entity listing and detail endpoints for VibeCheck API.

Phase 7: latest_sentiment now sourced from SentimentRollup (replaces v1.0 timeseries table).
Phase 8: Added GET /entities/{id}/aspects endpoint for aspect-level sentiment aggregation.
"""
from typing import Dict, Literal, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from db.models import Entity, SentimentRollup, AspectSentiment
from api.schemas.entity import EntitySchema, EntityDetailSchema
from api.schemas.aspect import AspectSentimentResponse, AspectWindowSchema
from db.session import get_session
from utils.constants import VALID_ASPECTS


router = APIRouter(prefix="/entities", tags=["entities"])


@router.get("", response_model=list[EntityDetailSchema])
async def list_entities(session: AsyncSession = Depends(get_session)):
    """List all tracked AI entities (models and tools).

    Returns:
        List of entities with latest_sentiment from most recent daily rollup.
    """
    query = select(Entity).order_by(Entity.name)
    result = await session.execute(query)
    entities = result.scalars().all()

    entities_with_sentiment = []
    for entity in entities:
        # Latest rollup row for this entity (most recent date)
        sentiment_query = (
            select(SentimentRollup.sentiment_mean)
            .where(SentimentRollup.entity_id == entity.id)
            .order_by(SentimentRollup.rollup_date.desc())
            .limit(1)
        )
        sentiment_result = await session.execute(sentiment_query)
        latest_sentiment = sentiment_result.scalar_one_or_none()

        entities_with_sentiment.append(
            EntityDetailSchema.model_validate({
                "id": entity.id,
                "name": entity.name,
                "category": entity.category,
                "created_at": entity.created_at,
                "latest_sentiment": latest_sentiment,
            })
        )

    return entities_with_sentiment


@router.get("/{entity_id}", response_model=EntityDetailSchema)
async def get_entity(entity_id: int, session: AsyncSession = Depends(get_session)):
    """Get details for a specific entity.

    Args:
        entity_id: Unique entity identifier

    Returns:
        Entity details with latest_sentiment from most recent rollup.

    Raises:
        HTTPException: 404 if entity not found
    """
    result = await session.execute(
        select(Entity).where(Entity.id == entity_id)
    )
    entity = result.scalar_one_or_none()

    if entity is None:
        raise HTTPException(status_code=404, detail=f"Entity {entity_id} not found")

    # Latest rollup for this entity
    sentiment_query = (
        select(SentimentRollup.sentiment_mean)
        .where(SentimentRollup.entity_id == entity_id)
        .order_by(SentimentRollup.rollup_date.desc())
        .limit(1)
    )
    sentiment_result = await session.execute(sentiment_query)
    latest_sentiment = sentiment_result.scalar_one_or_none()

    return EntityDetailSchema.model_validate({
        "id": entity.id,
        "name": entity.name,
        "category": entity.category,
        "created_at": entity.created_at,
        "latest_sentiment": latest_sentiment,
    })


@router.get("/{entity_id}/aspects", response_model=AspectSentimentResponse)
async def get_entity_aspects(
    entity_id: int,
    window: Literal["7d", "30d", "90d"] = Query("7d", description="Time window: 7d, 30d, or 90d"),
    source: Optional[Literal["hn", "reddit", "discourse", "devto"]] = Query(
        None, description="Filter by source: hn, reddit, discourse, devto"
    ),
    session: AsyncSession = Depends(get_session),
):
    """Get aggregated aspect-level sentiment for an entity over a time window.

    Aggregates AspectSentiment rows for the entity, grouped by aspect.
    Time windows are fixed: 7d, 30d, 90d (from locked CONTEXT.md decision).
    Source filter restricts aggregation to posts from a specific platform.

    Args:
        entity_id: Unique entity identifier
        window: Time window (7d, 30d, 90d). Defaults to 7d.
        source: Optional source filter (hn, reddit, discourse, devto).

    Returns:
        AspectSentimentResponse with aggregated aspect scores.
        All 7 VALID_ASPECTS keys always present; count=0 and mean=None if no data.

    Raises:
        HTTPException: 404 if entity not found.
        HTTPException: 422 if window or source is invalid (FastAPI validation).
    """
    window_days = {"7d": 7, "30d": 30, "90d": 90}
    days = window_days[window]

    # Verify entity exists
    entity_result = await session.execute(
        select(Entity).where(Entity.id == entity_id)
    )
    if entity_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail=f"Entity {entity_id} not found")

    # Build aggregation query — join through posts for source filter support
    # AspectSentiment has entity_id but no direct source column — join via post_id to posts.source
    source_filter = ""
    query_params: dict = {"entity_id": entity_id}
    if source:
        source_filter = "AND p.source = :source"
        query_params["source"] = source

    # NOTE: PostgreSQL does not support bind parameters inside INTERVAL strings.
    # days is validated against the whitelist {"7d": 7, "30d": 30, "90d": 90} above — safe.
    agg_query = text(f"""
        SELECT
            asp.aspect,
            ROUND(AVG(asp.score)::numeric, 3) AS mean_score,
            COUNT(*)::int AS post_count
        FROM aspect_sentiments asp
        JOIN posts p ON p.id = asp.post_id
        WHERE asp.entity_id = :entity_id
          AND asp.created_at >= NOW() AT TIME ZONE 'UTC' - INTERVAL '{days} days'
          {source_filter}
        GROUP BY asp.aspect
        ORDER BY asp.aspect
    """)

    result = await session.execute(agg_query, query_params)
    rows = result.all()

    # Build aspects dict — ensure all 7 VALID_ASPECTS keys present
    aspects_data: Dict[str, AspectWindowSchema] = {}
    for row in rows:
        if row.aspect in VALID_ASPECTS:  # Skip any invalid aspects from DB
            aspects_data[row.aspect] = AspectWindowSchema(
                mean=float(row.mean_score) if row.mean_score is not None else None,
                count=row.post_count,
            )

    # Fill missing aspects with count=0, mean=None
    for aspect in VALID_ASPECTS:
        if aspect not in aspects_data:
            aspects_data[aspect] = AspectWindowSchema(mean=None, count=0)

    return AspectSentimentResponse(
        entity_id=entity_id,
        window=window,
        source=source,
        aspects=aspects_data,
    )
