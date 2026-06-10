"""One ingestion cycle: registry -> fetch -> detect -> dedup -> publish.

The cycle is wired from the outside (fetchers and publisher are injected), so
sources are pluggable and the tests exercise the real registry + dedup
queries without a broker. One failing source never blocks the others — its
failure is logged and the cycle continues.
"""

import datetime as dt
import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any

from lib_db import queries
from psycopg_pool import AsyncConnectionPool

from ingestion.detection import ToolMatcher
from ingestion.posts import FetchedPost

logger = logging.getLogger(__name__)

# (tool display names to search for, window start) -> canonical posts
Fetcher = Callable[[Sequence[str], dt.datetime], Awaitable[list[FetchedPost]]]
Publisher = Callable[[FetchedPost, Sequence[str]], Awaitable[None]]


@dataclass
class CycleStats:
    fetched: int = 0
    published: int = 0
    skipped_existing: int = 0
    skipped_no_mention: int = 0


async def run_cycle(
    pool: AsyncConnectionPool[Any],
    publish: Publisher,
    fetchers: Sequence[Fetcher],
    *,
    lookback: dt.timedelta,
) -> CycleStats:
    since = dt.datetime.now(dt.UTC) - lookback

    # Fresh registry every cycle: seeding a new tool needs no redeploy.
    async with pool.connection() as conn:
        tools = await queries.list_tools(conn)
    matcher = ToolMatcher({t.slug: [t.display_name, *t.aliases] for t in tools})
    tool_queries = [t.display_name for t in tools]

    posts: dict[tuple[str, str], FetchedPost] = {}
    for fetcher in fetchers:
        try:
            fetched = await fetcher(tool_queries, since)
        except Exception:
            logger.exception("fetcher failed; continuing with remaining sources")
            continue
        for post in fetched:
            posts[(post.source, post.source_id)] = post

    stats = CycleStats(fetched=len(posts))
    for post in posts.values():
        slugs = sorted(matcher.detect(post.content))
        if not slugs:
            stats.skipped_no_mention += 1
            continue
        async with pool.connection() as conn:
            existing = await queries.get_post_id_by_source(
                conn, source=post.source, source_id=post.source_id
            )
        if existing is not None:
            stats.skipped_existing += 1
            continue
        await publish(post, slugs)
        stats.published += 1
    return stats
