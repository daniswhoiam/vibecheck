---
milestone: v1
audited: 2026-02-05T15:00:00Z
status: gaps_found
scores:
  requirements: 11/12
  phases: 3/3
  integration: 5/6
  flows: 1/2
gaps:
  critical:
    - "Entity seeding not automated - breaks article ingestion flow"
  requirements:
    - "STOR-01 partial: entities must be manually seeded before articles can be stored"
  integration:
    - "Entity seeding script exists but not called on application startup"
  flows:
    - "Article ingestion flow broken without seeded entities"
tech_debt:
  - phase: 01-foundation-storage
    items:
      - "Entity seeding not automated in FastAPI lifespan"
      - "No entity existence validation in database operations"
  - phase: 02-data-pipeline
    items:
      - "Jobs don't validate entity existence before processing"
      - "No automatic entity creation on first job execution"
  - phase: 03-api-integration
    items:
      - "API endpoints return empty results without seeded entities"
      - "No helpful error message when database empty"
---

# VibeCheck v1 Milestone — Audit Report

**Audited:** 2026-02-05 15:00 UTC
**Status:** ⚠️ **Gaps Found** — 1 critical blocker
**Milestone Definition:** Backend data pipeline and API that tracks public sentiment around AI models/tools

---

## Executive Summary

**Score:** 11/12 requirements satisfied | 3/3 phases passed | 5/6 integration points wired | 1/2 E2E flows complete

The VibeCheck v1 milestone has **1 critical gap** that prevents end-to-end functionality:

### Critical Blocker

**Entity seeding not automated** — The `seed_entities.py` script exists and functions correctly, but it is not called automatically during application startup. This breaks the article ingestion flow because:

1. Jobs depend on entities existing in the database (foreign key constraint)
2. API endpoints return empty results without entities
3. No validation or helpful error messages when database is empty

**Impact:** High — System appears non-functional until manual seeding executed
**Fix required:** Add entity seeding to FastAPI lifespan in `main.py`

### What Works

All three phases are individually complete and verified:
- ✅ Phase 1 (Foundation): Database, models, Docker, health checks
- ✅ Phase 2 (Data Pipeline): AskNews integration, scheduler, normalization, deduplication
- ✅ Phase 3 (API): Entity/sentiment endpoints, CORS, error handling

Cross-phase integration is mostly solid:
- ✅ Models properly imported across phases
- ✅ Session factory used in jobs and API routes
- ✅ Scheduler health monitoring connected to health endpoints

---

## Requirements Coverage

| ID | Requirement | Phase | Status | Evidence |
|----|-------------|-------|--------|----------|
| STOR-01 | Article storage with metadata | 1 | ⚠️ PARTIAL | Article model exists, but entities must be manually seeded first |
| STOR-02 | Time-series sentiment aggregates | 1 | ✅ SATISFIED | SentimentTimeseries model with proper indexes |
| INGT-01 | AskNews `/news` endpoint integration | 2 | ✅ SATISFIED | `poll_news_job` with retry, entity filters |
| INGT-02 | AskNews `/stories` endpoint integration | 2 | ✅ SATISFIED | `poll_stories_job` with Reddit extraction |
| INGT-03 | Entity name normalization | 2 | ✅ SATISFIED | `normalize_entity_name()` with 50+ variations |
| SCHD-01 | 15-min news polling | 2 | ✅ SATISFIED | APScheduler with 15min interval |
| SCHD-02 | 60-min stories polling | 2 | ✅ SATISFIED | APScheduler with 60min interval |
| SCHD-03 | Execution logging | 2 | ✅ SATISFIED | SchedulerExecutionLog with full audit trail |
| API-01 | GET /entities with sentiment | 3 | ✅ SATISFIED | Entity endpoints with latest sentiment |
| API-02 | GET /entities/{id}/sentiment time-series | 3 | ✅ SATISFIED | Time-series endpoint with filtering/pagination |
| INFR-01 | Docker Compose environment | 1 | ✅ SATISFIED | docker-compose.yml with health checks |
| INFR-02 | CORS for frontend | 3 | ✅ SATISFIED | Environment-aware CORS middleware |

**Score:** 11/12 satisfied (92%)

### Partial Requirements Detail

**STOR-01 (Article storage)**
- Status: Partial - Entities must be manually seeded
- Evidence:
  - Article model complete with all fields
  - Storage service implements deduplication
  - Foreign key to entities.id enforced
