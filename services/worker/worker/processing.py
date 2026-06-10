"""The per-message processing chain: post -> mentions -> analysis results.

The caller (consumer) wraps each call in one connection + transaction, so a
failure anywhere leaves no partial writes. Every insert is an idempotent
insert-or-get on its natural key, which makes redelivery of an already
processed message a no-op rather than a duplicate.
"""

import asyncio
from typing import Any, Protocol

from lib_db import queries
from psycopg import AsyncConnection

from worker.messages import PermanentError, PostMessage
from worker.sentiment import SentimentResult


class Analyzer(Protocol):
    """What processing needs from a model wrapper (see worker.sentiment)."""

    @property
    def model_name(self) -> str: ...
    @property
    def model_version(self) -> str | None: ...
    def analyze(self, text: str) -> SentimentResult: ...


async def process_message(conn: AsyncConnection[Any], msg: PostMessage, analyzer: Analyzer) -> None:
    """Persist one analyzed post. Raises PermanentError for unfixable input."""
    # Resolve slugs before any write or inference: an unknown tool is a
    # contract violation that redelivery cannot fix.
    tools = []
    for slug in msg.tools:
        tool = await queries.get_tool_by_slug(conn, slug=slug)
        if tool is None:
            raise PermanentError(f"unknown tool slug {slug!r}")
        tools.append(tool)

    # The model is synchronous and CPU-bound; a thread keeps the event loop
    # (and AMQP heartbeats) alive during inference.
    result = await asyncio.to_thread(analyzer.analyze, msg.content)

    post = await queries.create_post(
        conn,
        source=msg.source,
        source_id=msg.source_id,
        content=msg.content,
        author=msg.author,
        url=msg.url,
        published_at=msg.published_at,
        metadata=msg.metadata,
    )
    if post is None:  # insert-or-get always returns a row; None is a DB fault
        raise RuntimeError("create_post returned no row")

    for tool in tools:
        mention = await queries.create_mention(conn, post_id=post.id, tool_id=tool.id)
        if mention is None:
            raise RuntimeError("create_mention returned no row")
        analysis = await queries.create_analysis_result(
            conn,
            mention_id=mention.id,
            model_name=analyzer.model_name,
            model_version=analyzer.model_version,
            score=result.score,
            label=result.label,
            raw_output=result.raw,
        )
        if analysis is None:
            raise RuntimeError("create_analysis_result returned no row")
