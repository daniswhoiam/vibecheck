---
phase: 08-tier-2-llm-aspect-extraction
verified: 2026-02-23T22:15:00Z
status: passed
score: 5/5 must-haves verified
re_verification: false
---

# Phase 08: Tier 2 LLM Aspect Extraction - Verification Report

**Phase Goal:** Posts with ambiguous or non-neutral Tier 1 scores are processed by the configured LLM and aspect-level sentiment is stored per tool mention

**Verified:** 2026-02-23T22:15:00Z

**Status:** PASSED — All observable truths verified; all artifacts substantive and wired; all key links functional

**Requirements Coverage:** SENT-02, SENT-03, SENT-04 all satisfied

---

## Goal Achievement

### Observable Truths (5/5 Verified)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Posts with sentiment_score < 0.6 (Tier 1 low confidence) are routed to Tier 2 LLM | ✓ VERIFIED | `extract_aspects.py:25` defines `CONFIDENCE_THRESHOLD = 0.6`; line 53 filters `Post.sentiment_score < CONFIDENCE_THRESHOLD` |
| 2 | Tier 2 routing is idempotent — posts with existing AspectSentiment rows are skipped | ✓ VERIFIED | `extract_aspects.py:46-48` uses `NOT EXISTS subquery` checking for prior AspectSentiment rows; prevents reprocessing |
| 3 | All 7 defined aspects (performance, cost, reliability, UX, speed, code quality, context window) are stored per entity per post | ✓ VERIFIED | `extract_aspects.py:126-139` loops `for aspect_name in VALID_ASPECTS` storing each aspect with `session.add(AspectSentiment(...))` |
| 4 | LLM backend is switchable via LLM_PROVIDER env var without code changes (Groq, OpenAI supported) | ✓ VERIFIED | `llm_provider.py:277-289` `get_llm_provider()` factory checks `LLM_PROVIDER` env var and returns `GroqProvider` or `OpenAIProvider` instance based on value |
| 5 | New GET /entities/{id}/aspects endpoint returns aggregated aspect scores with time windows (7d/30d/90d) and optional source filter | ✓ VERIFIED | `entities.py:97-181` endpoint implemented with `Literal["7d", "30d", "90d"]` window validation, optional `source` filter parameter, SQL aggregation, and guaranteed 7-aspect response fill |

**Score:** 5/5 truths verified

---

## Required Artifacts (Substantive & Wired)

| Artifact | Path | Level 1: Exists | Level 2: Substantive | Level 3: Wired | Status |
|----------|------|--|--|--|--------|
| LLM Provider Abstraction | `backend/pipeline/services/llm_provider.py` | ✓ | ✓ (289 lines, ABC + 2 implementations + factory + Pydantic schemas) | ✓ (imported in extract_aspects.py:20, scheduler.py:25) | ✓ VERIFIED |
| Aspect Extraction Job | `backend/pipeline/jobs/extract_aspects.py` | ✓ | ✓ (151 lines, full routing/LLM/storage logic) | ✓ (called in scheduler.py:194 as Step 4) | ✓ VERIFIED |
| Aspect API Schemas | `backend/api/schemas/aspect.py` | ✓ | ✓ (38 lines, AspectWindowSchema + AspectSentimentResponse) | ✓ (imported in entities.py:13) | ✓ VERIFIED |
| Aspect API Endpoint | `backend/api/routes/entities.py` | ✓ | ✓ (85-line GET /aspects route with aggregation query, validation, 404 handling) | ✓ (route registered in router, included in main.py via app.include_router) | ✓ VERIFIED |
| Scheduler Integration | `backend/pipeline/scheduler.py` | ✓ | ✓ (Step 4 block lines 190-203, extract_aspects in 4-step pipeline) | ✓ (import line 25, call line 194, stats capture line 195) | ✓ VERIFIED |
| Dependencies | `backend/requirements.txt` | ✓ | ✓ (groq==0.10.0, tenacity==8.3.0, openai==1.3.0 all present) | ✓ (used by GroqProvider, OpenAIProvider, retry decorator) | ✓ VERIFIED |
| Test Scaffolds | `backend/tests/test_llm_provider.py, test_aspect_extraction.py, test_aspect_api.py` | ✓ | ✓ (25+ test functions, all scenarios covered) | ✓ (per summaries: all tests pass) | ✓ VERIFIED |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `extract_aspects.py` → `llm_provider.py` | `get_llm_provider()` factory | Line 20 import + line 74 call | ✓ WIRED | Factory instantiated once per job run, not per post |
| `extract_aspects.py` → `AspectSentiment` model | Session.add() + table insert | Lines 131-138 create and add instances | ✓ WIRED | All 7 aspects stored per entity via loop |
| `extract_aspects.py` → `VALID_ASPECTS` constant | Filtering + validation loop | Line 21 import + line 126 loop | ✓ WIRED | Ensures only known aspects stored |
| `llm_provider.py` → Groq SDK | `asyncio.to_thread()` wrapped call | Lines 134, 154-172 (GroqProvider) | ✓ WIRED | Synchronous SDK wrapped to avoid event loop blocking; tenacity retry decorator applied |
| `llm_provider.py` → OpenAI SDK | Native async client | Lines 205, 230-243 (OpenAIProvider) | ✓ WIRED | AsyncOpenAI is natively async; retry logic applied |
| `entities.py` → `AspectSentiment` model | SQL aggregation query via text() | Lines 145-157 aggregate query | ✓ WIRED | JOINs to posts for source filtering, aggregates by aspect |
| `scheduler.py` → `extract_aspects.py` | Import + Step 4 pipeline call | Lines 25 (import) + 194 (call) | ✓ WIRED | Called as 4th step after aggregate_sentiment; stats captured in pipeline_stats dict |
| `main.py` → aspect endpoint | Entities router auto-included | entities.py route in router, router in app.include_router | ✓ WIRED | No explicit main.py change needed; route auto-exposed via existing router mount |

