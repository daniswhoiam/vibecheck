"""Storage service for persisting collected posts to the database.

Implements duplicate rejection via the (source, external_id, published_at) UNIQUE
constraint on the posts table. IntegrityError on INSERT means the post is a
duplicate — return None without raising, so collectors can continue processing.

NOTE: content_hash is stored as a regular index (not unique constraint) because
TimescaleDB hypertables require all unique constraints to include the partition key
(published_at). Primary dedup key is (source, external_id, published_at).
"""
import logging
import re
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Post
from pipeline.models import PostCreate
from pipeline.services.deduplication_service import compute_content_hash

logger = logging.getLogger(__name__)

# Max body text stored per post (~99th percentile for Dev.to articles)
MAX_BODY_CHARS = 50_000

# Regex for stripping email addresses (GDPR: avoid storing PII in body text)
_EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Z|a-z]{2,}\b')


def _strip_pii(text: str) -> str:
    """Remove email addresses from text. Usernames in public posts are acceptable."""
    return _EMAIL_PATTERN.sub('[email removed]', text)


async def save_post(post_data: PostCreate, session: AsyncSession) -> "Post | None":
    """Persist a post to the database.

    Computes content_hash from URL (preferred) or body text, attempts INSERT,
    and returns the saved Post ORM object if saved. Returns None if duplicate
    (IntegrityError) without raising, so the caller can count duplicates and continue.

    Args:
        post_data: Normalized post from any source collector.
        session: Active AsyncSession (provided by wrapped_job_execution).

    Returns:
        Post ORM object (truthy, with .id populated) if the post was inserted successfully.
        None (falsy) if the post is a duplicate (source+external_id+published_at conflict).
    """
    # Compute content hash — URL preferred over body (canonical dedup key)
    hash_input = post_data.url or post_data.body or ""
    content_hash = compute_content_hash(hash_input)

    # Sanitize and truncate body text
    body = None
    if post_data.body:
        body = _strip_pii(post_data.body)
        if len(body) > MAX_BODY_CHARS:
            body = body[:MAX_BODY_CHARS]
            logger.debug(
                "Body truncated to %d chars for %s:%s",
                MAX_BODY_CHARS, post_data.source, post_data.external_id,
            )

    post = Post(
        source=post_data.source,
        external_id=post_data.external_id,
        url=post_data.url,
        title=post_data.title,
        body=body,
        content_hash=content_hash,
        published_at=post_data.published_at,
        post_metadata=post_data.metadata,
    )
    session.add(post)
    try:
        await session.commit()
        await session.refresh(post)
        return post
    except IntegrityError:
        await session.rollback()
        logger.debug(
            "Duplicate post skipped: %s:%s (hash=%s)",
            post_data.source, post_data.external_id, content_hash,
        )
        return None
