"""APScheduler job: collect articles from Dev.to via Forem API v1.

Strategy:
1. Fetch article list by tag (metadata + description only)
2. Filter on title+description (cheap — avoids unnecessary body fetches)
3. Concurrently fetch full body_markdown for articles passing title filter
   (semaphore-limited to BODY_FETCH_CONCURRENCY=5 concurrent requests)
4. Re-check relevance on full body before storing
"""
import asyncio
import logging
import os
import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from pipeline.clients.devto_client import (
    DEVTO_TAGS,
    BODY_FETCH_CONCURRENCY,
    fetch_devto_articles,
    fetch_article_body,
    normalize_devto_article,
)
from pipeline.models import PostCreate
from pipeline.services.filter_service import is_relevant
from pipeline.services.storage_service import save_post
from pipeline.services.mention_service import MentionExtractor, extract_and_save_mentions

logger = logging.getLogger(__name__)


async def run_collect_devto(session: AsyncSession) -> dict:
    """Collect Dev.to articles tagged with AI/LLM/tool keywords.

    DEVTO_API_KEY env var is optional — improves rate limits but not required.
    """
    stats = {
        "collected": 0,
        "filtered_title": 0,
        "filtered_body": 0,
        "duplicates": 0,
        "errors": 0,
        "mentions_extracted": 0,
    }

    api_key = os.environ.get("DEVTO_API_KEY")
    seen_ids: set[int] = set()  # Dedup across tags (same article may appear in multiple tags)
    semaphore = asyncio.Semaphore(BODY_FETCH_CONCURRENCY)

    # Initialize mention extractor once per job run (not per post)
    extractor = MentionExtractor()
    await extractor.load_entities(session)

    async def _fetch_body_limited(article_id: int, client: httpx.AsyncClient) -> str | None:
        async with semaphore:
            return await fetch_article_body(article_id, client, api_key)

    async with httpx.AsyncClient() as client:
        for tag in DEVTO_TAGS:
            try:
                articles = await fetch_devto_articles(tag, client, api_key, page=1, per_page=30)
            except Exception as exc:
                logger.error("Failed to fetch Dev.to articles for tag '%s': %s", tag, exc)
                stats["errors"] += 1
                continue

            # Pass 1: filter on title + description (cheap)
            candidate_ids: list[int] = []
            article_map: dict[int, dict] = {}
            for article in articles:
                article_id = article.get("id")
                if not article_id or article_id in seen_ids:
                    continue
                seen_ids.add(article_id)
                article_map[article_id] = article

                title = article.get("title", "")
                description = article.get("description", "")
                if not is_relevant(f"{title} {description}"):
                    stats["filtered_title"] += 1
                    continue
                candidate_ids.append(article_id)

            if not candidate_ids:
                continue

            # Pass 2: concurrently fetch full bodies for candidates
            bodies = await asyncio.gather(
                *[_fetch_body_limited(aid, client) for aid in candidate_ids],
                return_exceptions=True,
            )

            for article_id, body in zip(candidate_ids, bodies):
                if isinstance(body, Exception):
                    logger.warning("Body fetch failed for Dev.to article %d: %s", article_id, body)
                    body = None

                article = article_map[article_id]
                normalized = normalize_devto_article(article, body if isinstance(body, str) else None)
                full_text = f"{normalized['title'] or ''} {normalized['body'] or ''}"

                if not is_relevant(full_text):
                    stats["filtered_body"] += 1
                    continue

                post = PostCreate(**normalized)
                try:
                    saved = await save_post(post, session)
                    if saved:
                        stats["collected"] += 1
                        # Extract entity mentions for newly collected article
                        try:
                            mention_count = await extract_and_save_mentions(
                                session, saved.id, full_text, extractor
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
                    logger.error("Error storing Dev.to article %d: %s", article_id, exc)
                    stats["errors"] += 1

    logger.info("Dev.to collection complete: %s", {k: v for k, v in stats.items() if v > 0})
    return stats
