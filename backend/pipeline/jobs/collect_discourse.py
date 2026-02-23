"""APScheduler job: collect topics from Discourse forums.

Fetches latest topics from forum.cursor.com and community.openai.com,
fetches the OP body for topics that pass the title relevance filter,
then re-checks relevance on the full body before storing.
"""
import asyncio
import logging
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from pipeline.clients.discourse_client import (
    DISCOURSE_FORUMS,
    fetch_discourse_topics,
    fetch_topic_body,
    normalize_discourse_topic,
)
from pipeline.models import PostCreate
from pipeline.services.filter_service import is_relevant
from pipeline.services.storage_service import save_post
from pipeline.services.mention_service import MentionExtractor, extract_and_save_mentions

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAYS = [0, 5, 30]


async def _fetch_with_retry(coro_fn, *args, **kwargs):
    for attempt, delay in enumerate(RETRY_DELAYS):
        if delay > 0:
            await asyncio.sleep(delay)
        try:
            return await coro_fn(*args, **kwargs)
        except Exception as exc:
            if attempt == MAX_RETRIES - 1:
                raise
            logger.warning("Discourse fetch attempt %d failed: %s", attempt + 1, exc)


async def run_collect_discourse(session: AsyncSession) -> dict:
    """Collect topics from all configured Discourse forums.

    Two-pass strategy:
    1. Filter on title (cheap) — skip obviously irrelevant topics
    2. Fetch full body for title-passing topics, re-check relevance on combined text
    3. Store topics that pass the full relevance check

    Returns stats dict: {collected, filtered_title, filtered_body, duplicates, errors}
    """
    stats = {
        "collected": 0,
        "filtered_title": 0,
        "filtered_body": 0,
        "duplicates": 0,
        "errors": 0,
        "mentions_extracted": 0,
    }

    # Initialize mention extractor once per job run (not per post)
    extractor = MentionExtractor()
    await extractor.load_entities(session)

    async with httpx.AsyncClient() as client:
        for forum_url in DISCOURSE_FORUMS:
            try:
                topics = await _fetch_with_retry(
                    fetch_discourse_topics, forum_url, client, max_pages=5
                )
            except Exception as exc:
                logger.error("Failed to fetch topics from %s: %s", forum_url, exc)
                stats["errors"] += 1
                continue

            for topic in topics:
                title = topic.get("title", "")

                # Pass 1: title-only filter (cheap)
                if not is_relevant(title):
                    stats["filtered_title"] += 1
                    continue

                # Pass 2: fetch body and re-check on full text
                slug = topic.get("slug", "")
                topic_id = topic.get("id")
                body = await fetch_topic_body(forum_url, slug, topic_id, client)

                full_text = f"{title} {body or ''}"
                if not is_relevant(full_text):
                    stats["filtered_body"] += 1
                    continue

                normalized = normalize_discourse_topic(topic, forum_url, body)
                post = PostCreate(**normalized)
                try:
                    saved = await save_post(post, session)
                    if saved:
                        stats["collected"] += 1
                        # Extract entity mentions for newly collected topic
                        try:
                            post_text = f"{normalized['title'] or ''} {normalized['body'] or ''}"
                            mention_count = await extract_and_save_mentions(
                                session, saved.id, post_text, extractor
                            )
                            stats["mentions_extracted"] += mention_count
                        except Exception as exc:
                            logger.warning(
                                "Failed to extract mentions for post %s: %s",
                                normalized.get("external_id", "?"), exc,
                            )
                    else:
                        stats["duplicates"] += 1
                except Exception as exc:
                    logger.error(
                        "Error storing Discourse topic %s/%s: %s",
                        forum_url, topic_id, exc,
                    )
                    stats["errors"] += 1

    logger.info("Discourse collection complete: %s", {k: v for k, v in stats.items() if v > 0})
    return stats
