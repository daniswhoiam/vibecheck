"""Sentiment aggregation job for VibeCheck Phase 7.

Computes daily sentiment rollups per entity with per-source breakdown.
Only recomputes today's UTC date bucket — past days are immutable.
Upserts into sentiment_rollup table: create on first run, update on reruns.

source_breakdown JSONB format:
    {"hn": {"mean": 0.4, "count": 12}, "reddit": {"mean": -0.1, "count": 8}}

Returns stats dict compatible with wrapped_job_execution() audit logging.
"""
import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from db.models import SentimentRollup

logger = logging.getLogger(__name__)

# Raw SQL for aggregation — using jsonb_object_agg for per-source breakdown.
# Application-side aggregation would be much slower and more error-prone.
# sentiment_score in posts stores confidence (0-1); for aggregation we map:
#   Positive -> +1.0, Negative -> -1.0, Neutral -> 0.0
# This produces a signed sentiment_mean in [-1.0, 1.0] suitable for the API.
_AGG_QUERY = text("""
    SELECT
        pem.entity_id,
        ROUND(AVG(
            CASE p.sentiment_label
                WHEN 'Positive' THEN 1.0
                WHEN 'Negative' THEN -1.0
                ELSE 0.0
            END
        )::numeric, 3) AS sentiment_mean,
        COUNT(*)::int AS post_count,
        jsonb_object_agg(
            p.source,
            jsonb_build_object(
                'mean', ROUND(AVG(
                    CASE p.sentiment_label
                        WHEN 'Positive' THEN 1.0
                        WHEN 'Negative' THEN -1.0
                        ELSE 0.0
                    END
                )::numeric, 3),
                'count', COUNT(*)::int
            )
        ) AS source_breakdown
    FROM posts p
    JOIN post_entity_mentions pem ON p.id = pem.post_id
    WHERE DATE(p.published_at AT TIME ZONE 'UTC') = :today
      AND p.sentiment_label IS NOT NULL
    GROUP BY pem.entity_id
""")


async def run_aggregate_sentiment(session: AsyncSession) -> dict:
    """Recompute today's sentiment rollup for all entities.

    Runs a single aggregation query over all posts published today (UTC)
    that have been scored, grouped by entity and source. Upserts the result
    into sentiment_rollup — overwriting today's row if it already exists.

    Only today's bucket is recomputed; past days are never touched.

    Args:
        session: Active async database session.

    Returns:
        Stats dict with rollups_updated, entities_with_data, errors keys.
    """
    stats = {"rollups_updated": 0, "entities_with_data": 0, "errors": 0}

    today_utc = datetime.now(timezone.utc).date()
    # Use midnight UTC as the rollup_date timestamp for the day bucket
    today_ts = datetime(today_utc.year, today_utc.month, today_utc.day, tzinfo=timezone.utc)

    logger.info("aggregate_sentiment: computing rollup for %s UTC", today_utc.isoformat())

    try:
        result = await session.execute(_AGG_QUERY, {"today": today_utc})
        rows = result.all()
    except Exception as exc:
        logger.error("aggregate_sentiment: aggregation query failed: %s", exc, exc_info=True)
        stats["errors"] = 1
        return stats

    if not rows:
        logger.info("aggregate_sentiment: no scored posts found for today, skipping upsert")
        return stats

    stats["entities_with_data"] = len(rows)
    logger.info("aggregate_sentiment: aggregated %d entities for %s", len(rows), today_utc.isoformat())

    # Upsert each entity's rollup row
    for row in rows:
        entity_id, sentiment_mean, post_count, source_breakdown = (
            row.entity_id, row.sentiment_mean, row.post_count, row.source_breakdown
        )

        try:
            stmt = pg_insert(SentimentRollup).values(
                entity_id=entity_id,
                rollup_date=today_ts,
                sentiment_mean=float(sentiment_mean) if sentiment_mean is not None else None,
                post_count=post_count,
                source_breakdown=source_breakdown,
            ).on_conflict_do_update(
                index_elements=["entity_id", "rollup_date"],
                set_={
                    "sentiment_mean": float(sentiment_mean) if sentiment_mean is not None else None,
                    "post_count": post_count,
                    "source_breakdown": source_breakdown,
                    "updated_at": text("now()"),
                }
            )

            await session.execute(stmt)
            stats["rollups_updated"] += 1

        except Exception as exc:
            logger.error(
                "aggregate_sentiment: upsert failed for entity %d: %s",
                entity_id, exc, exc_info=True,
            )
            stats["errors"] += 1

    await session.commit()

    logger.info(
        "aggregate_sentiment: complete — rollups_updated=%d, errors=%d",
        stats["rollups_updated"], stats["errors"],
    )
    return stats
