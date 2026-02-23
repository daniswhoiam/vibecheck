---
phase: 08-tier-2-llm-aspect-extraction
plan: 01
subsystem: testing
tags: [pytest, pytest-asyncio, tdd, red-phase, llm-provider, aspect-extraction, pydantic]

# Dependency graph
requires:
  - phase: 07-tier-1-sentiment-aggregation
    provides: Post.sentiment_score and Post.sentiment_label columns used as routing criteria in tests
  - phase: 08-tier-2-llm-aspect-extraction
    provides: CONTEXT.md and RESEARCH.md decisions that drove test case design
provides:
  - failing test scaffolds for all Phase 8 concerns (RED phase)
  - conftest fixtures for mock LLM provider, low/high-confidence posts, sample aspect data
  - test_llm_provider.py covering provider factory, score bounds, unknown aspect validation
  - test_aspect_extraction.py covering routing logic, idempotency, aspect storage behavior
  - test_aspect_api.py covering time windows (7d/30d/90d), source filter, 404/422 responses
affects: [08-02, 08-03, 08-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "TDD RED phase: import from not-yet-created modules to ensure tests fail at collection stage"
    - "AsyncMock for LLM provider fixtures — no real API calls in unit tests"
    - "monkeypatch for env var switching (LLM_PROVIDER, LLM_MODEL) in provider factory tests"

key-files:
  created:
    - backend/tests/__init__.py
    - backend/tests/conftest.py
    - backend/tests/test_llm_provider.py
    - backend/tests/test_aspect_extraction.py
    - backend/tests/test_aspect_api.py
  modified: []

key-decisions:
  - "Assumption documented in test_aspect_api.py: entity with no aspects returns 200 with empty aspects (not 404)"
  - "All 7 aspects stored per entity per post (not sparse) — test asserts len(added_objects) == len(VALID_ASPECTS)"
  - "Unmatched LLM entity names (not in PostEntityMention) are silently skipped, not treated as errors"

patterns-established:
  - "Phase 8 test pattern: mock session.execute() with side_effect list for multi-query test flows"
  - "Provider factory tests use patch() to avoid requiring actual Groq/OpenAI SDK at test time"
  - "Stats dict contract: {routed, extracted, errors} — all three keys must be present even on empty run"

requirements-completed: [SENT-02, SENT-03, SENT-04]

# Metrics
duration: 6min
completed: 2026-02-23
---

# Phase 8 Plan 01: Phase 8 Test Scaffolds (Wave 0) Summary

**TDD RED phase: 25 failing test functions across 3 test files covering LLM provider factory, aspect extraction routing+storage, and aspect API endpoint — all fail with ModuleNotFoundError awaiting implementation**

## Performance

- **Duration:** 6 min
- **Started:** 2026-02-23T11:06:44Z
- **Completed:** 2026-02-23T11:13:00Z
- **Tasks:** 1 (TDD RED phase)
- **Files modified:** 5

## Accomplishments
- Created `backend/tests/` directory with `__init__.py` package marker
- Created `conftest.py` with 4 shared fixtures: `mock_llm_provider` (AsyncMock), `low_confidence_post` (score=0.4), `high_confidence_post` (score=0.9), `sample_aspect_data` (14 AspectSentiment-compatible rows for 2 posts, 1 entity, 7 aspects each)
- Created `test_llm_provider.py` (8 tests) covering: provider factory Groq/OpenAI/unknown env var selection, LLM_MODEL override, extract_aspects() entity-keyed dict return, retry-exhaustion exception, Pydantic bounds validation (score > 1.0, score < -1.0, unknown aspect name)
- Created `test_aspect_extraction.py` (8 tests) covering: low-confidence routing (score < 0.6), high-confidence exclusion (score >= 0.6), idempotency (no reprocessing when aspects exist), unscored posts excluded (sentiment_label=None), successful extraction writes rows, all 7 aspects stored per entity, unmatched entity names skipped, stats dict with correct keys
- Created `test_aspect_api.py` (9 tests) covering: 7d/30d/90d windows, source filter (hn/reddit), invalid window returns 422, unknown entity returns 404, entity with no aspects returns 200, response structure includes entity_id/aspects

## Task Commits

1. **Task 1: TDD RED phase — failing test scaffolds** - `72cd6e3` (test)

## Files Created/Modified
- `backend/tests/__init__.py` - Package marker for tests directory
- `backend/tests/conftest.py` - Shared fixtures: mock_llm_provider, low_confidence_post, high_confidence_post, sample_aspect_data
- `backend/tests/test_llm_provider.py` - 8 tests: provider factory selection, model override, extract_aspects behavior, Pydantic validation
- `backend/tests/test_aspect_extraction.py` - 8 tests: routing logic, idempotency, storage behavior, stats dict structure
- `backend/tests/test_aspect_api.py` - 9 tests: time windows, source filter, 404/422 responses, response structure

## Decisions Made
- **Assumption documented**: GET /entities/{id}/aspects for entity with no aspect data returns 200 with empty aspects dict (not 404). This was TBD per plan; resolved as 200-empty to simplify API consumers.
- **All 7 aspects stored per entity**: Test asserts exactly `len(VALID_ASPECTS)` = 7 rows added per entity per post, consistent with RESEARCH.md recommendation to avoid ambiguity between "not mentioned" and "neutral=0.0"
- **Unmatched LLM entity names silently skipped**: Entity named by LLM but not present in PostEntityMention is dropped with zero rows stored (test validates 0 adds when LLM returns entity not in mentions)

## Deviations from Plan

None - plan executed exactly as written. All test files created, all fail with ModuleNotFoundError (not syntax errors), all success criteria met.

## Issues Encountered

- **No pytest in host Python environment**: Host macOS Python 3.14 (Homebrew) is PEP 668 restricted; `pip install` blocked. Resolved by creating a `.venv` at project root and installing pytest/pytest-asyncio there for verification. The virtual environment is not committed and not part of the test infrastructure — Docker container will use `requirements.txt` which already includes `pytest==8.2.0` and `pytest-asyncio==0.24.0`.
- **pyproject.toml addopts interference**: `addopts = "--cov=backend --cov-report=html"` requires `pytest-cov` not installed in the local venv. Verified using `--override-ini="addopts="` flag. Does not affect Docker-based test runs.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- RED phase complete: all 25 test functions fail with `ModuleNotFoundError` (not syntax errors)
- Plan 02 will implement `pipeline/services/llm_provider.py` (GroqProvider, OpenAIProvider, get_llm_provider, LLMResponseSchema)
- Plan 03 will implement `pipeline/jobs/extract_aspects.py` (run_extract_aspects with routing logic, entity matching, storage)
- Plan 04 will implement `GET /entities/{id}/aspects` endpoint in `api/routes/entities.py`
- GREEN phase gate: all 25 tests pass after plan 04 completes

---
*Phase: 08-tier-2-llm-aspect-extraction*
*Completed: 2026-02-23*
