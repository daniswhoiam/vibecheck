"""Entity mention extraction service for VibeCheck Phase 11.

Implements keyword-based entity mention detection using word boundary regex —
the same pattern proven in Phase 6 filter_service.py is_relevant() function.

Usage:
    extractor = MentionExtractor()
    await extractor.load_entities(session)   # Call once per job run
    ids = extractor.extract_mentions(text)   # Call per post
    count = await extract_and_save_mentions(session, post_id, text, extractor)
"""
import re
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from db.models import Entity, PostEntityMention

logger = logging.getLogger(__name__)


class MentionExtractor:
    """Extract entity mentions from post text using keyword matching.

    Implements case-insensitive word-boundary matching for each entity name
    loaded from the database. Caches entity list in memory for the duration
    of a job run — call load_entities() once per job, not per post.
    """

    def __init__(self):
        self._entity_map: dict[str, int] | None = None

    async def load_entities(self, session: AsyncSession) -> None:
        """Load all entities from DB into memory as {name: entity_id} map.

        Idempotent — returns immediately if already loaded.
        """
        if self._entity_map is not None:
            return
        query = select(Entity.name, Entity.id)
        result = await session.execute(query)
        self._entity_map = {row.name: row.id for row in result.all()}
        logger.info("MentionExtractor: loaded %d entities", len(self._entity_map))

    def extract_mentions(self, text: str | None) -> set[int]:
        """Return set of entity IDs mentioned in text (word-boundary, case-insensitive).

        Args:
            text: Post title + body concatenated. None or empty → empty set.

        Returns:
            Set of entity_id integers for entities found in text.

        Raises:
            RuntimeError: If load_entities() has not been called yet.
        """
        if self._entity_map is None:
            raise RuntimeError(
                "MentionExtractor not initialized — call load_entities() first"
            )
        if not text:
            return set()

        mentioned_ids: set[int] = set()
        for entity_name, entity_id in self._entity_map.items():
            pattern = r"\b" + re.escape(entity_name) + r"\b"
            if re.search(pattern, text, re.IGNORECASE):
                mentioned_ids.add(entity_id)
        return mentioned_ids


async def extract_and_save_mentions(
    session: AsyncSession,
    post_id: int,
    text: str | None,
    extractor: MentionExtractor,
) -> int:
    """Extract entity mentions from text and save PostEntityMention rows.

    Idempotent: ON CONFLICT DO NOTHING handles re-runs safely.

    Args:
        session: Active AsyncSession.
        post_id: ID of the post to link entities to.
        text: Post title + body concatenated.
        extractor: Initialized MentionExtractor (load_entities already called).

    Returns:
        Count of PostEntityMention rows now associated with this post.
        Returns 0 if no entities found in text.
    """
    mention_ids = extractor.extract_mentions(text)

    if not mention_ids:
        logger.debug("extract_and_save_mentions: post %d has no entity mentions", post_id)
        return 0

    stmt = pg_insert(PostEntityMention).values([
        {"post_id": post_id, "entity_id": eid}
        for eid in mention_ids
    ]).on_conflict_do_nothing()

    await session.execute(stmt)
    await session.commit()

    # Verify actual count (rowcount may be -1 with ON CONFLICT)
    count_query = select(PostEntityMention).where(
        PostEntityMention.post_id == post_id
    )
    result = await session.execute(count_query)
    count = len(result.all())

    logger.debug(
        "extract_and_save_mentions: post %d → %d entities linked",
        post_id, count,
    )
    return count
