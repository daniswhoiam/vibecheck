---
phase: 02-data-pipeline
plan: 02
subsystem: data-ingestion
tags: [asknews, deduplication, url-hash, retry-logic, tenacity, sqlalchemy, asyncio]

# Dependency graph
requires:
  - phase: 02-01
    provides: AskNewsClient with fetch_news(), normalize_entity_name() service
  - phase: 01-03
    provides: Article model, async database session, CURATED_ENTITIES constants
provides:
  - News polling job with retry logic and per-entity error handling
  - URL hash deduplication (SHA256) for secondary duplicate detection
  - Storage service with entity normalization and batch insertion
  - Migration adding url_hash field to Article model
affects: [02-04-scheduler, 03-aggregation]

# Tech tracking
tech-stack:
  added: [tenacity (retry logic)]
  patterns: [exponential backoff, per-entity error handling, batch deduplication]

key-files:
  created:
    - backend/pipeline/jobs/news_job.py
    - backend/pipeline/services/deduplication_service.py
    - backend/pipeline/services/storage_service.py
    - backend/alembic/versions/435b852d9d02_add_url_hash_to_articles.py
  modified:
    - backend/db/models.py

key-decisions:
  - "Primary deduplication via external_id, secondary via SHA256 URL hash"
  - "Exponential backoff: 3 attempts, 1s-16s wait, retry on TimeoutError/ConnectionError only"
  - "Per-entity error handling: job continues processing remaining entities even if one fails"
  - "Non-curated entities silently filtered during normalization (no exceptions)"
  - "Sentiment label-to-score mapping: positive=0.5, negative=-0.5, neutral=0.0"

patterns-established:
  - "Retry pattern: @retry decorator with tenacity on fetch functions, not on entire job"
  - "Storage pipeline: dedup → normalize → compute hash → batch insert"
  - "Job stats return: structured dict with execution metrics and error tracking"

# Metrics
duration: 3min
completed: 2026-02-05
---

# Phase 2 Plan 2: News Ingestion Job Summary

**News polling job with URL hash deduplication and exponential backoff retry, processing all 10 curated entities independently**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-05T12:41:54Z
- **Completed:** 2026-02-05T12:44:33Z
- **Tasks:** 4
- **Files modified:** 5

## Accomplishments
- URL hash deduplication prevents duplicate articles with different external_ids
- Retry logic with exponential backoff handles transient API failures gracefully
- Per-entity error handling ensures job completes even if one entity fails
- Storage service batch inserts with automatic entity name normalization

## Task Commits

Each task was committed atomically:

1. **Task 1: Add url_hash field to Article model** - `baf8acb` (feat)
2. **Task 2: Create deduplication service** - `6548ca9` (feat)
3. **Task 3: Create storage service for batch article insertion** - `147c36d` (feat)
4. **Task 4: Implement news polling job with retry logic** - `3303a3d` (feat)

## Files Created/Modified
- `backend/db/models.py` - Added url_hash field (String 64, indexed) to Article model
- `backend/alembic/versions/435b852d9d02_add_url_hash_to_articles.py` - Migration for url_hash field
- `backend/pipeline/services/deduplication_service.py` - SHA256 URL hash computation and duplicate checking
- `backend/pipeline/services/storage_service.py` - Batch article insertion with normalization and deduplication
- `backend/pipeline/jobs/news_job.py` - News polling job with tenacity retry and error handling

## Decisions Made

**1. Dual deduplication strategy (external_id + url_hash)**
- External_id is primary check (AskNews article identifier)
- URL hash is secondary check for articles with different external_ids but same URL
- Prevents duplicate content from accumulating over time

**2. Exponential backoff parameters**
- 3 retry attempts with 1s → 2s → 4s wait times (max 16s)
- Retry only on TimeoutError and ConnectionError (transient network issues)
- Other exceptions propagate immediately (authentication, validation, etc.)

**3. Per-entity error handling in job**
- Each entity processed independently in try/except block
- Failure in one entity doesn't stop processing of remaining entities
- Errors tracked in stats dict for observability

**4. Non-curated entity filtering**
- Storage service silently skips articles for non-curated entities
- normalize_entity_name() returns None for unrecognized entities
- No exceptions raised - expected behavior for filtering

**5. Sentiment transformation**
- AskNews label strings mapped to numeric scores: positive=0.5, negative=-0.5, neutral=0.0
- Numeric sentiment values passed through as-is
- Fallback to None if sentiment format unrecognized

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Alembic database version out of sync**
- **Found during:** Task 1 (migration generation)
- **Issue:** Database tables existed but Alembic version table was empty, causing "Target database is not up to date" error
- **Fix:** Ran `alembic stamp head` to mark existing migration as applied before generating new migration
- **Files modified:** N/A (database metadata only)
- **Verification:** New migration generated successfully after stamping
- **Committed in:** baf8acb (Task 1 commit)

**2. [Rule 2 - Missing Critical] Datetime parsing with timezone handling**
- **Found during:** Task 4 (storage transformation)
- **Issue:** AskNews returns ISO 8601 strings with 'Z' suffix, needs conversion to datetime with timezone
- **Fix:** Added datetime.fromisoformat() with .replace('Z', '+00:00') to handle UTC timezone
- **Files modified:** backend/pipeline/jobs/news_job.py
- **Verification:** datetime objects correctly parsed with UTC timezone
- **Committed in:** 3303a3d (Task 4 commit)

**3. [Rule 2 - Missing Critical] Fallback datetime for parse failures**
- **Found during:** Task 4 (storage transformation)
- **Issue:** If published_at parsing fails (malformed date, missing field), would crash job
- **Fix:** Added try/except with fallback to datetime.utcnow() for resilience
- **Files modified:** backend/pipeline/jobs/news_job.py
- **Verification:** Job continues processing even with malformed dates
- **Committed in:** 3303a3d (Task 4 commit)

---

**Total deviations:** 3 auto-fixed (1 blocking, 2 missing critical)
**Impact on plan:** All auto-fixes necessary for correctness and resilience. No scope creep. Database sync was infrastructure fix, datetime handling prevents job crashes.

## Issues Encountered

None - plan executed smoothly after Alembic sync fix.

## User Setup Required

**ASKNEWS_API_KEY environment variable must be set before testing.**

The AskNewsClient will raise ValueError if ASKNEWS_API_KEY is not found in environment. User must:
1. Obtain API key from AskNews dashboard
2. Add to backend/.env: `ASKNEWS_API_KEY=your_key_here`
3. Restart Docker containers if running

**Note:** This was documented in Phase 2 STATE.md blockers and is expected setup.

## Next Phase Readiness

**Ready for:**
- Plan 02-03 (Stories job) - Uses same retry and storage patterns
- Plan 02-04 (Scheduler) - poll_news_job() ready to be scheduled at 15-min frequency

**Blockers:**
- Entity table must be seeded with CURATED_ENTITIES before job can store articles (entity normalization returns None if entity not in database)
- ASKNEWS_API_KEY must be configured before testing

**Technical notes:**
- Job returns structured stats dict suitable for scheduler logging
- Per-entity error handling ensures partial success is valuable
- URL hash deduplication prevents long-term accumulation of duplicates

---
*Phase: 02-data-pipeline*
*Completed: 2026-02-05*
