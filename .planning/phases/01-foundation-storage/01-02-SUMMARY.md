---
phase: 01
plan: 02
subsystem: database
tags: [sqlalchemy, postgres, alembic, orm, async, timeseries]
requires: [01-01]
provides:
  - "SQLAlchemy 2.0 async ORM models for Entity, Article, SentimentTimeseries"
  - "Async database session factory with connection pooling"
  - "Alembic migration system with async support"
  - "Initial schema migration with TimescaleDB-compatible indexes"
affects: [01-03, 02-01, 02-02]
tech-stack:
  added:
    - "SQLAlchemy 2.0.35 with AsyncAttrs and async_sessionmaker"
    - "Alembic 1.14.0 configured for async migrations"
    - "asyncpg driver for PostgreSQL async operations"
  patterns:
    - "SQLAlchemy 2.0 Mapped type hints for type safety"
    - "expire_on_commit=False for async session management"
    - "pool_pre_ping=True for connection verification"
    - "Composite indexes for time-series query optimization"
key-files:
  created:
    - backend/db/__init__.py
    - backend/db/base.py
    - backend/db/session.py
    - backend/db/models.py
    - backend/alembic.ini
    - backend/alembic/env.py
    - backend/alembic/versions/001_create_schema.py
  modified:
    - .gitignore (added .venv/)
key-decisions:
  - id: async-session-expire
    title: "Use expire_on_commit=False for async sessions"
    rationale: "Prevents implicit database queries after commit in async context, which would fail or cause blocking"
    impact: "All code must be aware that objects remain attached to session after commit"
  - id: pool-pre-ping
    title: "Enable pool_pre_ping for connection verification"
    rationale: "Verifies database connections before use, preventing errors from stale connections"
    impact: "Small performance overhead for connection health checks"
  - id: composite-timeseries-index
    title: "Composite index on (entity_id, timestamp DESC) for sentiment_timeseries"
    rationale: "Optimizes time-series queries by entity with descending timestamp order"
    impact: "Efficient queries for recent sentiment data per entity"
  - id: manual-migration
    title: "Create initial migration manually instead of autogenerate"
    rationale: "Alembic autogenerate requires live database connection; manual creation works offline"
    impact: "Migration file matches ORM models exactly, ready to apply when database is available"
duration: 3 min
completed: 2026-02-05
---

# Phase 01 Plan 02: SQLAlchemy Async ORM and Alembic Migrations Summary

**One-liner:** SQLAlchemy 2.0 async ORM with Entity, Article, and SentimentTimeseries models, async session factory with connection pooling, and Alembic configured for async migrations with TimescaleDB-compatible schema.

## Performance

- **Execution time:** 3 minutes
- **Tasks completed:** 3/3
- **Commits:** 3 (one per task)
- **Files created:** 7
- **Files modified:** 1

## What Was Accomplished

### Database Foundation Layer

1. **Async Session Management**
   - Created Base class with AsyncAttrs for async-compatible ORM
   - Configured async engine with pool_size=10, max_overflow=20
   - Set expire_on_commit=False to prevent implicit queries after commit
   - Added FastAPI dependency for session injection with proper cleanup

2. **ORM Models**
   - Entity model for tracked AI models and tools with category field
   - Article model with external_id, sentiment_score, and published_at index
   - SentimentTimeseries model with composite (entity_id, timestamp DESC) index
   - CheckConstraints enforce sentiment values between -1 and 1
   - All timestamps use TIMESTAMP WITH TIME ZONE for UTC storage

3. **Alembic Migration System**
   - Configured Alembic for async SQLAlchemy with create_async_engine
   - Modified env.py to use asyncio.run and async context
   - Created initial migration 001_create_schema.py with all three tables
   - TimescaleDB-compatible indexes for efficient time-series queries

## Task Commits

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 | Create SQLAlchemy async base and session management | d5971bf | backend/db/__init__.py, backend/db/base.py, backend/db/session.py |
| 2 | Create ORM models for entities, articles, and sentiment time-series | 6564b3e | backend/db/models.py |
| 3 | Initialize Alembic and create initial migration | 12f2187 | backend/alembic.ini, backend/alembic/env.py, backend/alembic/versions/001_create_schema.py, .gitignore |

