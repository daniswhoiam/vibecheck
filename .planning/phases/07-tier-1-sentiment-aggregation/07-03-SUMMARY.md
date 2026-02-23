---
phase: 07-tier-1-sentiment-aggregation
plan: "03"
subsystem: api
tags: [sqlalchemy, asyncpg, postgresql, jsonb, gliclass, sentiment, pipeline, apscheduler]

# Dependency graph
requires:
  - phase: 07-tier-1-sentiment-aggregation
    provides: SentimentClassifier.classify() in sentiment_service.py (Plan 02)
  - phase: 07-tier-1-sentiment-aggregation
    provides: Post.sentiment_label/sentiment_score columns and SentimentRollup table (Plan 01)

provides:
  - run_score_sentiment(session) async job in backend/pipeline/jobs/score_sentiment.py
  - run_aggregate_sentiment(session) async job in backend/pipeline/jobs/aggregate_sentiment.py

affects:
  - 07-05-scheduler-chaining (plugs score and aggregate jobs into the collect->score->aggregate pipeline)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Incremental scoring pattern — WHERE sentiment_label IS NULL prevents rescoring previously classified posts
    - Sub-batch commit pattern — classify all at once (model loaded once), write DB in SCORE_BATCH_SIZE chunks
    - Single-query aggregation — one SQL round-trip aggregates all entities via GROUP BY entity_id
    - jsonb_object_agg for per-source breakdown — server-side JSONB construction avoids application-side grouping
    - Signed sentiment mean — maps label to [-1,1] range (Positive=+1.0, Negative=-1.0, Neutral=0.0) in SQL
    - Per-entity error isolation — upsert failures per entity are caught independently; one failure doesn't abort others

key-files:
  created:
    - backend/pipeline/jobs/score_sentiment.py
    - backend/pipeline/jobs/aggregate_sentiment.py
  modified: []

key-decisions:
  - "Model loaded once for the full unscored post set, not per sub-batch — SentimentClassifier lifecycle is load-classify-unload in a single classify() call"
  - "DB writes committed in SCORE_BATCH_SIZE=8 sub-batches to limit transaction size — classification is decoupled from write batching"
  - "Sentiment mean uses signed label mapping (not confidence score) — produces API-friendly [-1,1] range from Positive/Negative/Neutral labels"
  - "Single aggregation query for all entities via GROUP BY entity_id — one DB round-trip regardless of entity count"
  - "jsonb_object_agg in SQL (not Python grouping) for source_breakdown — more efficient, atomic with the aggregation"
  - "rollup_date stored as midnight UTC datetime (not date type) — consistent with Phase 01 schema decision"

patterns-established:
  - "Incremental processing: SELECT WHERE sentinel_column IS NULL, ORDER BY id for stable iteration"
  - "Signed sentiment mean: CASE sentiment_label WHEN 'Positive' THEN 1.0 WHEN 'Negative' THEN -1.0 ELSE 0.0 END"
  - "Today-only UTC window: DATE(published_at AT TIME ZONE 'UTC') = :today"
  - "Idempotent upsert: pg_insert().on_conflict_do_update(index_elements=[...]) — safe to rerun multiple times per day"

requirements-completed: [SENT-01]

# Metrics
duration: 2min
completed: 2026-02-23
---

# Phase 7 Plan 03: Pipeline Job Functions Summary

**Incremental score_sentiment job (GliClass IS NULL filter + sub-batch commits) and idempotent aggregate_sentiment job (single-query jsonb_object_agg upsert into SentimentRollup) for daily entity sentiment rollups**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-23T09:44:42Z
- **Completed:** 2026-02-23T09:46:22Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Implemented `run_score_sentiment(session)` with incremental IS NULL filter, single model load for full post set, and sub-batch DB commits
- Implemented `run_aggregate_sentiment(session)` with single SQL aggregation query using `jsonb_object_agg`, signed sentiment mean mapping, and idempotent `on_conflict_do_update` upsert
- Both jobs follow the `{scored/rollups_updated, errors}` stats dict pattern established in Phase 6 for `wrapped_job_execution()` audit logging

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement run_score_sentiment job** - `54dc8bd` (feat)
2. **Task 2: Implement run_aggregate_sentiment job** - `e09551f` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified
- `backend/pipeline/jobs/score_sentiment.py` - Incremental sentiment scoring job: queries NULL posts, calls SentimentClassifier, writes back label+score in sub-batch commits
- `backend/pipeline/jobs/aggregate_sentiment.py` - Daily rollup aggregation job: single SQL query with jsonb_object_agg, upserts SentimentRollup via on_conflict_do_update

## Decisions Made
- Model loaded once for all unscored posts, not per sub-batch — the SentimentClassifier lifecycle is atomic (load-classify-unload) within a single `classify()` call, so splitting across batches would cause repeated model loads
- Sub-batch commits for DB writes (SCORE_BATCH_SIZE=8) are separate from classification batching — keeps individual transactions small while maintaining single model load
- Signed sentiment mean (-1 to +1) rather than raw confidence score — `sentiment_score` (0-1 confidence) is preserved in the posts table for Tier 2 routing; the rollup uses the signed convention for API-friendly display
- `jsonb_object_agg` in SQL rather than Python-side grouping — server-side construction is atomic with the aggregation and avoids a second pass over results

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `run_score_sentiment` and `run_aggregate_sentiment` are ready for Plan 05 (scheduler chaining) to wire into the collect->score->aggregate pipeline
- Both jobs accept `AsyncSession` and return stats dicts compatible with `wrapped_job_execution()`
- Idempotent upsert in `run_aggregate_sentiment` means daily reruns are safe — suitable for APScheduler's `replace_existing=True` pattern

---
*Phase: 07-tier-1-sentiment-aggregation*
*Completed: 2026-02-23*
