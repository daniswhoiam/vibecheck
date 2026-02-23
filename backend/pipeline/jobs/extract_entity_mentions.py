"""Backfill job: populate post_entity_mentions for all existing posts.

Runs once on startup to link existing posts to their mentioned entities.
Idempotent: only processes posts with no existing PostEntityMention rows.
Uses batched processing (BACKFILL_BATCH_SIZE=1000) to avoid OOM on Render.

Returns stats dict compatible with wrapped_job_execution() audit logging:
    {posts_scanned, mentions_added, posts_with_no_mentions, errors}
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.models import Post, PostEntityMention
from pipeline.services.mention_service import MentionExtractor, extract_and_save_mentions

logger = logging.getLogger(__name__)

BACKFILL_BATCH_SIZE = 1000


async def run_backfill_entity_mentions(session: AsyncSession) -> dict:
    """Backfill PostEntityMention rows for all posts without entity links.

    Processes posts in batches of BACKFILL_BATCH_SIZE to avoid loading all
    posts into memory at once (prevents OOM on Render with large post tables).

    Idempotent: uses NOT EXISTS subquery to skip already-processed posts.
    Can be safely re-run without creating duplicate rows.

    Args:
        session: Active AsyncSession.

    Returns:
        Stats dict: {posts_scanned, mentions_added, posts_with_no_mentions, errors}
    """
    stats = {
        "posts_scanned": 0,
        "mentions_added": 0,
        "posts_with_no_mentions": 0,
        "errors": 0,
    }

    # Load entity list once — shared across all batches
    extractor = MentionExtractor()
    await extractor.load_entities(session)

    logger.info("run_backfill_entity_mentions: starting backfill")

    offset = 0
    while True:
        # NOT EXISTS subquery: only select posts with no PostEntityMention rows yet
        has_mentions = (
            select(PostEntityMention.id)
            .where(PostEntityMention.post_id == Post.id)
            .exists()
        )

        query = (
            select(Post.id, Post.title, Post.body)
            .where(~has_mentions)
            .order_by(Post.id)
            .limit(BACKFILL_BATCH_SIZE)
            .offset(offset)
        )

        result = await session.execute(query)
        posts = result.all()

        if not posts:
            break  # No more unprocessed posts

        logger.info(
            "run_backfill_entity_mentions: processing batch of %d posts (offset=%d)",
            len(posts), offset,
        )

        for post in posts:
            stats["posts_scanned"] += 1
            try:
                text = ((post.title or "") + " " + (post.body or "")).strip()
                count = await extract_and_save_mentions(
                    session, post.id, text, extractor
                )
                if count > 0:
                    stats["mentions_added"] += count
                else:
                    stats["posts_with_no_mentions"] += 1
            except Exception as exc:
                logger.error(
                    "run_backfill_entity_mentions: error on post %d: %s",
                    post.id, exc, exc_info=True,
                )
                stats["errors"] += 1

        offset += BACKFILL_BATCH_SIZE

    logger.info(
        "run_backfill_entity_mentions: complete — %s",
        {k: v for k, v in stats.items() if v > 0},
    )
    return stats
