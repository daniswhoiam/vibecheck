---
phase: 08-tier-2-llm-aspect-extraction
plan: "02"
subsystem: pipeline
tags: [groq, openai, llm, tenacity, pydantic, async, strategy-pattern]

# Dependency graph
requires:
  - phase: 08-01
    provides: "Failing test scaffolds for LLM provider, aspect extraction, and aspect API"
provides:
  - "LLMProvider ABC with extract_aspects() contract"
  - "GroqProvider using Groq SDK + asyncio.to_thread() (non-blocking)"
  - "OpenAIProvider using AsyncOpenAI native async client"
  - "get_llm_provider() factory reading LLM_PROVIDER + LLM_MODEL env vars"
  - "LLMResponseSchema / AspectScoresSchema Pydantic validators (score bounds enforced)"
  - "All 11 test_llm_provider.py tests passing GREEN"
affects: [08-03, 08-04, 08-05]

# Tech tracking
tech-stack:
  added: [groq==0.10.0, tenacity==8.3.0, openai==1.3.0]
  patterns:
    - "Strategy pattern for LLM provider abstraction (switchable via env var)"
    - "asyncio.to_thread() for synchronous SDK calls in async context"
    - "tenacity retry decorator with exponential backoff on inner sync function"
    - "Module-level SDK imports (try/except ImportError) for test patchability"
    - "Pydantic required fields (no defaults) to enforce LLM output completeness"

key-files:
  created:
    - backend/pipeline/services/llm_provider.py
  modified:
    - backend/requirements.txt

key-decisions:
  - "AspectScoresSchema fields are REQUIRED (no default=0.0) so partial LLM output (missing aspects) raises ValidationError — enforces completeness"
  - "Module-level Groq/AsyncOpenAI imports (with try/except) instead of lazy inside __init__ — required for test patching via patch('pipeline.services.llm_provider.Groq')"
  - "extra='ignore' on AspectScoresSchema silently drops unknown aspects the LLM may hallucinate"
  - "get_llm_provider() uses None guard for LLM_MODEL to use provider defaults when unset"

patterns-established:
  - "LLM provider strategy: all future providers extend LLMProvider ABC and implement extract_aspects()"
  - "Retry pattern: define inner sync _call_sync() with @retry decorator, wrap via asyncio.to_thread"
  - "Pydantic validation at LLM boundary: always validate with LLMResponseSchema before returning dict"

requirements-completed: [SENT-03]

# Metrics
duration: 3min
completed: 2026-02-23
---

# Phase 8 Plan 02: LLM Provider Abstraction Summary

**Provider-agnostic LLM abstraction with Groq (Llama 3.3 70B) + OpenAI (GPT-4o-mini), Pydantic output validation, and tenacity retry — all 11 unit tests pass GREEN**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-02-23T11:15:36Z
- **Completed:** 2026-02-23T11:18:45Z
- **Tasks:** 3 (2 with commits, 1 verification only)
- **Files modified:** 2

## Accomplishments

- `backend/pipeline/services/llm_provider.py` created with 289 lines: LLMProvider ABC, GroqProvider, OpenAIProvider, get_llm_provider() factory, LLMResponseSchema, AspectScoresSchema, EntityAspectsSchema
- GroqProvider wraps synchronous Groq SDK in `asyncio.to_thread()` with tenacity retry (3 attempts, 1s/2s/4s backoff, reraise=True)
- OpenAIProvider uses native `AsyncOpenAI` async client with identical retry and validation logic
- Pydantic schemas enforce score bounds (-1.0 to 1.0) and reject incomplete/partial aspect responses
- All 11 `test_llm_provider.py` tests pass GREEN on first run — no test modifications needed

## Task Commits

Each task was committed atomically:

1. **Task 1: Add groq, tenacity, openai to requirements.txt** - `ca22330` (chore)
2. **Task 2: Implement LLM provider abstraction in llm_provider.py** - `0815251` (feat)
3. **Task 3: Turn test_llm_provider.py tests GREEN** - no commit (no file changes; tests passed first run)

