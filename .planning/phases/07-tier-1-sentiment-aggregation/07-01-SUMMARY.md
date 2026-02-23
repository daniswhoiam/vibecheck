---
phase: 07-tier-1-sentiment-aggregation
plan: 01
subsystem: database
tags: [sqlalchemy, alembic, postgresql, jsonb, timescaledb]

# Dependency graph
requires:
  - phase: 06-data-collection
    provides: Post model, posts hypertable, entity schema via migration 006_reset_schema
provides:
  - Post ORM model with nullable sentiment_label and sentiment_score columns
  - SentimentRollup ORM model and sentiment_rollup table with JSONB source_breakdown
  - Alembic migration chain 006 -> 007 -> 008
  - Clean db/__init__.py without v1.0 dead imports
affects: [07-02-PLAN.md, 07-03-PLAN.md, 07-04-PLAN.md, 07-05-PLAN.md]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "TIMESTAMP(timezone=True) for rollup_date instead of Date type — avoids timezone edge cases in aggregation queries"
    - "SQLAlchemy JSON type maps to JSONB on PostgreSQL — no explicit JSONB import needed"
    - "UniqueConstraint + Index on (entity_id, rollup_date) for upsert-friendly daily rollup pattern"

key-files:
  created:
    - backend/alembic/versions/007_add_sentiment_columns_to_posts.py
    - backend/alembic/versions/008_create_sentiment_rollup_table.py
  modified:
    - backend/db/models.py
    - backend/db/__init__.py

key-decisions:
  - "Store rollup_date as TIMESTAMP(timezone=True) (midnight UTC) not SQLAlchemy Date — consistent with rest of schema, avoids TZ edge cases"
  - "Use SQLAlchemy JSON type for source_breakdown — maps to JSONB on PostgreSQL automatically without separate import"
  - "sentiment_label indexed for efficient unscored-post queries (WHERE sentiment_label IS NULL)"

patterns-established:
  - "Sentiment columns nullable — existing posts remain valid before scoring job runs"
  - "SentimentRollup unique constraint on (entity_id, rollup_date) enables INSERT ... ON CONFLICT upsert pattern in aggregation job"

requirements-completed: [SENT-01]

# Metrics
duration: 2min
completed: 2026-02-23
---

# Phase 7 Plan 01: Schema Foundation Summary

**Nullable sentiment_label/sentiment_score added to Post, SentimentRollup table created with JSONB source_breakdown, Alembic migration chain 006->007->008, dead v1.0 imports removed from db/__init__.py**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-02-23T09:40:37Z
- **Completed:** 2026-02-23T09:42:03Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Added `sentiment_label` (VARCHAR 20, nullable, indexed) and `sentiment_score` (Float, nullable) to Post ORM model — enables zero-shot classifier output storage without breaking existing rows
- Created `SentimentRollup` ORM class with `entity_id` FK, `rollup_date` (TIMESTAMP TZ), `sentiment_mean`, `post_count`, `source_breakdown` (JSON/JSONB), unique constraint on (entity_id, rollup_date)
- Added `Entity.sentiment_rollups` relationship with cascade delete-orphan; wrote migrations 007 and 008 with clean upgrade/downgrade paths; cleaned `db/__init__.py` of dead `Article` and `SentimentTimeseries` imports

## Task Commits

Each task was committed atomically:

1. **Task 1: Add sentiment columns to Post model and create SentimentRollup ORM model** - `47b6be5` (feat)
2. **Task 2: Write Alembic migrations 007 + 008 and fix db/__init__.py** - `faaf618` (feat)

## Files Created/Modified

- `backend/db/models.py` - Added sentiment_label + sentiment_score to Post; new SentimentRollup class; Entity.sentiment_rollups relationship
- `backend/db/__init__.py` - Replaced dead Article/SentimentTimeseries imports with current model exports including SentimentRollup
- `backend/alembic/versions/007_add_sentiment_columns_to_posts.py` - Migration: adds sentiment columns + index to posts table
- `backend/alembic/versions/008_create_sentiment_rollup_table.py` - Migration: creates sentiment_rollup table with JSONB, FK, unique constraint

## Decisions Made

- `rollup_date` stored as `TIMESTAMP(timezone=True)` (midnight UTC) rather than SQLAlchemy `Date` type — maintains consistency with rest of schema and avoids timezone edge cases during aggregation queries
- `source_breakdown` uses SQLAlchemy `JSON` type — automatically maps to PostgreSQL `JSONB` without needing explicit `JSONB` import
- Index on `sentiment_label` chosen to optimize "find unscored posts" queries (`WHERE sentiment_label IS NULL`) used by the scoring job in Plan 03

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Schema foundation complete — Posts can store sentiment scores, SentimentRollup table is ready for aggregation writes
- Plan 02 (zero-shot classifier) and Plan 03 (scoring + aggregation jobs) depend directly on these columns and table
- Migration chain is valid: 006_reset_schema -> 007_add_sentiment_columns_to_posts -> 008_create_sentiment_rollup_table
- db/__init__.py now imports SentimentRollup, unblocking any code that does `from db import SentimentRollup`

---
*Phase: 07-tier-1-sentiment-aggregation*
*Completed: 2026-02-23*
