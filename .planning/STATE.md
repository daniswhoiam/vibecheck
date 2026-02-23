# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-19)

**Core value:** Users can see how sentiment around AI models and tools has changed over time, with clear time-series data powered by real news and Reddit community opinion.
**Current focus:** v2.0 Free Pipeline — replacing AskNews with free data sources + own sentiment pipeline

## Current Position

Phase: 06-data-collection (Plan 2 of 4)
Plan: 06-02
Status: In progress
Last activity: 2026-02-23 — Completed 06-01 (data pipeline foundation)

## Accumulated Context

### Decisions

All v1.0 decisions logged in PROJECT.md Key Decisions table with outcomes.

**06-01 (2026-02-23):**
- Context words for ambiguous names use word-boundary regex (not substring) — prevents "ai" matching inside "painted", "trained", etc.
- Filter API is module-level is_relevant() function, not a FilterService class — simpler for collectors
- MAX_BODY_CHARS=50_000 (50K chars) covers ~99th percentile of Dev.to articles
- Hash input: url > body > empty string — URL is canonical dedup key across mirrors/reposts

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

Last session: 2026-02-23 (Executing phase 06-data-collection)
Stopped at: Completed 06-01-PLAN.md
Resume: Execute 06-02-PLAN.md (next source collector plan)

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
