# Plan 05-02 Summary: AskNews Removal — Delete Files, Clean Dependencies, Update Pipeline

## What Was Built/Removed
- **4 files deleted**: asknews_client.py, news_job.py, stories_job.py (committed); run_stories_job.py (was untracked)
- **requirements.txt**: Removed asknews, tenacity, structlog. Added pgvector==0.3.6. Upgraded httpx 0.25.2 → 0.28.1
- **7 files cleaned** of AskNews/structlog references:
  - scheduler.py: standard logging, setup_jobs() placeholder, job wrappers removed
  - storage_service.py: stubbed (Article functions removed)
  - deduplication_service.py: kept compute_content_hash(), removed Article-specific functions
  - sentiment_service.py: stubbed (AskNews sentiment removed)
  - entity_service.py: kept get_entity_id_by_name(), removed normalize_entity_name()
  - constants.py: removed ENTITY_NAMES/ENTITY_VARIATIONS, added VALID_ASPECTS + score bounds
  - admin.py: removed trigger endpoints, kept router

## Key Decisions
- Removed `normalize_entity_name()` entirely rather than keeping as stub — its dependency `ENTITY_VARIATIONS` was removed from constants.py, making the function non-functional. Phase 6 will implement new entity recognition.
- Renamed `compute_url_hash()` to `compute_content_hash()` to match new schema terminology
- `get_job_health()` emptied its job_configs dict — will be repopulated in Phase 6

## Verification Results
- Zero import references to asknews/structlog/tenacity/news_job/stories_job in backend/ Python files: PASS
- requirements.txt clean (no asknews/tenacity/structlog, has pgvector + httpx 0.28.1): PASS
- VALID_ASPECTS and CURATED_ENTITIES present in constants.py: PASS
- bun test: 1/1 pass
- bun run build: success

## Files Modified
- `backend/requirements.txt` — dependency cleanup
- `backend/pipeline/clients/asknews_client.py` — DELETED
- `backend/pipeline/jobs/news_job.py` — DELETED
- `backend/pipeline/jobs/stories_job.py` — DELETED
- `backend/run_stories_job.py` — DELETED (was untracked)
- `backend/pipeline/scheduler.py` — AskNews jobs removed, structlog → logging
- `backend/pipeline/services/storage_service.py` — stubbed
- `backend/pipeline/services/deduplication_service.py` — Article funcs removed
- `backend/pipeline/services/sentiment_service.py` — stubbed
- `backend/pipeline/services/entity_service.py` — ENTITY_VARIATIONS dependency removed
- `backend/utils/constants.py` — VALID_ASPECTS added, AskNews constants removed
- `backend/api/routes/admin.py` — trigger endpoints removed

## Metrics
- Tasks completed: 2
- Tests added: 0
- Lines of code removed: ~785
- Lines of code added: ~65