- Gap: `scripts/seed_entities.py` exists but not called automatically
- Fix: Add to FastAPI lifespan startup in `main.py`

---

## Phase Verification Summary

### Phase 1: Foundation & Storage
**Status:** ✅ PASSED | Score: 27/27 must-haves verified

All 27 success criteria verified:
- PostgreSQL database with proper schema (entities, articles, sentiment_timeseries)
- SQLAlchemy async ORM models with 2.0+ syntax
- Docker Compose with health checks and service dependencies
- TimescaleDB-compatible time-series patterns (composite indexes)
- Health endpoint with database connectivity test
- Environment variable configuration via .env
- Curated entity list defined (10 entities: 5 models + 5 tools)

**Tech Debt:**
- Entity seeding script not automated (critical gap)

### Phase 2: Data Pipeline
**Status:** ✅ PASSED | Score: 5/5 must-haves verified

All 5 success criteria verified:
- System fetches articles from AskNews `/news` every 15 minutes
- System fetches stories from AskNews `/stories` every 60 minutes
- Entity name variations normalize to canonical names (50+ variations)
- Scheduler logs each execution with status, duration, errors
- No duplicate articles (deduplication via external_id + url_hash)

**Artifacts Verified:**
- AskNews client (174 lines) with OAuth2 auth
- Entity normalization service (117 lines) with bidirectional matching
- Deduplication service (100 lines) with SHA256 hashing
- Storage service (110 lines) with batch insertion
- News ingestion job (203 lines) with retry logic
- Story ingestion job (227 lines) with Reddit extraction
- Sentiment service (222 lines) with time-series aggregation
- Scheduler (235 lines) with health monitoring

**Tech Debt:**
- Jobs don't validate entity existence before processing
- No automatic entity creation on first execution

### Phase 3: API & Integration
**Status:** ✅ PASSED | Score: 4/4 must-haves verified (re-verified after gap closure)

All 4 success criteria verified:
- GET /entities returns all tracked AI entities with latest sentiment
- GET /entities/{id}/sentiment returns time-series data with filtering
- CORS configured for frontend (environment-aware)
- API responds with proper error codes (404, 400, 500)

**Artifacts Verified:**
- Entity routes with Pydantic schemas
- Sentiment routes with cursor-based pagination
- CORS middleware with production restrictions
- Comprehensive error handling

**Tech Debt:**
- No helpful error message when database empty

---

## Cross-Phase Integration

### Wiring Status: 5/6 Connected

| Connection | Status | Evidence |
|------------|--------|----------|
| Phase 1 → Phase 2 (Models) | ✅ WIRED | Entity/Article/SentimentTimeseries imported in jobs |
| Phase 1 → Phase 2 (Session) | ✅ WIRED | `get_session()` dependency in scheduled jobs |
| Phase 1 → Phase 3 (Models) | ✅ WIRED | Entity models used in API routes |
| Phase 1 → Phase 3 (Session) | ✅ WIRED | Session factory used in all API endpoints |
| Phase 2 → Phase 3 (Data) | ✅ WIRED | SentimentTimeseries queried by sentiment API |
| Phase 1 → Lifecycle (Seeding) | ❌ MISSING | Entity seeding not in FastAPI lifespan |

### Orphaned Component

**`backend/scripts/seed_entities.py`**
- Status: Created but never called
- Impact: Database empty until manually executed
- Fix: Add to `main.py` lifespan startup

---

## End-to-End Flow Verification

### Flow 1: Health Monitoring ✅ COMPLETE

```
FastAPI startup → Scheduler init → Job execution → DB logging → Health endpoint query
```

**Verification:**
- ✅ Scheduler starts on FastAPI startup (`main.py` lifespan)
- ✅ Jobs register with APScheduler (15min news, 60min stories)
- ✅ Job execution logged to `SchedulerExecutionLog` table
- ✅ Health check `/health` tests DB connectivity
- ✅ Health check `/health/scheduler` reports job status
- ✅ Proper HTTP status codes (200 healthy, 503 unhealthy)

**Status:** Fully functional

### Flow 2: Article Ingestion ❌ BROKEN

```
AskNews API → Entity normalization → Deduplication → Storage → API query
```

**Break point:** Entity seeding

