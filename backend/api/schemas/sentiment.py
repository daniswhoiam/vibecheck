"""Sentiment time-series response schemas for API endpoints.

Provides schemas for querying sentiment trends over time for entities.
All datetime fields use ISO 8601 format (FastAPI default).
"""
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import List, Optional


class SentimentPointSchema(BaseModel):
    """Single time-series data point for sentiment.

    Represents sentiment statistics aggregated over a time period (hourly or daily).

    Attributes:
        timestamp: Time period start (ISO 8601)
        period: Aggregation period ("hourly" or "daily")
        sentiment_mean: Average sentiment score (-1 to 1)
        sentiment_min: Minimum sentiment score in period
        sentiment_max: Maximum sentiment score in period
        sentiment_std: Standard deviation of sentiment scores
        article_count: Number of articles in period
        reddit_sentiment: Average Reddit sentiment score (-1 to 1)
        reddit_thread_count: Number of Reddit threads in period
    """

    timestamp: datetime
    period: str
    sentiment_mean: float | None
    sentiment_min: float | None
    sentiment_max: float | None
    sentiment_std: float | None
    article_count: int | None
    reddit_sentiment: float | None
    reddit_thread_count: int | None

    model_config = ConfigDict(from_attributes=True)


class SentimentTimeseriesResponse(BaseModel):
    """Paginated time-series response for entity sentiment queries.

    Contains sentiment data points with cursor-based pagination for large datasets.

    Attributes:
        entity_id: Entity identifier
        period: Aggregation period used for query
        data: Array of sentiment data points (reverse chronological)
        next_cursor: ISO timestamp for fetching next page (None if last page)
        has_more: Whether more data points exist beyond this page
    """

    entity_id: int
    period: str
    data: List[SentimentPointSchema]
    next_cursor: str | None
    has_more: bool
