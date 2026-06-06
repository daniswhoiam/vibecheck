"""Public queries API.

Re-exports all generated query functions.  The one exception is
``get_sentiment_by_tool_bucket``, which is wrapped here so callers use the
intuitive ``bucket=`` keyword while the underlying generated function uses the
scythe-assigned positional name ``p4``.
"""

import datetime

from psycopg import AsyncConnection

from .generated.queries import (
    CreateAnalysisResultRow,
    CreateMentionRow,
    CreatePostRow,
    GetPostsByToolAndRangeRow,
    GetSentimentByToolBucketRow,
    GetToolBySlugRow,
    ListToolsRow,
    create_analysis_result,
    create_mention,
    create_post,
    get_posts_by_tool_and_range,
    get_tool_by_slug,
    list_tools,
)
from .generated.queries import (
    get_sentiment_by_tool_bucket as _get_sentiment_by_tool_bucket,
)

__all__ = [
    "CreateAnalysisResultRow",
    "CreateMentionRow",
    "CreatePostRow",
    "GetPostsByToolAndRangeRow",
    "GetSentimentByToolBucketRow",
    "GetToolBySlugRow",
    "ListToolsRow",
    "create_analysis_result",
    "create_mention",
    "create_post",
    "get_posts_by_tool_and_range",
    "get_sentiment_by_tool_bucket",
    "get_tool_by_slug",
    "list_tools",
]


async def get_sentiment_by_tool_bucket(
    conn: AsyncConnection,
    *,
    slug: str,
    bucket: str,
    published_at_1: datetime.datetime,
    published_at_2: datetime.datetime,
) -> list[GetSentimentByToolBucketRow]:
    """Execute GetSentimentByToolBucket query.

    Thin wrapper that exposes ``bucket`` as the keyword for the
    date_trunc granularity (e.g. ``'day'``, ``'week'``).
    """
    return await _get_sentiment_by_tool_bucket(
        conn,
        slug=slug,
        published_at_1=published_at_1,
        published_at_2=published_at_2,
        p4=bucket,
    )
