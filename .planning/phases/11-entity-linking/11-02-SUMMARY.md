---
phase: 11-entity-linking
plan: 02
subsystem: pipeline
tags: [backfill, scheduler, apscheduler, sqlalchemy, batch-processing, idempotent]

# Dependency graph
requires:
  - phase: 11-01
    provides: MentionExtractor class + extract_and_save_mentions() from mention_service.py
  - phase: 05-schema-migrations
    provides: PostEntityMention model with UniqueConstraint on (post_id, entity_id)
  - phase: 06-04
    provides: scheduler.py with wrapped_job_execution() and setup_jobs() pattern
provides:
  - run_backfill_entity_mentions() job function in extract_entity_mentions.py
  - Backfill registered as one-time startup job in scheduler (trigger="date", +5 min)
affects:
  - 11-03 (pipeline integration can now assume backfill has run on startup)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - APScheduler trigger="date" for one-time startup jobs (DateTrigger fires once)
    - NOT EXISTS subquery for idempotent batch processing of unlinked posts
    - Offset-based pagination with NOT EXISTS for large-table backfills
    - wrapped_job_execution() reused for one-time jobs as well as recurring ones

key-files:
  created:
    - backend/pipeline/jobs/extract_entity_mentions.py
  modified:
    - backend/pipeline/scheduler.py

key-decisions:
  - "NOT EXISTS subquery used (not simpler all-posts pagination) — correct because posts with no entity matches are not inserted into PostEntityMention and won't re-appear; offset pagination safe for single backfill run"
  - "trigger='date' with run_date=now+5min chosen for one-time startup execution — APScheduler DateTrigger fires exactly once and does not repeat"
  - "Backfill NOT added to get_job_health() job_configs — it is a one-time job not subject to recurring overdue monitoring"
  - "wrapped_job_execution() reused for backfill (not wrapped_pipeline_execution) — backfill is standalone, not chained with score/aggregate steps"

# Metrics
duration: 1min
completed: 2026-02-23
---

# Phase 11 Plan 02: Entity Mentions Backfill Job Summary

**Batched backfill job for existing posts using NOT EXISTS subquery + APScheduler one-time DateTrigger registered 5 minutes after startup, audit-logged via wrapped_job_execution()**

## Performance

- **Duration:** ~1 min
- **Started:** 2026-02-23T14:58:16Z
- **Completed:** 2026-02-23T14:59:29Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- `run_backfill_entity_mentions()`: batched (BACKFILL_BATCH_SIZE=1000), NOT EXISTS subquery excludes already-processed posts, stats dict `{posts_scanned, mentions_added, posts_with_no_mentions, errors}`
- `scheduler.py`: imports `run_backfill_entity_mentions`, registers as `trigger="date"` one-time job firing 5 min after startup
- Existing 4 collection jobs and `get_job_health()` left unchanged
- All syntax validation passes; implementation ready for Docker environment testing

## Task Commits

Each task was committed atomically:

1. **Task 1: Create backfill job for existing posts** - `73ce439` (feat)
2. **Task 2: Register backfill as startup job in scheduler** - `0b55c92` (feat)

## Files Created/Modified
- `backend/pipeline/jobs/extract_entity_mentions.py` - `run_backfill_entity_mentions()` with batched NOT EXISTS processing
- `backend/pipeline/scheduler.py` - Import + one-time DateTrigger registration added after existing 4-job loop

## Decisions Made
- NOT EXISTS subquery (not simpler all-posts scan): posts with no entity matches are never inserted into `PostEntityMention`, so they appear exactly once in the NOT EXISTS pass — correct behavior for a single backfill run
- `trigger="date"` with `run_date=now+5min`: APScheduler DateTrigger fires once, does not repeat — ideal for startup one-time backfill
- Backfill excluded from `get_job_health()`: one-time jobs don't have "overdue" semantics; monitoring only applies to recurring collection jobs
- `wrapped_job_execution()` (not `wrapped_pipeline_execution()`): backfill is standalone — it populates mentions but does not chain into score/aggregate; those run in their own collect cycles

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered
- Docker containers not available in local env (asyncpg not installed locally, same issue as Phase 11 Plan 01). Python syntax verified with `ast.parse()`. Implementation will be validated in Docker on next scheduled run.

## User Setup Required
None — no external service configuration required.

## Next Phase Readiness
- `extract_entity_mentions.py` is importable and ready for Phase 11 Plan 03 (pipeline integration)
- Backfill will populate `post_entity_mentions` on first startup, enabling aggregate_sentiment and extract_aspects to produce non-empty results
- All existing 4 collection jobs verified unchanged

## Self-Check: PASSED

- FOUND: `backend/pipeline/jobs/extract_entity_mentions.py`
- FOUND: `backend/pipeline/scheduler.py` (modified)
- FOUND commit: `73ce439` (feat Task 1)
- FOUND commit: `0b55c92` (feat Task 2)

---
*Phase: 11-entity-linking*
*Completed: 2026-02-23*
