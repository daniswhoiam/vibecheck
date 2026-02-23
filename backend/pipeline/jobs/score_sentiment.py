"""Sentiment scoring job for VibeCheck Phase 7.

Queries posts with NULL sentiment_label, classifies them using GliClass,
and writes sentiment_label + sentiment_score back to the posts table.
Incremental: only processes unscored posts — never rescores.

Returns stats dict compatible with wrapped_job_execution() audit logging.
"""
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from db.models import Post
from pipeline.services.sentiment_service import SentimentClassifier

logger = logging.getLogger(__name__)

# Process unscored posts in batches to limit peak memory.
# 8 posts × 2000 chars ≈ ~100–200MB model memory on CPU.
# Increase to 16 after confirming memory headroom in production.
SCORE_BATCH_SIZE = 8


async def run_score_sentiment(session: AsyncSession) -> dict:
    """Score all unscored posts with GliClass zero-shot classification.

    Only processes posts where sentiment_label IS NULL (incremental).
    Writes sentiment_label (Positive/Negative/Neutral) and sentiment_score
    (confidence 0.0–1.0) back to each post row.

    Args:
        session: Active async database session.

    Returns:
        Stats dict with scored, skipped, errors keys.
    """
    stats = {"scored": 0, "skipped": 0, "errors": 0}

    # Fetch all unscored posts — we load IDs + text content only
    query = select(Post.id, Post.title, Post.body).where(
        Post.sentiment_label == None  # noqa: E711 — SQLAlchemy requires == None
    ).order_by(Post.id)  # Stable ordering for incremental processing

    result = await session.execute(query)
    rows = result.all()

    if not rows:
        logger.info("score_sentiment: no unscored posts found, skipping")
        return stats

    logger.info("score_sentiment: found %d unscored posts to classify", len(rows))

    # Build text inputs: title + body, with None guards
    post_ids = [row.id for row in rows]
    texts = [
        ((row.title or "") + " " + (row.body or "")).strip()
        for row in rows
    ]

    # Classify in one batch — SentimentClassifier loads model once, then unloads
    classifier = SentimentClassifier()
    try:
        results = await classifier.classify(texts)
    except Exception as exc:
        logger.error("score_sentiment: classification failed: %s", exc, exc_info=True)
        stats["errors"] = len(post_ids)
        return stats

    # Write results back in sub-batches to keep transactions small
    for i in range(0, len(post_ids), SCORE_BATCH_SIZE):
        batch_ids = post_ids[i : i + SCORE_BATCH_SIZE]
        batch_results = results[i : i + SCORE_BATCH_SIZE]

        for post_id, classification in zip(batch_ids, batch_results):
            stmt = (
                update(Post)
                .where(Post.id == post_id)
                .values(
                    sentiment_label=classification["label"],
                    sentiment_score=classification["score"],
                )
            )
            await session.execute(stmt)

        await session.commit()
        stats["scored"] += len(batch_ids)
        logger.info(
            "score_sentiment: committed batch %d/%d (%d posts)",
            min(i + SCORE_BATCH_SIZE, len(post_ids)),
            len(post_ids),
            len(batch_ids),
        )

    logger.info(
        "score_sentiment: complete — scored=%d, errors=%d",
        stats["scored"], stats["errors"],
    )
    return stats
