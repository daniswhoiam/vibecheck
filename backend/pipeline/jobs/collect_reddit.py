"""APScheduler job: collect Reddit posts from tool-specific and broad AI subreddits.

Two-layer filtering strategy:
- Tool-specific subreddits (r/ChatGPT etc.): apply is_relevant() as basic sanity check
- Broad subreddits (r/programming etc.): apply full ambiguity-aware is_relevant() strictly
"""
import asyncio
import logging
import os
from sqlalchemy.ext.asyncio import AsyncSession

from pipeline.clients.reddit_client import (
    TOOL_SUBREDDITS,
    BROAD_SUBREDDITS,
    fetch_subreddit_posts,
    normalize_reddit_post,
)
from pipeline.models import PostCreate
from pipeline.services.filter_service import is_relevant
from pipeline.services.storage_service import save_post

logger = logging.getLogger(__name__)

POSTS_PER_SUBREDDIT = 100  # asyncpraw .new(limit=100) per subreddit
MAX_RETRIES = 3
RETRY_DELAYS = [0, 5, 30]


async def _fetch_with_retry(subreddit: str, client_id: str, client_secret: str) -> list[dict]:
    """Fetch subreddit posts with simple retry on failure."""
    for attempt, delay in enumerate(RETRY_DELAYS):
        if delay > 0:
            await asyncio.sleep(delay)
        try:
            return await fetch_subreddit_posts(subreddit, client_id, client_secret, limit=POSTS_PER_SUBREDDIT)
        except Exception as exc:
            if attempt == MAX_RETRIES - 1:
                raise
            logger.warning("Reddit fetch attempt %d for r/%s failed: %s", attempt + 1, subreddit, exc)
    return []


async def run_collect_reddit(session: AsyncSession) -> dict:
    """Collect posts from Reddit subreddits.

    Returns early with errors=1 if Reddit credentials are not set.
    """
    stats = {
        "collected": 0,
        "filtered": 0,
        "duplicates": 0,
        "errors": 0,
    }

    client_id = os.environ.get("REDDIT_CLIENT_ID")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET")

    if not client_id or not client_secret:
        logger.error(
            "Reddit credentials not configured. Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET."
        )
        stats["errors"] = 1
        return stats

    async def _process_subreddit(subreddit: str, strict_filter: bool) -> None:
        try:
            posts = await _fetch_with_retry(subreddit, client_id, client_secret)
        except Exception as exc:
            logger.error("Failed to fetch r/%s: %s", subreddit, exc)
            stats["errors"] += 1
            return

        for post_dict in posts:
            normalized = normalize_reddit_post(post_dict)
            text = f"{normalized['title'] or ''} {normalized['body'] or ''}"

            if strict_filter and not is_relevant(text):
                stats["filtered"] += 1
                continue
            elif not strict_filter and not is_relevant(text):
                # Loose check for tool-specific subs — skip clearly irrelevant posts
                stats["filtered"] += 1
                continue

            post = PostCreate(**normalized)
            saved = await save_post(post, session)
            if saved:
                stats["collected"] += 1
            else:
                stats["duplicates"] += 1

    # Process tool-specific subreddits (loose filter — most posts ARE relevant)
    for subreddit in TOOL_SUBREDDITS:
        await _process_subreddit(subreddit, strict_filter=False)

    # Process broad subreddits (strict ambiguity-aware filter)
    for subreddit in BROAD_SUBREDDITS:
        await _process_subreddit(subreddit, strict_filter=True)

    logger.info("Reddit collection complete: %s", {k: v for k, v in stats.items() if v > 0})
    return stats
