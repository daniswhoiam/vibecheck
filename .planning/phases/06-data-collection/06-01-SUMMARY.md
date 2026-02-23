---
phase: 06-data-collection
plan: 01
subsystem: pipeline
tags: [pydantic, fastapi, sqlalchemy, deduplication, keyword-filter, regex]

# Dependency graph
requires:
  - phase: 05-infrastructure
    provides: "Post ORM model with content_hash UNIQUE constraint, deduplication_service.compute_content_hash()"

provides:
  - "PostCreate Pydantic transfer model shared by all source collectors"
  - "is_relevant() ambiguity-aware keyword filter (unambiguous bare-word + ambiguous context-window)"
  - "save_post() async storage with IntegrityError deduplication, 50K body cap, email PII stripping"

affects: [06-02, 06-03, 06-04, 07-nlp-pipeline]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Transfer model pattern: Pydantic PostCreate separates collector output from ORM layer"
    - "Ambiguity-aware keyword filter: unambiguous=bare word, ambiguous=word + context within ±150 chars"
    - "Silent duplicate discard: IntegrityError -> rollback -> return False (no logging table)"
    - "URL-preferred dedup key: hash(url) preferred over hash(body) for canonical deduplication"
    - "GDPR body sanitization: strip emails before storing, usernames in public posts are acceptable"

key-files:
  created:
    - backend/pipeline/models.py
    - backend/pipeline/services/filter_service.py
  modified:
    - backend/pipeline/services/storage_service.py

key-decisions:
  - "Context words for ambiguous names use word-boundary regex matching (not substring) — prevents 'ai' matching inside 'painted' or 'trained'"
  - "Filter is module-level function is_relevant(), not a FilterService class — simpler API for collectors"
  - "MAX_BODY_CHARS=50_000 (50K chars) — covers ~99th percentile of Dev.to articles per research spec"
  - "Hash input: url preferred over body, empty string fallback — URL is canonical dedup key across mirrors/reposts"

patterns-established:
  - "All collectors must normalize into PostCreate before calling save_post()"
  - "All collectors must call is_relevant(title + ' ' + (body or '')) before save_post()"

requirements-completed: [COLL-05, COLL-06]

# Metrics
duration: 3min
completed: 2026-02-23
---

# Phase 6 Plan 01: Data Pipeline Foundation Summary

**Ambiguity-aware keyword filter (is_relevant) + PostCreate Pydantic transfer model + async save_post with IntegrityError dedup, 50K body cap, and email PII stripping**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-23T08:27:06Z
- **Completed:** 2026-02-23T08:30:13Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments
- PostCreate Pydantic model provides a canonical normalized format for all four source collectors (HackerNews, Reddit, Discourse, Dev.to)
- is_relevant() filter with two tiers: unambiguous names match bare word-boundary, ambiguous names (Claude, Cursor, Gemini, Llama, Mistral) require a context word within ±150 chars
- save_post() integrates compute_content_hash(), body truncation at 50K chars, email PII stripping, and IntegrityError-based silent duplicate discard

## Task Commits

Each task was committed atomically:

1. **Task 1: Create PostCreate Pydantic model in pipeline/models.py** - `fb2852a` (feat)
2. **Task 2: Implement FilterService with ambiguity-aware keyword matching** - `6097deb` (feat)
3. **Task 3: Implement save_post() in storage_service.py** - `ae7bd1f` (feat)

## Files Created/Modified
- `backend/pipeline/models.py` - PostCreate Pydantic transfer model for all source collectors
- `backend/pipeline/services/filter_service.py` - is_relevant() with unambiguous/ambiguous keyword matching
- `backend/pipeline/services/storage_service.py` - save_post() with deduplication, body cap, PII stripping

## Decisions Made
- Context words for ambiguous entity names use word-boundary regex patterns instead of substring matching. This is critical correctness: "ai" as a substring matches inside "painted", "trained", "maintained" — causing false positives for "Claude painted the wall" type posts. Word-boundary matching prevents this.
- The filter uses a module-level `is_relevant()` function rather than a FilterService class, per the plan spec — simpler API for collector callers.
- Hash input precedence is URL > body > empty string, making URL the canonical deduplication key. This correctly deduplicates reposts of the same link across different HN/Reddit threads.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed context word substring false-positive in is_relevant()**
- **Found during:** Task 2 (FilterService implementation)
- **Issue:** The plan's `any(ctx in window for ctx in context_words)` uses substring matching. The context word "ai" matches inside "painted" ("p-**ai**-nted"), causing "Claude Monet painted the Haystacks" to return True incorrectly.
- **Fix:** Added `_CONTEXT_PATTERNS` dict of pre-compiled word-boundary regex patterns for all context words. Changed matching from `any(ctx in window ...)` to `any(ctx_pat.search(window) ...)`.
- **Files modified:** backend/pipeline/services/filter_service.py
- **Verification:** Test `assert not is_relevant('Claude Monet painted the Haystacks')` passes. All plan verification tests and additional edge cases pass.
- **Committed in:** 6097deb (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug fix)
**Impact on plan:** Essential correctness fix. The bug would cause significant false positives for the "claude" and "cursor" ambiguous names given how common short words like "ai" appear as substrings in English text.

## Issues Encountered
- Docker not running locally — verification of pydantic imports done via AST/syntax checks and stdlib-only test harness for filter logic. Full import chain verification requires Docker to be running with project dependencies installed.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Foundation complete: PostCreate, is_relevant(), save_post() ready for all four source collectors
- Plans 06-02 through 06-04 can each call `from pipeline.models import PostCreate`, `from pipeline.services.filter_service import is_relevant`, `from pipeline.services.storage_service import save_post`
- No blockers — storage layer depends on DB connection which is tested in integration with Docker

## Self-Check: PASSED

- FOUND: backend/pipeline/models.py
- FOUND: backend/pipeline/services/filter_service.py
- FOUND: backend/pipeline/services/storage_service.py
- FOUND commit: fb2852a (Task 1 - PostCreate model)
- FOUND commit: 6097deb (Task 2 - FilterService)
- FOUND commit: ae7bd1f (Task 3 - storage_service)

---
*Phase: 06-data-collection*
*Completed: 2026-02-23*
