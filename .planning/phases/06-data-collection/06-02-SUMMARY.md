---
phase: 06-data-collection
plan: "02"
subsystem: pipeline
tags: [hackernews, algolia, discourse, httpx, async, data-collection]

# Dependency graph
requires:
  - phase: 06-01
    provides: filter_service.is_relevant, storage_service.save_post, PostCreate model, pipeline foundation

provides:
  - HN Algolia client (fetch_hn_stories, fetch_hn_comments_for_story, normalize_hn_story, normalize_hn_comment)
  - HN collection job (run_collect_hackernews) — fetch -> filter -> store with stats
  - Discourse REST client (fetch_discourse_topics, fetch_topic_body, normalize_discourse_topic, DISCOURSE_FORUMS)
  - Discourse collection job (run_collect_discourse) — two-pass title+body filter with stats

affects:
  - 06-03 (Reddit/Dev.to collectors — same client+job pattern)
  - 06-04 (scheduler integration — registers these jobs)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Client module: pure HTTP, no DB deps, raises on errors"
    - "Job module: fetch -> filter (is_relevant) -> store (save_post) -> return stats dict"
    - "_fetch_with_retry: exponential backoff wrapper for outer fetch calls"
    - "Two-pass filtering for Discourse: title first (cheap), then body after fetching OP"

key-files:
  created:
    - backend/pipeline/clients/hackernews_client.py
    - backend/pipeline/jobs/collect_hackernews.py
    - backend/pipeline/clients/discourse_client.py
    - backend/pipeline/jobs/collect_discourse.py
  modified: []

key-decisions:
  - "HN: top-level comment filter via parent_id == story_id (not Algolia parent_path) — direct parent check is simpler and correct"
  - "Discourse: two-pass filter (title then body) conserves API calls on rate-sensitive Discourse forums"
  - "Discourse: 1s INTER_PAGE_DELAY between requests; 429 handled with Retry-After header before single retry"
  - "HN: 1000-hit cap logged as WARNING not error — callers should use weekly time windows for backfill"

patterns-established:
  - "All collectors: async def run_collect_X(session: AsyncSession) -> dict"
  - "All stats dicts include at minimum: collected, filtered, duplicates, errors keys"
  - "Per-forum error isolation in Discourse: exception on one forum doesn't abort others"

requirements-completed:
  - COLL-01
  - COLL-03

# Metrics
duration: 3min
completed: 2026-02-23
---

# Phase 06 Plan 02: HN + Discourse Source Collectors Summary

**HN Algolia client with 1000-hit cap handling and Discourse REST client with two-pass title+body filtering, both wired into collect jobs using the shared filter+storage pipeline**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-23T08:32:59Z
- **Completed:** 2026-02-23T08:35:40Z
- **Tasks:** 2
- **Files modified:** 4 created

## Accomplishments
- HN Algolia client fetches stories and top-level comments via `search_by_date` endpoint with pagination and 1000-hit cap warning
- HN collection job applies `is_relevant()` filter, fetches top-level comments from passing stories, calls `save_post()`, returns stats dict
- Discourse client fetches latest topics from forum.cursor.com and community.openai.com with 1s polite delay and 429 Retry-After handling
- Discourse collection job uses two-pass filtering (title first, then body after fetching OP) before storage

## Task Commits

Each task was committed atomically:

1. **Task 1: HN Algolia client and collection job** - `abd485c` (feat)
2. **Task 2: Discourse REST client and collection job** - `e88c7c5` (feat)

**Plan metadata:** TBD (docs: complete plan)

## Files Created/Modified
- `backend/pipeline/clients/hackernews_client.py` - HN Algolia API client: fetch stories, comments, normalize to PostCreate
- `backend/pipeline/jobs/collect_hackernews.py` - HN collection job: fetch->filter->store with retry and stats
- `backend/pipeline/clients/discourse_client.py` - Discourse REST client: latest topics, topic body fetch, normalize
- `backend/pipeline/jobs/collect_discourse.py` - Discourse collection job: two-pass title+body filter, per-forum isolation

## Decisions Made
- HN top-level comment filtering uses `parent_id == story_id` check (not Algolia's `parent_path`) — direct parent ID comparison is unambiguous
- Discourse two-pass filter (title first, then body) conserves API calls on rate-sensitive Discourse instances — only fetch OP body for title-passing topics
- HN 1000-hit cap logs a WARNING (not error) since it's expected behavior for large time windows — callers should use weekly chunks for backfill

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- System Python3 lacked `asyncpg` (C extension, Docker-only), so verification used AST parsing instead of live imports. All files parsed cleanly and export signatures confirmed via source inspection. Full live verification occurs in Docker runtime.

## User Setup Required

None - no external service configuration required. Both HN and Discourse APIs are public and unauthenticated.

## Next Phase Readiness
- Wave 2 collectors complete. Pattern established for all future collectors.
- Plan 03 (Reddit + Dev.to) follows the same client+job structure and can import `is_relevant`/`save_post` identically.
- Plan 04 scheduler integration will register `run_collect_hackernews` and `run_collect_discourse` as APScheduler jobs.

---
*Phase: 06-data-collection*
*Completed: 2026-02-23*

## Self-Check: PASSED

- FOUND: backend/pipeline/clients/hackernews_client.py
- FOUND: backend/pipeline/jobs/collect_hackernews.py
- FOUND: backend/pipeline/clients/discourse_client.py
- FOUND: backend/pipeline/jobs/collect_discourse.py
- FOUND: .planning/phases/06-data-collection/06-02-SUMMARY.md
- FOUND commit: abd485c (Task 1 - HN client and job)
- FOUND commit: e88c7c5 (Task 2 - Discourse client and job)
