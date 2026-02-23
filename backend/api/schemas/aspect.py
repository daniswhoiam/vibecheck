"""Aspect sentiment response schemas for VibeCheck API Phase 8.

New endpoint: GET /entities/{id}/aspects?window=7d|30d|90d&source=hn|reddit|discourse|devto
Returns aggregated aspect scores over the specified time window.
"""
from typing import Dict, Optional
from pydantic import BaseModel, ConfigDict


class AspectWindowSchema(BaseModel):
    """Aggregated score for a single aspect within a time window.

    Attributes:
        mean: Average aspect score in [-1.0, 1.0] across all contributing posts.
              None if no posts in window have this aspect scored.
        count: Number of posts contributing to this aspect's mean.
    """
    mean: Optional[float]
    count: int

    model_config = ConfigDict(from_attributes=True)


class AspectSentimentResponse(BaseModel):
    """Aspect-level sentiment aggregation for one entity over a time window.

    Attributes:
        entity_id: Entity identifier.
        window: Time window label (7d, 30d, or 90d).
        source: Optional source filter applied (None if all sources included).
        aspects: Dict mapping aspect name → {mean, count}.
                 All 7 VALID_ASPECTS keys always present; count=0 if no data.
    """
    entity_id: int
    window: str
    source: Optional[str]
    aspects: Dict[str, AspectWindowSchema]
