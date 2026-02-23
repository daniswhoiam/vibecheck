---
phase: 07-tier-1-sentiment-aggregation
plan: 05
subsystem: infra
tags: [apscheduler, fastapi, sqlalchemy, pipeline, sentiment, asyncio]

# Dependency graph
requires:
  - phase: 07-03
    provides: run_score_sentiment and run_aggregate_sentiment async job functions
  - phase: 06-04
    provides: scheduler.py with wrapped_job_execution and setup_jobs

provides:
  - collect→score→aggregate pipeline chain in scheduler per source
  - wrapped_pipeline_execution function with 3 independent try/except steps
  - single SchedulerExecutionLog entry per pipeline run (collection/sentiment/aggregation sub-dicts)

affects: [phase-08, api-health-checks, scheduler-monitoring]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Pipeline chaining: scoring and aggregation run as inline steps of each collection job, not as separate scheduler registrations
    - Fault-isolated steps: each of collect/score/aggregate wrapped in independent try/except — partial success is logged, not lost
    - Health tracking on full pipeline success only: job_last_run updated only when all three steps succeed

key-files:
  created: []
  modified:
    - backend/pipeline/scheduler.py

key-decisions:
  - "Score/aggregate run as pipeline steps inside each collect job, not as separate scheduler jobs — avoids race conditions and keeps one log entry per source"
  - "Collection failure does not prevent scoring/aggregation from running — previously unscored posts from earlier runs are still processed"
  - "wrapped_job_execution() preserved (not deleted) for potential future non-collection job types"

patterns-established:
  - "Pipeline chain pattern: wrapped_pipeline_execution(job_name, collect_func, db_session) — reusable for any collect→score→aggregate source"
  - "Error accumulation pattern: errors list collects failures, log_entry.status = 'failed' if errors else 'success' — single status field covers partial failures"

requirements-completed: [SENT-01]

# Metrics
duration: 1min
completed: 2026-02-23
---

# Phase 07 Plan 05: Scheduler Pipeline Chaining Summary

**APScheduler collect→score→aggregate pipeline chain wired per-source using wrapped_pipeline_execution() with fault-isolated try/except blocks and single audit log entry per run**

## Performance

- **Duration:** 1 min
- **Started:** 2026-02-23T09:49:15Z
- **Completed:** 2026-02-23T09:50:21Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Added `wrapped_pipeline_execution()` that chains collect → score → aggregate in sequence with each step in its own try/except
- Updated `_make_scheduled_job()` to call `wrapped_pipeline_execution` instead of `wrapped_job_execution` — all 4 sources now run the full pipeline
- Imported `run_score_sentiment` and `run_aggregate_sentiment` from pipeline.jobs modules
- Preserved `wrapped_job_execution()` for potential future use
- `metadata_json` on SchedulerExecutionLog now contains collection/sentiment/aggregation sub-dicts per pipeline run

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire collect→score→aggregate pipeline chain into scheduler** - `c56a358` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `backend/pipeline/scheduler.py` - Added wrapped_pipeline_execution(), updated _make_scheduled_job() to use pipeline wrapper, added score/aggregate imports

## Decisions Made
- Scoring and aggregation are NOT separate scheduler jobs — they execute as inline pipeline steps within each collection job's execution context, avoiding race conditions and keeping one log entry per source per cycle
- Collection failure (Step 1) does not prevent scoring/aggregation — `errors` list accumulates failures but all three steps always run; `job_last_run` only updated on zero-error completion
- `wrapped_job_execution()` kept in the file (not deleted) per plan instruction — may be needed for non-collection jobs in future phases

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 07 is now complete: all 5 plans executed
- Pipeline: collect (Phase 6) → score (07-02/03) → aggregate (07-03) → API (07-04) → scheduler chain (07-05)
- SENT-01 requirement fulfilled: scheduler runs full sentiment pipeline per source on each 6-hour cycle

---
*Phase: 07-tier-1-sentiment-aggregation*
*Completed: 2026-02-23*

## Self-Check: PASSED

- backend/pipeline/scheduler.py: FOUND
- 07-05-SUMMARY.md: FOUND
- Commit c56a358: FOUND
