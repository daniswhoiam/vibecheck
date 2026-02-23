"""Sentiment time-series response schemas for VibeCheck API v2.

Phase 7: Responses now include per-source sentiment breakdown in each data point.
Source breakdown structure: {"hn": {"mean": 0.4, "count": 12}, "reddit": {...}}
"""
from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, ConfigDict


class SentimentPointSchema(BaseModel):
    """Single daily sentiment data point with per-source breakdown.

    Attributes:
        rollup_date: UTC date for this rollup bucket (midnight UTC timestamp)
        sentiment_mean: Signed mean sentiment in [-1.0, 1.0]
            (Positive=+1.0, Negative=-1.0, Neutral=0.0 weighted average)
        post_count: Total posts contributing to this day's rollup
        source_breakdown: Per-source mean and count, e.g.:
            {"hn": {"mean": 0.4, "count": 12}, "reddit": {"mean": -0.1, "count": 8}}
    """
    rollup_date: datetime
    sentiment_mean: Optional[float]
    post_count: int
    source_breakdown: Optional[Dict[str, Any]]

    model_config = ConfigDict(from_attributes=True)


class SentimentTimeseriesResponse(BaseModel):
    """Paginated response for entity sentiment time-series query.

    Attributes:
        entity_id: Entity identifier
        data: Array of daily sentiment points (reverse chronological)
        next_cursor: ISO timestamp for next page (None if last page)
        has_more: Whether more data exists beyond this page
    """
    entity_id: int
    data: List[SentimentPointSchema]
    next_cursor: Optional[str]
    has_more: bool
