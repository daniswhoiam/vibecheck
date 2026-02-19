"""Entity service for entity lookup and management.

Entity name normalization (via ENTITY_VARIATIONS) removed in Phase 5.
New entity recognition will use structured source data in Phase 6.
"""
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Entity

logger = logging.getLogger(__name__)


async def get_entity_id_by_name(
    canonical_name: str,
    db_session: AsyncSession
) -> int | None:
    """Get entity database ID by canonical name.

    Args:
        canonical_name: Canonical entity name (must match Entity.name exactly).
        db_session: Async database session.

    Returns:
        Entity ID if found, None if not in database.
    """
    try:
        stmt = select(Entity).where(Entity.name == canonical_name)
        result = await db_session.execute(stmt)
        entity = result.scalar_one_or_none()

        if entity:
            logger.debug("Entity resolved: %s (id=%d)", canonical_name, entity.id)
            return entity.id
        else:
            logger.warning("Entity not in database: %s", canonical_name)
            return None

    except Exception as exc:
        logger.error("Entity lookup failed: %s (error=%s)", canonical_name, str(exc), exc_info=True)
        return None
