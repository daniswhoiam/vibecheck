---
phase: 11-entity-linking
plan: 03
subsystem: pipeline
tags: [entity-linking, mention-extraction, collectors, hackernews, reddit, discourse, devto, pipeline]

# Dependency graph
requires:
  - phase: 11-01
    provides: MentionExtractor service and extract_and_save_mentions() function
provides:
  - All 4 collection jobs wire entity mention extraction immediately after each successful save_post()
  - save_post() now returns Post ORM object (with .id) or None — backward-compatible with all callers
  - New posts collected going forward get entity links in the same job run as collection
affects:
  - aggregation queries (entity mentions now populated for new posts automatically)
  - 11-entity-linking (phase complete after this plan)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "MentionExtractor initialized once per job run (not per post) to avoid N+1 DB queries"
    - "save_post() returns Post ORM object (truthy) or None (falsy) — callers use truthiness check"
    - "Mention extraction errors caught as warnings; collection never aborted by extraction failure"

key-files:
  created: []
  modified:
    - backend/pipeline/services/storage_service.py
    - backend/pipeline/jobs/collect_hackernews.py
    - backend/pipeline/jobs/collect_reddit.py
    - backend/pipeline/jobs/collect_discourse.py
    - backend/pipeline/jobs/collect_devto.py

key-decisions:
  - "save_post() return type changed from bool to Post|None — preserves backward-compatible truthiness, enables saved.id access for mention extraction"
  - "Mention extraction runs inside the if saved: branch only — duplicates do not get re-extracted"
  - "HN collector: extraction for both stories and comments (both call save_post separately)"
  - "Dev.to: full_text (post-body-fetch) used for extraction — ensures full article text coverage"

patterns-established:
  - "Pipeline integration pattern: import MentionExtractor, init once before loop, call extract_and_save_mentions after truthy save_post"
  - "Stats dict always includes mentions_extracted key for observability"

requirements-completed: [SENT-01, SENT-02, SENT-04, FRON-01, FRON-02]

# Metrics
duration: 10min
completed: 2026-02-23
---

# Phase 11 Plan 03: Pipeline Mention Extraction Integration Summary

**All 4 collectors (HN, Reddit, Discourse, Dev.to) wired to extract entity mentions after each new post save — using Post ORM return from storage_service for same-transaction ID access**

## Performance

- **Duration:** ~10 min
- **Started:** 2026-02-23T15:58:39Z
- **Completed:** 2026-02-23T16:07:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- All 4 collectors import MentionExtractor and extract_and_save_mentions from mention_service
- MentionExtractor initialized once per job run (load_entities cached in memory during run)
- Mention extraction runs immediately after each successful post save, using saved.id
- stats["mentions_extracted"] tracked in all 4 collector stat dicts
- Extraction errors are warnings only — collection continues on any mention failure
- storage_service.save_post() now returns Post ORM object or None (backward-compatible)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add mention extraction to HN and Reddit collectors** - `5f1e240` (feat)
2. **Task 2: Add mention extraction to Discourse and Dev.to collectors** - `08536a4` (feat)

**Plan metadata:** _(docs commit follows)_

## Files Created/Modified
- `backend/pipeline/services/storage_service.py` - Return type changed bool→Post|None; added session.refresh(post) for .id population
- `backend/pipeline/jobs/collect_hackernews.py` - Import + extractor init + extraction for both stories and comments
- `backend/pipeline/jobs/collect_reddit.py` - Import + extractor init + extraction inside _process_subreddit closure
- `backend/pipeline/jobs/collect_discourse.py` - Import + extractor init + extraction after save_post
- `backend/pipeline/jobs/collect_devto.py` - Import + extractor init + extraction with full article text

## Decisions Made
- **save_post() return type:** Changed from `bool` to `Post | None`. All callers use `if saved:` truthiness check (backward-compatible), but now callers can also access `saved.id` for mention extraction. Added `await session.refresh(post)` to populate the .id after commit.
- **Dev.to text:** Uses `full_text` (the already-computed title+body string) rather than re-constructing from normalized dict — avoids redundant string construction and uses the exact text that passed relevance check.
- **Reddit inner closure:** `extractor` captured from outer scope via closure — correct Python semantics, same pattern as `stats` dict.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] save_post() returns bool, not Post ORM object with .id**
- **Found during:** Task 1 (Add mention extraction to HN and Reddit collectors)
- **Issue:** The plan's pattern used `saved.id` to pass to `extract_and_save_mentions()`, but `storage_service.save_post()` returns `True` (bool), not the ORM object. This would cause `AttributeError: 'bool' object has no attribute 'id'`.
- **Fix:** Modified `save_post()` to return the `Post` ORM object on success (after `session.refresh(post)` to populate server-generated .id) and `None` on duplicate. All existing callers use truthiness check (`if saved:`) so this is backward-compatible.
- **Files modified:** `backend/pipeline/services/storage_service.py`
- **Verification:** Python syntax check passes; all caller sites unchanged (still use `if saved:`)
- **Committed in:** `5f1e240` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug)
**Impact on plan:** Essential for correctness. The plan assumed `.id` access on save_post() return; fixing the return type was necessary to implement the plan as designed.

## Issues Encountered
- Docker infrastructure unavailable for test suite execution: TimescaleDB HA image manifest error prevents `docker compose up`, and the existing backend container image predates Phase 8 (missing numpy, pgvector). Tests could not be run. Python syntax validation confirmed all 5 modified files are syntactically valid.

## Next Phase Readiness
- Phase 11 entity linking is complete: Plan 01 (MentionExtractor service), Plan 02 (backfill job), Plan 03 (pipeline integration) all done
- Entity mentions will be extracted for all new posts immediately upon collection
- Aggregation pipeline (Phase 7) can now join through PostEntityMention for accurate entity-level sentiment

---
*Phase: 11-entity-linking*
*Completed: 2026-02-23*
