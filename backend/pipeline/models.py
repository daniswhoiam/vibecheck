"""Shared transfer models for the VibeCheck data pipeline.

PostCreate is used by all source collectors to pass normalized post data
to storage_service.save_post(). It is NOT an ORM model.
"""
from datetime import datetime
from pydantic import BaseModel


class PostCreate(BaseModel):
    """Normalized post data from any collection source.

    source: one of "hackernews" | "reddit" | "discourse" | "devto"
    external_id: source-specific unique ID (e.g., HN objectID, Reddit submission ID)
    url: canonical URL to the post (None for self-posts without link)
    title: headline/title (None for pure comment posts)
    body: full post text, pre-truncated to MAX_BODY_CHARS by the collector
    published_at: UTC-aware datetime of original publication
    metadata: dict of engagement metrics (score, comment_count, etc.) — varies per source
    """
    source: str
    external_id: str
    url: str | None = None
    title: str | None = None
    body: str | None = None
    published_at: datetime
    metadata: dict | None = None
