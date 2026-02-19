---
phase: 02-data-pipeline
plan: 03
subsystem: data-ingestion
tags: [asknews, sentiment-analysis, reddit, time-series, asyncio, tenacity, sqlalchemy]

# Dependency graph
requires:
  - phase: 02-01
    provides: AskNewsClient with fetch_stories() method and entity normalization
  - phase: 01-02
    provides: SentimentTimeseries model and async database session
provides:
  - Story polling job with retry logic for all 10 curated entities
  - Sentiment time-series storage with Reddit data extraction
  - Graceful handling of missing Reddit data (common for many stories)
affects: [02-04-scheduler, 03-frontend-integration]

# Tech tracking
tech-stack:
  added: [tenacity (retry with exponential backoff)]
  patterns: [Job execution with per-entity error recovery, PostgreSQL INSERT ON CONFLICT for upserts, Structured sentiment extraction from API responses]

key-files:
  created:
    - backend/pipeline/jobs/stories_job.py
    - backend/pipeline/services/sentiment_service.py
    - backend/pipeline/jobs/__init__.py
  modified:
    - backend/db/models.py

key-decisions:
  - "Use PostgreSQL INSERT ... ON CONFLICT DO NOTHING for time-series deduplication instead of SELECT-then-INSERT pattern"
  - "Extract Reddit sentiment as separate field rather than blending with overall sentiment"
  - "Continue job execution on per-entity failures to maximize data collection rather than fail-fast"
  - "Log first story response at INFO level for API response validation without overwhelming logs"
  - "Retry only on transient network errors (TimeoutError, ConnectionError) not API validation errors"

patterns-established:
  - "Job pattern: async poll function accepts db_session, returns execution stats dict with success/failure metrics"
  - "Retry pattern: @retry decorator on fetch function, 3 attempts with exponential backoff (multiplier=1, min=2s, max=10s)"
  - "Sentiment extraction: Separate extract function returns structured dict with timeseries/reddit data, gracefully handles missing fields"

# Metrics
duration: 2min
completed: 2026-02-05
---

# Phase 2 Plan 3: Story Ingestion with Reddit Sentiment Summary

**Story polling job with hourly sentiment time-series aggregates and Reddit-specific community opinion tracking**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-05T12:42:15Z
- **Completed:** 2026-02-05T12:44:08Z
- **Tasks:** 3
- **Files modified:** 5 (2 created, 1 modified, 1 migration, 1 init)

## Accomplishments
- SentimentTimeseries model extended with reddit_sentiment and reddit_thread_count fields for community opinion tracking
- Sentiment service extracts time-series aggregates and Reddit data from AskNews story responses with graceful missing-data handling
- Story polling job fetches clusters for all 10 entities with retry logic, continues on per-entity failures to maximize data collection
- PostgreSQL upsert pattern prevents duplicate time-series entries efficiently

## Task Commits

Each task was committed atomically:

1. **Task 1: Add reddit_sentiment field to SentimentTimeseries model** - `c1582f5` (feat)
2. **Task 2: Create sentiment time-series storage service** - `30ec987` (feat)
3. **Task 3: Implement story polling job with Reddit sentiment extraction** - `1bd26e2` (feat)

**Note:** Plan 02-03 executed in parallel with plan 02-02 (both modifying backend/db/models.py). No conflicts occurred as each modified separate models.

## Files Created/Modified
- `backend/db/models.py` - Added reddit_sentiment and reddit_thread_count fields to SentimentTimeseries
- `backend/alembic/versions/6d279f8e2869_add_reddit_sentiment_to_sentiment_.py` - Database migration for new fields
- `backend/pipeline/services/sentiment_service.py` - store_sentiment_timeseries() with PostgreSQL upsert, extract_story_sentiment() parses AskNews responses
- `backend/pipeline/jobs/stories_job.py` - poll_stories_job() with per-entity error recovery, fetch_stories_from_asknews_with_retry() with exponential backoff
- `backend/pipeline/jobs/__init__.py` - Jobs package initialization

## Decisions Made

**1. PostgreSQL INSERT ... ON CONFLICT for deduplication**
- Rationale: More efficient than SELECT-then-INSERT pattern, atomic operation prevents race conditions
- Trade-off: Requires unique constraint on (entity_id, timestamp, period) - to be added in future migration

**2. Separate reddit_sentiment field**
- Rationale: Preserve both overall sentiment and Reddit-specific sentiment for comparison, enables frontend to show community vs. media divergence
- Alternative considered: Blend into single sentiment score - rejected as loses valuable signal about community opinion

**3. Continue on per-entity failures**
- Rationale: Maximize data collection even if some entities fail, better to have partial data than no data
- Pattern: Log errors, increment failure counter, continue loop

**4. Retry only transient network errors**
- Rationale: TimeoutError/ConnectionError indicate network issues (retry likely to succeed), API validation errors unlikely to resolve with retry
- Implementation: tenacity @retry decorator with retry_if_exception_type

**5. Log first story response only**
- Rationale: Validate AskNews API response structure without overwhelming logs with every story
- Pattern: first_story_logged boolean flag prevents duplicate logging

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - all tasks completed successfully without unexpected obstacles.

## User Setup Required

**ASKNEWS_API_KEY environment variable must be set before testing.**

See Phase 2 integration documentation for:
- Where to obtain AskNews API key
- Adding to .env or docker-compose environment
- Entity seeding script to populate Entity table

## Next Phase Readiness

**Ready for Plan 02-04 (scheduler implementation):**
- poll_stories_job() function complete and ready for APScheduler integration
- Returns execution stats for monitoring and health checks
- Per-entity error recovery ensures partial data collection on failures

**Blockers/Concerns:**
- Entity seeding script needed before first job execution (Entity table must contain curated entities)
- ASKNEWS_API_KEY environment variable required
- Real AskNews /stories API response structure needs validation via first job execution
- Unique constraint on sentiment_timeseries(entity_id, timestamp, period) recommended for true upsert behavior

**Database state:**
- Migration 6d279f8e2869 applied successfully
- reddit_sentiment and reddit_thread_count columns exist in sentiment_timeseries table

---
*Phase: 02-data-pipeline*
*Completed: 2026-02-05*
