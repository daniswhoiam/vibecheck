"""Entity response schemas for API endpoints.

Provides schemas for listing and detailing AI entities (models and tools).
All datetime fields use ISO 8601 format (FastAPI default).
"""
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class EntitySchema(BaseModel):
    """Basic entity representation for listing endpoints.

    Attributes:
        id: Unique entity identifier
        name: Entity name (e.g., "GPT-4", "Claude")
        category: Entity type ("model" or "tool")
        created_at: Entity creation timestamp
    """

    id: int
    name: str
    category: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EntityDetailSchema(BaseModel):
    """Extended entity representation with latest sentiment for detail endpoint.

    Attributes:
        id: Unique entity identifier
        name: Entity name (e.g., "GPT-4", "Claude")
        category: Entity type ("model" or "tool")
        created_at: Entity creation timestamp
        latest_sentiment: Most recent sentiment score (-1 to 1)
                          TODO: Populate from SentimentTimeseries in plan 03-02
    """

    id: int
    name: str
    category: str
    created_at: datetime
    latest_sentiment: float | None = None

    model_config = ConfigDict(from_attributes=True)