---

## Requirements Coverage

| Requirement | Description | Plan(s) | Evidence | Status |
|-------------|-------------|---------|----------|--------|
| **SENT-02** | Tier 2 LLM extracts structured aspect-level sentiment for non-neutral/low-confidence posts | 08-01, 08-04, 08-05 | `extract_aspects.py:25-60` routing logic; `scheduler.py:190-203` Step 4 integration | ✓ SATISFIED |
| **SENT-03** | LLM backend is configurable via env vars (Groq, DeepInfra, or GPT-4o-mini) | 08-02, 08-03 | `llm_provider.py:277-289` factory reads `LLM_PROVIDER` env var; Groq and OpenAI implemented | ✓ SATISFIED (Groq + OpenAI; DeepInfra out of scope per RESEARCH.md) |
| **SENT-04** | Aspect-level sentiment stored per tool mention (7 fixed aspects) | 08-03, 08-04 | `entities.py:97-181` GET endpoint returns aspect scores; `extract_aspects.py:126-139` stores all 7 aspects per entity | ✓ SATISFIED |

---

## Anti-Patterns Scan

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `llm_provider.py` | 178-182 | Log warning on validation error; continues to raise — correct error propagation | ℹ️ INFO | Proper error handling; job continues safely |
| `extract_aspects.py` | 103-110 | LLM provider exception caught, logged, stats["errors"] incremented; loop continues | ℹ️ INFO | Post skipped on error, retried next run; job doesn't crash |
| `entities.py` | 172-174 | Missing aspects filled with count=0, mean=None | ℹ️ INFO | API contract fulfilled: all 7 aspects always returned |
| **None found** | — | No TODO/FIXME/placeholder comments; no empty implementations; all paths wired | ✓ CLEAN | Full substantive implementations across all components |

---

## Test Coverage Verification

All 5 Phase 08 plans executed with test validation:

- **08-01 (RED phase):** 25 test functions scaffolded (fail with ModuleNotFoundError) ✓
- **08-02 (GREEN):** 11 `test_llm_provider.py` tests pass (provider factory, model override, retry logic, Pydantic bounds) ✓
- **08-03 (GREEN):** 10 `test_aspect_api.py` tests pass (7d/30d/90d windows, source filter, 404/422 responses) ✓
- **08-04 (GREEN):** 9 `test_aspect_extraction.py` tests pass (routing, idempotency, storage, stats) ✓
- **08-05 (INTEGRATION):** Full test suite (30 tests) passes; scheduler integration verified ✓

Per 08-04-SUMMARY: "All 30 tests pass locally — no Docker required for development cycle"

---

## Human Verification Items

### 1. LLM Output Quality & Reliability

**Test:** Call Groq API (or mocked provider) with a real developer post about Claude; verify aspect scores are reasonable

**Expected:**
- All 7 aspects returned with scores in [-1.0, 1.0] range
- Aspects with no signal = 0.0
- Strong opinions (e.g., "Claude is expensive") → cost aspect score < 0.0
- Weak opinions → scores near 0.0

**Why human:** LLM behavior depends on model quality and prompt design; can't verify programmatically without runtime

---

### 2. Aggregation Accuracy (7d/30d/90d Windows)

**Test:**
1. Create 3 posts with aspects scored on day 1, day 20, day 60
2. Query GET /entities/1/aspects?window=7d → should see day 1 only
3. Query GET /entities/1/aspects?window=30d → should see days 1 and 20
4. Query GET /entities/1/aspects?window=90d → should see all three
5. Verify AVG and COUNT are correct

**Expected:** Time windows correctly filter and aggregate

**Why human:** Complex SQL aggregation; boundary conditions (midnight UTC, date math) need integration test with real database

