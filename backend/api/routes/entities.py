"""Entity listing and detail endpoints for VibeCheck API.

Phase 7: latest_sentiment now sourced from SentimentRollup (replaces v1.0 timeseries table).
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.models import Entity, SentimentRollup
from api.schemas.entity import EntitySchema, EntityDetailSchema
from db.session import get_session


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
