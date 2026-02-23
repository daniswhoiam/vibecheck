---
phase: 09-frontend-evolution
plan: 01
subsystem: testing
tags: [vitest, react-testing-library, react-query, tdd, wave-0]

# Dependency graph
requires:
  - phase: 08-tier-2-llm-aspect-extraction
    provides: GET /entities/{id}/aspects endpoint with 7-aspect response shape
provides:
  - Wave 0 RED test scaffolds for useAspectSentiment hook
  - Wave 0 RED test scaffolds for SourceFilterToggle component
  - Wave 0 RED test scaffolds for AspectSentimentChart component
  - Wave 0 RED test scaffolds for Detail page source filter integration
  - Mock fixtures (mockAspectResponse, createQueryClient, mockEmptyAspectResponse) in src/test/mocks.ts
affects: [09-02, 09-03, 09-04, 09-05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Wave 0 TDD RED pattern — test files fail with "Cannot find module" for unimplemented code
    - mockAspectResponse factory pattern with overrides spread for flexible test data
    - createQueryClient() helper with retry=false, staleTime=Infinity for deterministic React Query tests
    - vi.mock() hoisting pattern for mocking hooks in page integration tests

key-files:
  created:
    - src/test/mocks.ts
    - src/hooks/useAspectSentiment.test.ts
    - src/components/SourceFilterToggle.test.tsx
    - src/components/AspectSentimentChart.test.tsx
    - src/pages/Detail.test.tsx
  modified: []

key-decisions:
  - "All 7 aspects hardcoded in mockAspectResponse (not dynamic) — mirrors backend schema, tests pass with known values"
  - "mockEmptyAspectResponse uses source='discourse' — matches empty state test scenario for source-specific empty message"
  - "Detail.test.tsx mocks both useToolDetail and useAspectSentiment at module level — avoids React Query network calls in page integration tests"

patterns-established:
  - "Mock factory pattern: mockAspectResponse(overrides?) spread — use for all aspect data tests in Phase 9"
  - "createQueryClient() — use in all React Query hook tests to prevent cross-test cache pollution"
  - "vi.mock() at module level before imports — required for vi.mocked() to work in test assertions"

requirements-completed: [FRON-01, FRON-02]

# Metrics
duration: 2min
completed: 2026-02-23
---

# Phase 9 Plan 01: Wave 0 TDD RED Scaffolds Summary

**Five test files with specific failing assertions establishing TDD RED state for useAspectSentiment hook, SourceFilterToggle, AspectSentimentChart, and Detail page integration — all failing with "Cannot find module" import errors.**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-23T13:28:04Z
- **Completed:** 2026-02-23T13:30:22Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Created `src/test/mocks.ts` with three mock factories: `mockAspectResponse`, `createQueryClient`, `mockEmptyAspectResponse`
- Created four test files with 13 total test cases covering all Phase 9 behaviors
- Confirmed RED state: `npm test` exits non-zero, 4 suites fail with "Failed to resolve import" (not syntax errors)
- Test infrastructure validated: existing `example.test.ts` continues to pass (1/1 tests green)

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend mocks.ts with AspectSentimentResponse fixtures and queryClient helper** - `e8218af` (test)
2. **Task 2: Create failing test scaffolds for all four Phase 9 test files** - `9527152` (test)

**Plan metadata:** (to be committed)

## Files Created/Modified
- `src/test/mocks.ts` — Three mock factory functions for aspect sentiment testing
- `src/hooks/useAspectSentiment.test.ts` — 3 tests: fetch with entityId, disabled when undefined, source param in URL
- `src/components/SourceFilterToggle.test.tsx` — 3 tests: 5 source options rendered, onChange callback, active state via data-state
- `src/components/AspectSentimentChart.test.tsx` — 4 tests: 7 aspect labels, empty state, insufficient data label, sort order
- `src/pages/Detail.test.tsx` — 3 integration tests: source filter visible, aspect section heading, DOM position order

## Decisions Made
- `mockEmptyAspectResponse` defaults `source: "discourse"` to match the "No Discourse data indexed yet" empty state test
- `Detail.test.tsx` uses `vi.mock()` at module level (not `vi.spyOn`) — required for React module mocking with vitest/vite
- No new npm packages added — `@tanstack/react-query`, `@testing-library/react`, and `react-router-dom` were already installed

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Node modules were not installed (fresh checkout state) — ran `npm install` before test run. This is standard setup, not a deviation.
- Pre-existing TypeScript errors in `src/components/ui/carousel.tsx`, `chart.tsx`, `sidebar.tsx` (truncated files) — out of scope, not fixed.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All 5 test files exist and fail with correct import errors (RED state confirmed)
- `src/test/mocks.ts` provides reusable fixtures for all Phase 9 implementation plans
- Ready for 09-02: implement `useAspectSentiment` hook (will turn `useAspectSentiment.test.ts` GREEN)
- Ready for 09-03: implement `SourceFilterToggle` component (will turn `SourceFilterToggle.test.tsx` GREEN)
- Ready for 09-04: implement `AspectSentimentChart` component (will turn `AspectSentimentChart.test.tsx` GREEN)
- Ready for 09-05: wire Detail page (will turn `Detail.test.tsx` GREEN)

## Self-Check: PASSED

- FOUND: src/test/mocks.ts
- FOUND: src/hooks/useAspectSentiment.test.ts
- FOUND: src/components/SourceFilterToggle.test.tsx
- FOUND: src/components/AspectSentimentChart.test.tsx
- FOUND: src/pages/Detail.test.tsx
- FOUND: .planning/phases/09-frontend-evolution/09-01-SUMMARY.md
- FOUND commit: e8218af (Task 1 — mocks.ts)
- FOUND commit: 9527152 (Task 2 — 4 test files)

---
*Phase: 09-frontend-evolution*
*Completed: 2026-02-23*
