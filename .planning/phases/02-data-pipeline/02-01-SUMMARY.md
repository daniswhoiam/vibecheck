---
phase: 02-data-pipeline
plan: 01
subsystem: api
tags: [asknews, oauth2, entity-normalization, structlog, tenacity, python-async]

# Dependency graph
requires:
  - phase: 01-foundation-storage
    provides: Entity model, AsyncSession, FastAPI lifespan, curated entity constants
provides:
  - AskNews SDK client with OAuth2 authentication and async methods
  - Entity normalization service with variation mapping
  - Structured logging infrastructure for pipeline operations
affects: [02-02, 02-03, 02-04]

# Tech tracking
tech-stack:
  added: [asknews>=0.4.0, tenacity>=8.2.0, structlog>=24.1.0]
  patterns: [async API client wrappers, entity name normalization, structured logging]

key-files:
  created:
    - backend/pipeline/clients/asknews_client.py
    - backend/pipeline/services/entity_service.py
  modified:
    - backend/requirements.txt
    - backend/utils/constants.py

key-decisions:
  - "Use AskNews SDK OAuth2 with scopes=['news', 'stories'] for minimal permission surface"
  - "Bidirectional substring matching for entity variations (handles partial matches like 'OpenAI GPT-4o')"
  - "Entity normalization returns None for non-curated entities (no exceptions)"
  - "Exception propagation in AskNews client for retry handling in jobs layer"
  - "ENTITY_VARIATIONS covers all 10 curated entities with 5+ variations each"

patterns-established:
  - "Pattern 1: async API client wrappers with structlog logging and standard dict responses"
  - "Pattern 2: entity normalization as separate service layer for reusability"
  - "Pattern 3: no backend. prefix in imports (Docker WORKDIR compatibility)"

# Metrics
duration: 2min
completed: 2026-02-05
---

# Phase 2 Plan 1: AskNews Integration & Entity Normalization Summary

**AskNews SDK client with OAuth2 authentication, async fetch methods for news/stories, and entity normalization service with bidirectional variation matching**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-05T12:37:14Z
- **Completed:** 2026-02-05T12:39:21Z
- **Tasks:** 3
- **Files modified:** 7

## Accomplishments
- AskNews SDK integrated with OAuth2 client credentials for news and stories API access
- Entity normalization service maps name variations to canonical names for all 10 curated entities
- Structured logging infrastructure with entity tracking and operation counts
- Pipeline directory structure established for future ingestion jobs

## Task Commits

Each task was committed atomically:

1. **Task 1: Install AskNews SDK and retry dependencies** - `a1b6a54` (chore)
2. **Task 2: Create AskNews SDK client wrapper** - `a628fce` (feat)
3. **Task 3: Implement entity normalization service** - `6cffeb8` (feat)

## Files Created/Modified
- `backend/requirements.txt` - Added asknews>=0.4.0, tenacity>=8.2.0, structlog>=24.1.0
- `backend/pipeline/__init__.py` - Pipeline package marker
- `backend/pipeline/clients/__init__.py` - API clients package marker
- `backend/pipeline/clients/asknews_client.py` - AskNewsClient class with OAuth2 auth, fetch_news() and fetch_stories() async methods
- `backend/pipeline/services/__init__.py` - Services package marker
- `backend/pipeline/services/entity_service.py` - normalize_entity_name() and get_entity_id_by_name() functions
- `backend/utils/constants.py` - ENTITY_VARIATIONS dict with 5+ variations per curated entity

## Decisions Made
- **OAuth2 scopes**: Used scopes=["news", "stories"] to request only needed permissions from AskNews API, minimizing attack surface
- **Bidirectional matching**: Entity normalization uses bidirectional substring matching (variation in name OR name in variation) to handle partial matches like "OpenAI's GPT-4o" → "GPT-4o"
- **Exception propagation**: AskNews client methods propagate exceptions instead of catching and returning empty lists, allowing retry logic to be handled by tenacity decorators in jobs layer (Plan 02/03)
- **None for non-curated**: normalize_entity_name() returns None for entities not in ENTITY_VARIATIONS instead of raising exceptions, allowing graceful filtering
- **Import paths**: All imports use relative paths (db.models, utils.constants) not backend. prefix for Docker WORKDIR compatibility

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - all tasks completed without blocking issues.

## User Setup Required

**External services require manual configuration.** AskNews API authentication needed before ingestion jobs can run:

**Service:** AskNews API
**Purpose:** News Search and Story Clustering endpoints for article and sentiment data

**Setup Steps:**
1. Create AskNews account at https://asknews.app
2. Select Spelunker tier ($250/mo, 1,500 base requests)
3. Navigate to Dashboard → API Keys
4. Generate new API key
5. Add to backend/.env: `ASKNEWS_API_KEY=your_key_here`

**Verification:**
After adding API key, verify authentication:
```bash
# In Python container
docker-compose exec backend python -c "from pipeline.clients.asknews_client import AskNewsClient; client = AskNewsClient(); print('Auth OK')"
```

**Note:** Ingestion jobs (Plan 02/02, 02/03) will fail with authentication errors until ASKNEWS_API_KEY is configured.

## Next Phase Readiness

**Ready for next phase:**
- AskNews client operational with OAuth2 authentication
- Entity normalization handles all 10 curated entities with common variations
- Pipeline directory structure in place for ingestion services
- Structured logging configured for observability

**Blockers:**
- ASKNEWS_API_KEY environment variable must be set before testing ingestion jobs
- Entity seeding script needed to populate Entity table with curated entities (database currently empty)
- Real AskNews API response structure for /stories endpoint needs validation (logged on first call for inspection)

**Concerns:**
- Entity variations dictionary is based on anticipated patterns - may need adjustment after testing with real AskNews data
- No retry logic in client layer - depends on tenacity decorators in jobs layer (Plan 02/03)

---
*Phase: 02-data-pipeline*
*Completed: 2026-02-05*
