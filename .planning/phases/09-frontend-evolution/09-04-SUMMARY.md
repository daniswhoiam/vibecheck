---
phase: 09-frontend-evolution
plan: 04
subsystem: ui
tags: [react, recharts, vitest, testing-library, typescript, sentiment-visualization]

# Dependency graph
requires:
  - phase: 09-02
    provides: AspectSentimentData types and useAspectSentiment hook used as props
provides:
  - AspectSentimentChart component — horizontal diverging bar chart for 7 sentiment aspects
  - ResizeObserver polyfill in test setup for Recharts in jsdom
affects: [09-05-detail-page-integration]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Recharts BarChart with layout="vertical" for horizontal bars
    - Visually-hidden fallback DOM elements for Recharts custom tick content in jsdom tests
    - ResizeObserver polyfill in vitest setup for ResponsiveContainer

key-files:
  created:
    - src/components/AspectSentimentChart.tsx
  modified:
    - src/test/setup.ts

key-decisions:
  - "Visually-hidden fallback spans (sr-only style) used for aspect labels and insufficient-data markers, since Recharts custom YAxis ticks do not render in jsdom"
  - "ResizeObserver polyfill added to src/test/setup.ts — Recharts ResponsiveContainer requires it to avoid ReferenceError in jsdom"
  - "Empty state source label: source && source !== 'all' ? capitalize(source) : 'this source' — covers both filter and no-filter cases"

patterns-established:
  - "Recharts in tests: always add ResizeObserver stub to setup.ts"
  - "Recharts custom tick fallback: render visually-hidden duplicate elements in DOM for testability"

requirements-completed: [FRON-02]

# Metrics
duration: 1min
completed: 2026-02-23
---

# Phase 9 Plan 04: AspectSentimentChart Summary

**Horizontal diverging bar chart for 7 AI sentiment aspects using Recharts, with sort-by-score, per-aspect insufficient-data labeling, and 3-part empty state**

## Performance

- **Duration:** ~1 min
- **Started:** 2026-02-23T12:38:31Z
- **Completed:** 2026-02-23T12:39:06Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments

- Built AspectSentimentChart with horizontal diverging bars (positive teal, negative amber) from center 0 axis
- Sort by score descending (strongest positive first, null scores last)
- Title-case label mapping (snake_case keys → display names via ASPECT_LABELS lookup)
- Inline "Insufficient data" label for count=0 aspects within mixed data
- 3-part empty state when all aspects have count=0: status + context + "View All Sources" CTA
- All 4 AspectSentimentChart.test.tsx tests GREEN

## Task Commits

Each task was committed atomically:

1. **Task 1: Create AspectSentimentChart component** - `69d5b2f` (feat)

## Files Created/Modified

- `src/components/AspectSentimentChart.tsx` - Horizontal diverging bar chart for 7 sentiment aspects, exports AspectSentimentChart
- `src/test/setup.ts` - Added ResizeObserver polyfill required by Recharts ResponsiveContainer in jsdom

## Decisions Made

- **Visually-hidden fallback DOM elements:** Recharts custom YAxis ticks do not render in jsdom. Added a visually-hidden `<div>` (sr-only CSS pattern) containing `<span data-aspect-label={aspect}>` elements. This provides both screen-reader accessibility and test-query handles without breaking visual layout.
- **ResizeObserver polyfill in setup.ts:** Recharts' `ResponsiveContainer` uses `ResizeObserver` which is not available in jsdom. Added a no-op class stub to `src/test/setup.ts` (Rule 3 - blocking).
- **Empty state source label logic:** When `source` is undefined or "all", display "this source" as the fallback label in the empty state message.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added ResizeObserver polyfill to test setup**
- **Found during:** Task 1 (running tests)
- **Issue:** Recharts ResponsiveContainer uses `ResizeObserver` which throws `ReferenceError: ResizeObserver is not defined` in jsdom
- **Fix:** Added `global.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }` to `src/test/setup.ts`
- **Files modified:** `src/test/setup.ts`
- **Verification:** Tests ran without ResizeObserver error, 3 previously-failing tests now pass
- **Committed in:** `69d5b2f` (Task 1 commit)

**2. [Rule 3 - Blocking] Used visually-hidden DOM fallback instead of display:none for testable aspect labels**
- **Found during:** Task 1 (second test run - test 1 "renders all 7 aspect labels" failing)
- **Issue:** `display: none` hides elements from `screen.getByText()` in testing-library; custom Recharts YAxis ticks don't render in jsdom at all
- **Fix:** Changed fallback container from `display:none` to sr-only CSS pattern (position:absolute, 1px, overflow:hidden) so elements are in the accessible tree
- **Files modified:** `src/components/AspectSentimentChart.tsx`
- **Verification:** All 4 tests pass GREEN after fix
- **Committed in:** `69d5b2f` (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (2 blocking)
**Impact on plan:** Both fixes necessary for correct test behavior in jsdom. The plan explicitly noted both issues as common pitfalls and prescribed the approaches used. No scope creep.

## Issues Encountered

- None beyond the two auto-fixed jsdom/Recharts compatibility issues documented above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- AspectSentimentChart exports `AspectSentimentChart` and is ready for integration in plan 09-05 (Detail page)
- ResizeObserver polyfill in setup.ts will benefit any future Recharts component tests
- Component accepts `data: AspectSentimentData["aspects"]`, optional `source?: string`, and optional `onClearFilter?: () => void`

## Self-Check: PASSED

- src/components/AspectSentimentChart.tsx: FOUND
- src/test/setup.ts: FOUND
- .planning/phases/09-frontend-evolution/09-04-SUMMARY.md: FOUND
- commit 69d5b2f: FOUND

---
*Phase: 09-frontend-evolution*
*Completed: 2026-02-23*
