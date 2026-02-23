# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-19)

**Core value:** Users can see how sentiment around AI models and tools has changed over time, with clear time-series data powered by real news and Reddit community opinion.
**Current focus:** v2.0 Free Pipeline — replacing AskNews with free data sources + own sentiment pipeline

## Current Position

Phase: 07-tier-1-sentiment-aggregation (Plan 5 of 5)
Plan: 07-05
Status: Complete
Last activity: 2026-02-23 — Completed 07-05 (Scheduler pipeline chain: collect→score→aggregate per source)

## Accumulated Context

### Decisions

All v1.0 decisions logged in PROJECT.md Key Decisions table with outcomes.

**06-01 (2026-02-23):**
- Context words for ambiguous names use word-boundary regex (not substring) — prevents "ai" matching inside "painted", "trained", etc.
- Filter API is module-level is_relevant() function, not a FilterService class — simpler for collectors
- MAX_BODY_CHARS=50_000 (50K chars) covers ~99th percentile of Dev.to articles
- Hash input: url > body > empty string — URL is canonical dedup key across mirrors/reposts
- [Phase 06-02]: HN top-level comment filter: parent_id == story_id check is direct and unambiguous
- [Phase 06-02]: Discourse two-pass filter (title then body) conserves API calls on rate-sensitive forums
- [Phase 06-02]: HN 1000-hit cap logs WARNING (not error) — callers use weekly time windows for backfill

**06-03 (2026-02-23):**
- asyncpraw context manager (async with ... as reddit) mandatory — prevents aiohttp connector leak on session close
- Tool-specific and broad subreddits both call is_relevant() identically — distinction is structural, not logic-level
- Dev.to seen_ids dedup before body fetch — saves API calls for articles appearing under multiple tags
- BODY_FETCH_CONCURRENCY=5 caps concurrent /api/articles/{id} requests to avoid 429 without API key
- [Phase 06-04]: AsyncSessionLocal used directly in scheduler (not get_session generator) — cleaner for APScheduler context
- [Phase 06-04]: Job factory closure _make_scheduled_job creates fresh coroutine per trigger; each run gets its own AsyncSession
- [Phase 06-04]: Stagger: HN +0m, Reddit +30m, Discourse +60m, Dev.to +90m to smooth resource usage across 6h cycle

**07-01 (2026-02-23):**
- rollup_date stored as TIMESTAMP(timezone=True) (midnight UTC) not SQLAlchemy Date — consistent with schema, avoids TZ edge cases in aggregation queries
- SQLAlchemy JSON type used for source_breakdown — maps to PostgreSQL JSONB automatically without explicit import
- sentiment_label indexed for efficient unscored-post queries (WHERE sentiment_label IS NULL)

**07-02 (2026-02-23):**
- device=-1 (CPU) set explicitly in HuggingFace pipeline — Render Standard tier has no GPU, avoids CUDA warnings
- On-demand model load/unload per classify() call — 3s load time tradeoff for minimal baseline memory between 6h cycles
- asyncio.to_thread() wraps both model load and inference — HuggingFace pipeline() is fully synchronous
- Labels Positive/Negative/Neutral (capitalized) matching CONTEXT.md user decision
- MAX_CHARS=2000 truncation — ~512 tokens for typical English developer text
- DEFAULT_BATCH_SIZE=8 conservative start for 1.5GB memory budget

**07-03 (2026-02-23):**
- Model loaded once for all unscored posts, not per sub-batch — SentimentClassifier lifecycle is atomic (load-classify-unload) in single classify() call
- Sub-batch commits for DB writes (SCORE_BATCH_SIZE=8) decoupled from classification — keeps individual transactions small
- Signed sentiment mean (-1 to +1) in rollup — Positive=+1.0, Negative=-1.0, Neutral=0.0 for API-friendly display; raw confidence preserved in posts.sentiment_score
- jsonb_object_agg in SQL (not Python-side grouping) for source_breakdown — atomic with aggregation, single DB round-trip
- Idempotent upsert via on_conflict_do_update on (entity_id, rollup_date) — safe to rerun multiple times per day

**07-04 (2026-02-23):**
- period param removed from GET /entities/{id}/sentiment — Phase 7 is daily-only per prior user decision
- SentimentTimeseriesResponse class name kept (describes API response shape, not DB model)
- source_breakdown typed Optional[Dict[str, Any]] matching SentimentRollup.source_breakdown JSON column

**07-05 (2026-02-23):**
- Score/aggregate run as pipeline steps inside each collect job, not as separate scheduler jobs — avoids race conditions and keeps one log entry per source
- Collection failure does not prevent scoring/aggregation from running — errors list accumulates, but all three steps always attempt
- wrapped_job_execution() preserved (not deleted) for potential future non-collection job types

### Known Tech Debt

- Unique constraint on `sentiment_timeseries(entity_id, timestamp, period)` not yet added
- Entity variation dictionary may need tuning with more real API data
- AskNews SDK and `httpx` pin to be removed in v2.0

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 001 | Frontend-backend alignment analysis | 2026-02-05 | a30ff68 | 001-frontend-backend-alignment |
| 002 | Frontend-backend integration Phase 1 | 2026-02-05 | 3a8f0a4 | 002-frontend-backend-integration-phase1 |
| 003 | Frontend-backend integration Phase 2 | 2026-02-05 | a71be9d | 003-frontend-backend-integration-phase2 |

## Session Continuity

Last session: 2026-02-23 (Executing phase 07-tier-1-sentiment-aggregation)
Stopped at: Completed 07-05-PLAN.md (Scheduler pipeline chain: collect→score→aggregate per source)
Resume: Phase 07 all 5 plans complete — phase fully done

Config:
{
  "mode": "yolo",
  "depth": "quick",
  "parallelization": true,
  "commit_docs": true,
  "model_profile": "budget",
  "workflow": {
    "research": true,
    "plan_check": true,
    "verifier": true
  }
}