## Files Created/Modified

- `backend/pipeline/services/llm_provider.py` - Full LLM provider abstraction: ABC, GroqProvider, OpenAIProvider, factory, Pydantic schemas
- `backend/requirements.txt` - Added groq==0.10.0, tenacity==8.3.0, openai==1.3.0

## Decisions Made

- **AspectScoresSchema requires all 7 fields (no defaults):** The plan spec said `Field(default=0.0, ...)` but this would make `test_unknown_aspect_name_fails_validation` pass without error (unknown aspect gets ignored by extra='ignore', missing fields get defaults). Making fields required ensures partial LLM output raises ValidationError — correct behavior and matches test intent.
- **Module-level SDK imports:** Tests use `patch("pipeline.services.llm_provider.Groq")` requiring the name to exist in module namespace. Used try/except ImportError at module top instead of lazy imports inside `__init__`. This is safe because packages are in requirements.txt.
- **get_llm_provider() None guard for LLM_MODEL:** Uses `kwargs = {"model_id": model_id} if model_id else {}` so when LLM_MODEL is unset, the provider uses its own default model string.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] AspectScoresSchema fields changed from default=0.0 to required**
- **Found during:** Task 3 (test verification analysis)
- **Issue:** Plan spec said `Field(default=0.0, ge=-1.0, le=1.0)` but `test_unknown_aspect_name_fails_validation` provides only 2 fields and expects ValidationError. With defaults, Pydantic would fill missing fields with 0.0 and not raise — test would fail.
- **Fix:** Removed `default=0.0` from all AspectScoresSchema fields, keeping only `ge=-1.0, le=1.0` constraints. All 7 aspects are now required.
- **Files modified:** backend/pipeline/services/llm_provider.py
- **Verification:** `test_unknown_aspect_name_fails_validation` passes; `test_valid_response_passes_validation` (with all 7 fields) also passes
- **Committed in:** 0815251 (Task 2 commit)

**2. [Rule 1 - Bug] Module-level imports instead of lazy inside __init__**
- **Found during:** Task 3 (test analysis)
- **Issue:** Plan spec said "lazy import inside `__init__`" but tests patch `pipeline.services.llm_provider.Groq` and `pipeline.services.llm_provider.AsyncOpenAI`. Lazy imports inside `__init__` create local bindings, not module-level names — `patch()` would fail with AttributeError.
- **Fix:** Import `Groq` and `AsyncOpenAI` at module level with `try/except ImportError` (graceful fallback when packages absent).
- **Files modified:** backend/pipeline/services/llm_provider.py
- **Verification:** `test_groq_env_returns_groq_provider` and `test_openai_env_returns_openai_provider` both pass with patching
- **Committed in:** 0815251 (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (both Rule 1 - Bug)
**Impact on plan:** Both fixes necessary for test correctness. No scope creep. Behavior is strictly better: required fields catch incomplete LLM output early; module-level imports enable clean mocking.

## Issues Encountered

- groq, openai, tenacity not installed in local venv — installed via `pip install` in `.venv/` before running tests. This is expected: packages are Docker-only per requirements.txt, but local testing requires them.

## User Setup Required

**External services require manual configuration.** See plan frontmatter for env vars:
- `GROQ_API_KEY` — from https://console.groq.com/keys
- `LLM_PROVIDER` — set to `groq` (default), `openai`, or other supported value
- `LLM_MODEL` — optional model override (provider default used if unset)
- `LLM_MAX_CALLS_PER_RUN` — optional integer cap (default 100)

## Next Phase Readiness

- `get_llm_provider()` is ready for use in Plan 03 (aspect extraction job)
- `LLMResponseSchema` validates LLM output before storage — safe to use directly
- Provider switching via env var fully functional and tested
- No blockers for 08-03

---
*Phase: 08-tier-2-llm-aspect-extraction*
*Completed: 2026-02-23*
