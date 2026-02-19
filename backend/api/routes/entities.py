"""Entity listing and detail endpoints for VibeCheck API.

Provides endpoints for querying tracked AI models and tools.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.models import Entity, SentimentTimeseries
from api.schemas.entity import EntitySchema, EntityDetailSchema
from db.session import get_session


router = APIRouter(prefix="/entities", tags=["entities"])


@router.get("", response_model=list[EntityDetailSchema])
async def list_entities(session: AsyncSession = Depends(get_session)):
    """List all tracked AI entities (models and tools).

    Returns:
        List of entities with latest_sentiment, ordered by name.
    """
    query = select(Entity).order_by(Entity.name)
    result = await session.execute(query)
    entities = result.scalars().all()

    # Build list with latest sentiment for each entity
    entities_with_sentiment = []
    for entity in entities:
        # Query latest sentiment (prefer daily, fall back to hourly)
        sentiment_query = select(SentimentTimeseries.sentiment_mean).where(
            SentimentTimeseries.entity_id == entity.id,
            SentimentTimeseries.period.in_(["daily", "hourly"])
        ).order_by(
            SentimentTimeseries.period.desc(),
            SentimentTimeseries.timestamp.desc()
        ).limit(1)

        sentiment_result = await session.execute(sentiment_query)
        latest_sentiment = sentiment_result.scalar_one_or_none()

        entity_dict = {
            "id": entity.id,
            "name": entity.name,
            "category": entity.category,
            "created_at": entity.created_at,
            "latest_sentiment": latest_sentiment
        }
        entities_with_sentiment.append(EntityDetailSchema.model_validate(entity_dict))

    return entities_with_sentiment


@router.get("/{entity_id}", response_model=EntityDetailSchema)
async def get_entity(entity_id: int, session: AsyncSession = Depends(get_session)):
    """Get details for a specific entity.

    Args:
        entity_id: Unique entity identifier

    Returns:
        Entity details with latest_sentiment field

    Raises:
        HTTPException: 404 if entity not found
    """
    query = select(Entity).where(Entity.id == entity_id)
    result = await session.execute(query)
    entity = result.scalar_one_or_none()

    if entity is None:
        raise HTTPException(
            status_code=404,
            detail=f"Entity {entity_id} not found"
        )

    # Query latest sentiment from SentimentTimeseries
    # Prefer daily, but fall back to hourly if no daily data exists
    sentiment_query = select(SentimentTimeseries.sentiment_mean).where(
        SentimentTimeseries.entity_id == entity_id,
        SentimentTimeseries.period.in_(["daily", "hourly"])
    ).order_by(
        SentimentTimeseries.period.desc(),  # Prefer daily over hourly
        SentimentTimeseries.timestamp.desc()
    ).limit(1)

    sentiment_result = await session.execute(sentiment_query)
    latest_sentiment = sentiment_result.scalar_one_or_none()

    # Create a dict with entity data and add latest_sentiment
    entity_dict = {
        "id": entity.id,
        "name": entity.name,
        "category": entity.category,
        "created_at": entity.created_at,
        "latest_sentiment": latest_sentiment
    }

    return EntityDetailSchema.model_validate(entity_dict)