**Flow trace:**
1. ✅ AskNews client authenticates with API key
2. ✅ News job fetches articles with entity filters
3. ✅ Entity normalization maps variations to canonical names
4. ✅ Deduplication checks external_id and url_hash
5. ❌ **FAILS HERE:** Article.entity_id references non-existent entity
6. ❌ Foreign key constraint violation or empty results
7. ❌ API endpoints return empty entity lists

**Root cause:** Entities not seeded in database
**Impact:** Jobs fail silently or violate foreign key constraints
**Fix:** Call `seed_entities()` in FastAPI lifespan before scheduler starts

---

## Anti-Patterns Scan

**Result:** ✅ No blockers found in code

No stub patterns, TODO comments, or placeholder implementations detected in:
- All API routes (entities, sentiment, health)
- All pipeline jobs (news, stories)
- All services (normalization, deduplication, storage, sentiment)
- Database models and migrations
- Scheduler configuration

**Code Quality:**
- Proper error handling with try/except blocks
- Graceful degradation for missing data
- Structured logging via structlog
- Full async/await with proper session management
- Pydantic validation on all API responses

---

## Risks & Considerations

### Critical
1. **Entity seeding required before testing** — System appears broken until manual execution
2. **Jobs may fail silently** — No validation that entities exist before processing

### Medium
1. **AskNews API key setup** — User must configure ASKNEWS_API_KEY (documented)
2. **Database migrations** — User must run `alembic upgrade head` (documented)
3. **Docker dependency** — Local development requires Docker Desktop

### Low
1. **Reddit data variance** — Some stories lack Reddit threads (handled gracefully)
2. **Time-series uniqueness** — INSERT ON CONFLICT DO NOTHING used; recommend unique constraint
3. **Production CORS** — Need to configure FRONTEND_URL for production origins

---

## Recommendations

### Immediate (Required for v1)

1. **Automate entity seeding** — Add to `main.py` lifespan:
   ```python
   @asynccontext_manager
   async def lifespan(app: FastAPI):
       # Create tables
       await Base.metadata.create_all(engine)

       # Seed entities (add this)
       async with AsyncSessionLocal() as session:
           await seed_entities(session)

       # Setup scheduler
       setup_jobs()
       scheduler.start()
   ```

2. **Add entity validation** — Check entity exists in jobs:
   ```python
   entity = await get_entity_id_by_name(canonical_name, db_session)
   if not entity:
       logger.warning(f"Entity {canonical_name} not found, skipping")
       continue
   ```

### Short-term (Nice to have)

1. **Helpful empty DB message** — API should return informative error:
   ```python
   if not entities:
       raise HTTPException(
           status_code=503,
           detail="Database not initialized. Please run seed_entities script."
       )
   ```

2. **Automatic migrations** — Run `alembic upgrade head` on startup if needed

### Long-term (Future)

1. **Unique constraint on time-series** — Add `UNIQUE(entity_id, timestamp, period)`
2. **Entity existence validation** — Add database-level check constraints
3. **Health check for entities** — `/health/entities` endpoint to verify seeding

---

## Next Steps

**Option A: Complete milestone with tech debt**
- Accept entity seeding gap as known limitation
- Document manual seeding in README
- Track in backlog for v1.1
- Run `/gsd:complete-milestone v1`

**Option B: Plan gap closure phase**
- Create Phase 1.1 (or 4) to automate entity seeding
- Add validation and error handling
- Ensure full E2E flow works
- Run `/gsd:plan-milestone-gaps`

---

## Appendix: Test Commands

**Verify entity seeding (manual):**
```bash
cd backend
python3 scripts/seed_entities.py
```

**Test API (after seeding):**
```bash
# Health checks
curl http://localhost:8000/health
curl http://localhost:8000/health/scheduler

# Entity endpoints
curl http://localhost:8000/entities
curl http://localhost:8000/entities/1/sentiment?period=daily&limit=10
```

**Test ingestion (requires ASKNEWS_API_KEY):**
```bash
# Start Docker
docker-compose up -d

# Check logs for job execution
docker-compose logs -f backend

# Verify data in /entities endpoint
curl http://localhost:8000/entities
```

---

_Audit completed: 2026-02-05 15:00 UTC_
_Audited by: Claude Code (gsd-integration-checker)_
_Milestone: v1 (Backend data pipeline and API)_