---

### 3. Provider Switching End-to-End

**Test:**
1. Set `LLM_PROVIDER=groq`, trigger pipeline (via direct call or wait for scheduled run)
2. Verify aspects stored in DB
3. Change `LLM_PROVIDER=openai`
4. Trigger pipeline again
5. Verify OpenAI provider handles the request (check logs, verify no errors)

**Expected:** Provider switches cleanly; no code redeploy needed

**Why human:** Integration test spanning env vars → factory → provider SDK; can't verify without real API calls

---

### 4. Error Recovery on LLM Failure

**Test:**
1. Set GROQ_API_KEY to invalid value
2. Trigger pipeline with low-confidence posts queued
3. Observe job logs: should see 3 retries logged, then error logged, then job continues
4. Set GROQ_API_KEY to valid value
5. Trigger pipeline again; same posts now processed successfully

**Expected:** Failed posts are retried next run; job doesn't crash

**Why human:** Retry behavior + state recovery across runs; hard to test without real failure conditions

---

### 5. Idempotency Under Concurrent Scheduler

**Test:**
1. Enable all 4 collection jobs (HN, Reddit, Discourse, Dev.to) with 15-min stagger
2. Within a 6-hour cycle, aspect extraction runs 4x (once per source job)
3. First run processes 100 low-confidence posts → 700 AspectSentiment rows (100 posts × 7 aspects)
4. Second run finds 0 new posts (NOT EXISTS check filters them out) → returns stats.routed=0
5. Verify no duplicate rows inserted

**Expected:** Job is safe to call 4x per cycle; idempotency prevents duplication

**Why human:** Concurrent scheduling + DB constraints interaction; needs production-like load

---

## Gaps Summary

**None found.** All phase success criteria achieved:

1. ✓ Posts with confidence < 0.6 are routed to Tier 2 LLM
2. ✓ LLM output is validated (Pydantic schema enforces score bounds)
3. ✓ All 7 aspects stored per entity per post (no sparse storage)
4. ✓ LLM provider is switchable via env var (factory pattern, zero code change)
5. ✓ Aspect endpoint returns aggregated scores with time windows and source filter
6. ✓ Full integration in 4-step pipeline with fault isolation

---

## Implementation Notes

### Wiring Quality

- **Low-level correctness:** All files syntactically valid Python; all imports available in Docker context; all functions have correct signatures
- **Integration correctness:** LLM provider is called correctly (async context, retries applied, output validated); extract_aspects called once per cycle (via scheduler); endpoint wired to router
- **Failure safety:** Each step (collect, score, aggregate, extract_aspects) is wrapped in try/except; failures logged but don't crash pipeline
- **Idempotency:** Extract_aspects uses NOT EXISTS check to skip already-processed posts; safe to call multiple times per cycle

### Pattern Consistency

- Follows Phase 7 patterns: wrapped_pipeline_execution() with fault isolation, stats dict returned for audit logging, async/await throughout
- Follows established VibeCheck patterns: Pydantic validation at boundaries, SQLAlchemy async queries, FastAPI route with Literal type validation
- Provider abstraction follows strategy pattern: LLMProvider ABC, concrete implementations, factory function

### Data Flow

```
Low-confidence post (score < 0.6)
    ↓
extract_aspects job (Step 4 in pipeline)
    ↓
Query: Select(Post) WHERE sentiment_score < 0.6 AND NOT EXISTS(AspectSentiment)
    ↓
For each post:
  - Lookup entity names via PostEntityMention JOIN Entity
  - Call LLM provider (via get_llm_provider() factory)
  - Validate output with Pydantic schema
  - Store 7 AspectSentiment rows (one per aspect)
    ↓
Stats dict returned to scheduler audit log
    ↓
GET /entities/{id}/aspects endpoint queries:
  - SELECT AVG(score), COUNT(*) FROM AspectSentiment
  - GROUP BY aspect
  - Filter by window (7d/30d/90d) and source (optional)
  - Fill missing aspects with count=0, mean=None
```

---

## Conclusion

**Phase 08 achieves its goal.** All three success criteria are met in the codebase:

1. Posts routed to Tier 2 have aspect_sentiments rows covering the 7 defined aspects
2. Changing LLM_PROVIDER env var results in the new provider handling Tier 2 requests without code changes
3. New entity aspect endpoint returns aspect scores when queried for an entity with accumulated Tier 2 data

All requirements (SENT-02, SENT-03, SENT-04) are satisfied. No implementation gaps detected. Human verification is recommended for integration tests (concurrent scheduling, real LLM calls, provider switching end-to-end).

---

_Verification completed: 2026-02-23T22:15:00Z_
_Verifier: Claude (gsd-verifier)_
_Methodology: Code inspection, artifact verification, wiring validation, requirement traceability_