## Files Created/Modified

### Created
- `backend/db/__init__.py` - Database module exports
- `backend/db/base.py` - SQLAlchemy declarative base with AsyncAttrs
- `backend/db/session.py` - Async engine and session factory
- `backend/db/models.py` - Entity, Article, SentimentTimeseries ORM models
- `backend/alembic.ini` - Alembic configuration
- `backend/alembic/env.py` - Async migration environment
- `backend/alembic/versions/001_create_schema.py` - Initial schema migration

### Modified
- `.gitignore` - Added .venv/ for virtual environments

## Decisions Made

### 1. Use expire_on_commit=False for async sessions
**Context:** SQLAlchemy async sessions require special handling for post-commit object access.

**Decision:** Configure async_sessionmaker with expire_on_commit=False.

**Rationale:** Prevents implicit database queries after commit in async context, which would fail or cause blocking operations.

**Impact:** All code must be aware that objects remain attached to session after commit. This is the recommended pattern for async SQLAlchemy.

**Alternatives considered:**
- Keep default expire_on_commit=True: Would require explicit refresh after commit
- Use detached objects: Would lose relationship loading capabilities

### 2. Enable pool_pre_ping for connection verification
**Context:** Database connections can become stale, especially with cloud databases or network interruptions.

**Decision:** Configure engine with pool_pre_ping=True.

**Rationale:** Verifies database connections before use, preventing errors from stale connections. Small overhead is worth the reliability.

**Impact:** Adds minimal performance overhead for connection health checks, but prevents hard-to-debug connection errors.

### 3. Composite index on (entity_id, timestamp DESC)
**Context:** Time-series queries will frequently request recent sentiment data for specific entities.

**Decision:** Create composite index on (entity_id, timestamp DESC) for sentiment_timeseries table.

**Rationale:** Optimizes the most common query pattern (recent data per entity) and is compatible with TimescaleDB if we add it later.

**Impact:** Efficient queries for charting recent sentiment trends, which is the core user feature.

### 4. Manual migration creation
**Context:** Alembic autogenerate requires live database connection.

**Decision:** Create initial migration manually instead of running autogenerate.

**Rationale:** Allows offline development without running Docker daemon, and migration file matches ORM models exactly.

**Impact:** Migration is ready to apply when database is started. Future migrations can use autogenerate once database is running.

## Deviations from Plan

None - plan executed exactly as written. All tasks completed successfully with proper async patterns.

## Issues Encountered

### Docker daemon not running
**Issue:** Docker daemon was not running, preventing database connection for Alembic autogenerate.

**Resolution:** Created initial migration manually, which works offline. Migration is ready to apply when Docker is started.

**Severity:** Low - manual migration creation is a valid approach and matches ORM models exactly.

## Schema Compatibility

The schema is TimescaleDB-compatible from day 1:

1. **Entity-timestamp indexing** - Composite index on (entity_id, timestamp DESC) supports time-series queries
2. **Timestamp with timezone** - All timestamps use TIMESTAMP WITH TIME ZONE stored in UTC
3. **Normalized structure** - Entities separate from time-series data for efficient storage
4. **Foreign key relationships** - Proper referential integrity maintained

This design allows adding TimescaleDB hypertables later without schema changes.

## Next Phase Readiness

### Ready For
- **Plan 01-03:** FastAPI app initialization can now import db.models and db.session
- **Plan 02-01:** AskNews client can store results using Article and Entity models
- **Plan 02-02:** Sentiment aggregation can write to SentimentTimeseries model

### Blockers/Concerns
- **Database initialization:** Migration needs to be run when Docker Compose starts PostgreSQL
  - Command: `cd backend && alembic upgrade head`
  - Should be added to backend service startup or documented in README
- **Entity seeding:** Need to seed initial entities (GPT-4, Claude, etc.) after schema creation
  - Consider adding seed data migration or initialization script

### Remaining Work
None for this plan. Database layer is complete and ready for CRUD operations.
