"""Tier 2 LLM aspect extraction job for VibeCheck Phase 8.

Routes posts with low Tier 1 confidence (< 0.6) to the configured LLM provider
for per-entity aspect-level sentiment extraction. Stores results in AspectSentiment.

Routing criteria (ALL must be true):
- Post.sentiment_score < 0.6 (any label — Positive, Negative, Neutral)
- Post.sentiment_label IS NOT NULL (scored by Tier 1)
- No existing AspectSentiment rows for this post (idempotent)

Per-run volume cap: LLM_MAX_CALLS_PER_RUN env var (default 100).
Returns stats dict compatible with wrapped_pipeline_execution() audit logging.
"""
import logging
import os
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, exists

from db.models import Post, PostEntityMention, AspectSentiment, Entity
from pipeline.services.llm_provider import get_llm_provider
from utils.constants import VALID_ASPECTS

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = 0.6  # Posts below this are routed to Tier 2


async def run_extract_aspects(session: AsyncSession) -> dict:
    """Route low-confidence posts to LLM for per-entity aspect extraction.

    Queries posts where sentiment_score < 0.6, sentiment_label is not NULL,
    and no AspectSentiment rows exist yet (idempotent). Calls LLM provider once
    per job run (not per post). Stores all 7 VALID_ASPECTS per entity per post.

    Args:
        session: Active async database session.

    Returns:
        Stats dict with {routed, extracted, errors, skipped} keys.
    """
    stats = {"routed": 0, "extracted": 0, "errors": 0, "skipped": 0}

    max_calls = int(os.getenv("LLM_MAX_CALLS_PER_RUN", "100"))

    # Routing query — idempotent via NOT EXISTS on AspectSentiment
    has_aspects = exists(
        select(AspectSentiment.id).where(AspectSentiment.post_id == Post.id)
    )
    query = (
        select(Post.id, Post.title, Post.body)
        .where(
            and_(
                Post.sentiment_score < CONFIDENCE_THRESHOLD,
                Post.sentiment_label.isnot(None),
                ~has_aspects,
            )
        )
        .order_by(Post.id)
        .limit(max_calls)
    )

    result = await session.execute(query)
    posts_to_route = result.all()

    if not posts_to_route:
        logger.info("extract_aspects: no low-confidence posts to route, skipping")
        return stats

    logger.info(
        "extract_aspects: routing %d low-confidence posts", len(posts_to_route)
    )

    # Instantiate LLM provider once per job run — not per post
    provider = get_llm_provider()

    for post in posts_to_route:
        stats["routed"] += 1

        # Compose text (title + body, capped at 3000 chars)
        text = ((post.title or "") + " " + (post.body or "")).strip()[:3000]

        # Lookup entity names + IDs for this post via JOIN in one query
        mention_query = (
            select(PostEntityMention.entity_id, Entity.name)
            .join(Entity, Entity.id == PostEntityMention.entity_id)
            .where(PostEntityMention.post_id == post.id)
        )
        mention_result = await session.execute(mention_query)
        mention_rows = mention_result.all()

        if not mention_rows:
            logger.warning(
                "extract_aspects: post %s has no entity mentions, skipping", post.id
            )
            stats["skipped"] += 1
            continue

        # Build name → entity_id map
        entity_map = {row.name: row.entity_id for row in mention_rows}
        entity_names = list(entity_map.keys())

        # Call LLM provider (retry handled inside provider)
        try:
            aspects_by_entity = await provider.extract_aspects(text, entity_names)
        except Exception as exc:
            logger.error(
                "extract_aspects: LLM failed for post %s: %s", post.id, exc
            )
            stats["errors"] += 1
            continue  # Skip this post — will retry next run

        # Write AspectSentiment rows for each entity returned by LLM
        for entity_name, aspect_scores in aspects_by_entity.items():
            entity_id = entity_map.get(entity_name)
            if entity_id is None:
                # LLM hallucinated an entity not in PostEntityMention
                logger.warning(
                    "extract_aspects: LLM returned unmatched entity '%s' for post %s"
                    " — skipping",
                    entity_name,
                    post.id,
                )
                continue

            # Store all 7 VALID_ASPECTS — 0.0 for any aspect not in LLM output
            for aspect_name in VALID_ASPECTS:
                raw_score = float(aspect_scores.get(aspect_name, 0.0))
                # Clamp to [-1.0, 1.0] as safety guard
                score = max(-1.0, min(1.0, raw_score))

                session.add(
                    AspectSentiment(
                        post_id=post.id,
                        entity_id=entity_id,
                        aspect=aspect_name,
                        score=score,
                    )
                )

        # Commit after each post to keep transactions small
        await session.commit()
        stats["extracted"] += 1

    logger.info(
        "extract_aspects: complete — routed=%d, extracted=%d, errors=%d, skipped=%d",
        stats["routed"],
        stats["extracted"],
        stats["errors"],
        stats["skipped"],
    )
    return stats
