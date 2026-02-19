# Plan 05-01 Summary: Schema Reset — TimescaleDB Image, Destructive Migration, New ORM Models

## What Was Built
- **docker-compose.yml**: Switched postgres service from `postgres:16-alpine` to `timescale/timescaledb-ha:pg16-latest` (includes TimescaleDB + pgvector pre-installed). Removed `ASKNEWS_API_KEY` from backend environment.
- **006_reset_schema.py**: Destructive Alembic migration that drops old tables (articles, sentiment_timeseries, entities), creates TimescaleDB + pgvector extensions, and builds new schema: entities, posts (hypertable), post_entity_mentions, aspect_sentiments. Posts table uses composite PK (id, published_at) with Identity() on id for hypertable compatibility.
- **db/models.py**: Complete rewrite — removed Article/SentimentTimeseries, added Post, PostEntityMention, AspectSentiment ORM models. No ForeignKey constraints to posts.id (TimescaleDB hypertable limitation). Entity updated with server_default and relationships. SchedulerExecutionLog kept unchanged.
- **alembic/env.py**: Added pgvector type registration (`ischema_names['vector']`), TIMESCALE_SCHEMAS constant for filtering TimescaleDB internal schemas, and `include_object` filter to prevent autogenerate drift.

## Key Decisions
- Used `sa.Identity()` instead of `autoincrement=True` for posts.id — Identity() properly handles PostgreSQL GENERATED ALWAYS AS IDENTITY syntax for BigInteger columns
- No FK constraints from post_entity_mentions/aspect_sentiments to posts.id — TimescaleDB prohibits FK constraints referencing hypertable columns; referential integrity deferred to application layer (Phase 6)
- Entity FK constraints from junction tables are safe — entities is NOT a hypertable
- Downgrade uses `op.execute("DROP TABLE IF EXISTS ...")` instead of `op.drop_table(..., if_exists=True)` — Alembic API does not support if_exists parameter

## Verification Results
- Python syntax check on migration: PASS
- Content verification (revision chain, create_hypertable, all 4 tables): PASS
- models.py class verification: PASS (Post, PostEntityMention, AspectSentiment, SchedulerExecutionLog present; Article/SentimentTimeseries removed)
- env.py feature verification: PASS (ischema_names, include_object, TIMESCALE_SCHEMAS all present)
- Full migration run against TimescaleDB: DEFERRED to Plan 02 completion (pgvector Python package not yet in requirements.txt)

## Files Modified
- `docker-compose.yml` — TimescaleDB image + AskNews env var removal
- `backend/alembic/versions/006_reset_schema.py` — NEW: destructive migration
- `backend/db/models.py` — Complete rewrite with new models
- `backend/alembic/env.py` — pgvector + TimescaleDB filtering additions

## Metrics
- Tasks completed: 3
- Tests added: 0 (infrastructure changes, no unit tests applicable)
- Lines of code added: ~250 (new migration + models rewrite)
