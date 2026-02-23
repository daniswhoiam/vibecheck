"""APScheduler job: collect Hacker News stories and top-level comments.

Called by scheduler.py via wrapped_job_execution.
Fetches stories since the last successful run (or 7 days ago on first run).
Also fetches top-level comments from stories that pass the relevance filter.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from pipeline.clients.hackernews_client import (
    fetch_hn_stories,
    fetch_hn_comments_for_story,
    normalize_hn_story,
    normalize_hn_comment,
)
from pipeline.models import PostCreate
from pipeline.services.filter_service import is_relevant
from pipeline.services.storage_service import save_post

logger = logging.getLogger(__name__)

# Default lookback window for first run / backfill
DEFAULT_LOOKBACK_DAYS = 7
# For backfill, split into weekly chunks to avoid Algolia 1000-hit cap
BACKFILL_WINDOW_DAYS = 7
# Max retry attempts for transient failures
MAX_RETRIES = 3
RETRY_DELAYS = [0, 5, 30]  # seconds


async def _fetch_with_retry(coro_fn, *args, **kwargs):
    """Call an async function with simple exponential backoff retry."""
    for attempt, delay in enumerate(RETRY_DELAYS):
        if delay > 0:
            await asyncio.sleep(delay)
        try:
            return await coro_fn(*args, **kwargs)
        except Exception as exc:
            if attempt == MAX_RETRIES - 1:
                raise
            logger.warning("HN fetch attempt %d failed: %s. Retrying...", attempt + 1, exc)


async def run_collect_hackernews(session: AsyncSession) -> dict:
    """Collect HN stories and top-level comments relevant to tracked entities.

    Args:
        session: AsyncSession provided by wrapped_job_execution.

    Returns:
        Stats dict: {collected_stories, collected_comments, filtered, duplicates, errors}
    """
    stats = {
        "collected_stories": 0,
        "collected_comments": 0,
        "filtered": 0,
        "duplicates": 0,
        "errors": 0,
    }

    since = datetime.now(timezone.utc) - timedelta(days=DEFAULT_LOOKBACK_DAYS)
    since_unix = int(since.timestamp())

    async with httpx.AsyncClient() as client:
        # Retry outer fetch; individual story comment fetches do best-effort
        stories = await _fetch_with_retry(fetch_hn_stories, since_unix, client)

        for hit in stories:
            if not hit.get("objectID") or not hit.get("created_at_i"):
                continue

            normalized = normalize_hn_story(hit)
            text = f"{normalized['title'] or ''} {normalized['body'] or ''}"

            if not is_relevant(text):
                stats["filtered"] += 1
                continue

            post = PostCreate(**normalized)
            saved = await save_post(post, session)
            if saved:
                stats["collected_stories"] += 1
            else:
                stats["duplicates"] += 1

            # Fetch top-level comments for relevant stories
            try:
                comments = await fetch_hn_comments_for_story(hit["objectID"], client)
                for comment_hit in comments:
                    if not comment_hit.get("comment_text"):
                        continue
                    c_normalized = normalize_hn_comment(
                        comment_hit, story_title=normalized["title"]
                    )
                    c_text = c_normalized["body"] or ""
                    if not is_relevant(c_text):
                        stats["filtered"] += 1
                        continue
                    c_post = PostCreate(**c_normalized)
                    c_saved = await save_post(c_post, session)
                    if c_saved:
                        stats["collected_comments"] += 1
                    else:
                        stats["duplicates"] += 1
            except Exception as exc:
                logger.warning(
                    "Failed to fetch comments for story %s: %s",
                    hit["objectID"], exc,
                )
                stats["errors"] += 1

    logger.info(
        "HN collection complete: %s",
        {k: v for k, v in stats.items() if v > 0},
    )
    return stats
