# Architecture Research: v2.0 Integration

**Domain:** Python FastAPI backend — adding 5 free data source collectors, two-tier sentiment pipeline, relevance filtering, and aspect-level sentiment to existing VibeCheck v1.0
**Researched:** 2026-02-19
**Confidence:** MEDIUM-HIGH (integration patterns HIGH, RoBERTa memory constraints on Render HIGH, ABSA library selection MEDIUM)

---

## Context: What Exists in v1.0

The v1.0 codebase uses this pipeline pattern:

```
APScheduler → jobs/ (news_job, stories_job)
                ↓
          clients/ (asknews_client)   ← REPLACING
                ↓
          services/ (sentiment_service, storage_service, deduplication_service, entity_service)
                ↓
          PostgreSQL: entities, articles, sentiment_timeseries, scheduler_execution_log
```

The v2.0 work replaces `asknews_client` with 5 new collectors, adds an own-sentiment pipeline, and keeps the same APScheduler + PostgreSQL infrastructure.

---

## v2.0 System Overview

```
┌────────────────────────────────────────────────────────────────────────┐
│                          Frontend (Vite/React)                         │
│                  (new: source breakdown, aspect tabs)                  │
└─────────────────────────────┬──────────────────────────────────────────┘
                              │ REST API (unchanged endpoints + new ones)
                              ▼
┌────────────────────────────────────────────────────────────────────────┐
│                       FastAPI (Uvicorn)                                │
│  api/routes/entities.py  (MODIFIED: add source_breakdown, aspects)    │
│  api/routes/posts.py     (NEW: raw post feed endpoint)                 │
└──────────────────────────────┬─────────────────────────────────────────┘
                               │
       ┌───────────────────────┴───────────────────────┐
       │ SQLAlchemy async ORM (unchanged)               │
       ▼                                                ▼
┌──────────────┐                              ┌─────────────────────────┐
│  PostgreSQL  │                              │  APScheduler (in-proc)  │
│  (modified   │                              │  (new jobs added)       │
│   schema)    │                              └──────────┬──────────────┘
└──────────────┘                                         │
                              ┌──────────────────────────┴──────────────────────┐
                              │              pipeline/                           │
                              │                                                  │
                 ┌────────────┴────────────┐    ┌───────────────────────────────┤
                 │  jobs/ (MODIFIED+NEW)   │    │  services/ (MODIFIED+NEW)     │
                 │  - collection_job.py    │    │  - relevance_filter.py  (NEW) │
                 │    (replaces news_job,  │    │  - roberta_service.py   (NEW) │
                 │     stories_job)        │    │  - llm_service.py       (NEW) │
                 │  - sentiment_job.py     │    │  - aspect_service.py    (NEW) │
                 │    (NEW: run own NLP)   │    │  - storage_service.py (MOD)   │
                 │  - aggregation_job.py   │    │  - dedup_service.py   (KEPT)  │
                 │    (NEW: rollups)       │    │  - entity_service.py  (KEPT)  │
                 └────────────┬────────────┘    └───────────────────────────────┘
                              │
                 ┌────────────┴────────────────────────────────────────────────┐
                 │  clients/ (REPLACED + ADDED)                               │
                 │  - hn_client.py        (NEW: HN Algolia API)               │
                 │  - reddit_client.py    (NEW: asyncpraw)                    │
                 │  - discourse_client.py (NEW: httpx + REST)                 │
                 │  - github_client.py    (NEW: httpx + GitHub API)           │
                 │  - devto_client.py     (NEW: httpx + Dev.to API)           │
                 │  [asknews_client.py removed or disabled]                   │
                 └────────────────────────────────────────────────────────────┘
```

---

## Component Boundaries

### New vs Modified vs Kept

| Component | Status | Location | Change |
|-----------|--------|----------|--------|
| `asknews_client.py` | REMOVE | `pipeline/clients/` | Replaced by 5 collectors |
| `news_job.py` | REPLACE | `pipeline/jobs/` | Replaced by `collection_job.py` |
| `stories_job.py` | REPLACE | `pipeline/jobs/` | Replaced by `collection_job.py` |
| `sentiment_service.py` | REPLACE | `pipeline/services/` | Was AskNews-specific; replace with RoBERTa pipeline |
| `storage_service.py` | MODIFY | `pipeline/services/` | Adapt to new `posts` table |
| `deduplication_service.py` | KEEP | `pipeline/services/` | URL hash logic still valid |
| `entity_service.py` | KEEP | `pipeline/services/` | Entity normalization still valid |
| `scheduler.py` | MODIFY | `pipeline/` | Add new job registrations |
| `entities.py` (route) | MODIFY | `api/routes/` | Add source breakdown, aspects |
| `models.py` | MODIFY | `db/` | New tables, keep existing |
| HN client | NEW | `pipeline/clients/hn_client.py` | |
| Reddit client | NEW | `pipeline/clients/reddit_client.py` | |
| Discourse client | NEW | `pipeline/clients/discourse_client.py` | |
| GitHub client | NEW | `pipeline/clients/github_client.py` | |
| Dev.to client | NEW | `pipeline/clients/devto_client.py` | |
| `collection_job.py` | NEW | `pipeline/jobs/` | Orchestrates all 5 collectors |
| `sentiment_job.py` | NEW | `pipeline/jobs/` | Runs RoBERTa + LLM tier on new posts |
| `aggregation_job.py` | NEW | `pipeline/jobs/` | Recomputes sentiment_timeseries rollups |
| `relevance_filter.py` | NEW | `pipeline/services/` | Keyword/embedding-based relevance |
| `roberta_service.py` | NEW | `pipeline/services/` | Tier-1 RoBERTa inference |
| `llm_service.py` | NEW | `pipeline/services/` | Tier-2 hosted LLM calls (fallback/augment) |
| `aspect_service.py` | NEW | `pipeline/services/` | Aspect-level sentiment extraction |
| `posts.py` (route) | NEW | `api/routes/` | Raw post feed |

---

## Schema Migration Strategy

### Keep Existing Tables, Add New Ones

The `entities` and `sentiment_timeseries` tables are well-structured and continue to serve the API layer. The `articles` table becomes the model for a new `posts` table that handles all 5 sources.

**Do not delete `articles` — rename and extend it via migration.**

```
MIGRATION PLAN (Alembic):

Migration 001: Rename articles → posts (or add new posts table, copy data)
Migration 002: Add source_type column to posts (hn, reddit, discourse, github, devto)
Migration 003: Add content_text column (for NLP — was absent in v1)
Migration 004: Add relevance_score column (float, nullable)
Migration 005: Add roberta_score column (float, nullable)
Migration 006: Create post_entity_mentions table (many-to-many: posts ↔ entities)
Migration 007: Create aspect_sentiments table
Migration 008: Add source_breakdown JSONB column to sentiment_timeseries
```

### New Table: `posts` (replaces `articles`)

```sql
CREATE TABLE posts (
    id            INTEGER PRIMARY KEY,
    external_id   VARCHAR(255) UNIQUE NOT NULL,  -- source-specific ID
    source_type   VARCHAR(20) NOT NULL,           -- 'hn', 'reddit', 'discourse', 'github', 'devto'
    title         VARCHAR(500),
    content_text  TEXT,                           -- body text for NLP (NEW — was absent)
    url           TEXT UNIQUE NOT NULL,
    url_hash      VARCHAR(64) NOT NULL,
    source_name   VARCHAR(255),                   -- subreddit, forum name, etc.
    published_at  TIMESTAMP WITH TIME ZONE NOT NULL,

    -- Sentiment pipeline columns (filled in later by sentiment_job)
    relevance_score   FLOAT,                      -- 0-1, NULL = not yet scored
    roberta_score     FLOAT,                      -- tier-1 sentiment (-1 to 1)
    final_score       FLOAT,                      -- tier-2 or fallback to roberta_score
    sentiment_method  VARCHAR(20),                -- 'roberta' or 'llm'

    created_at    TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indices
CREATE INDEX ix_posts_published_at ON posts(published_at DESC);
CREATE INDEX ix_posts_source_type ON posts(source_type);
CREATE INDEX ix_posts_url_hash ON posts(url_hash);
CREATE INDEX ix_posts_relevance ON posts(relevance_score) WHERE relevance_score IS NOT NULL;
```

### New Table: `post_entity_mentions` (replaces title-search approach)

```sql
-- v1 did ILIKE '%entity_name%' on article titles — brittle and slow.
-- v2 uses a proper junction table populated by the entity tagger.
CREATE TABLE post_entity_mentions (
    post_id    INTEGER REFERENCES posts(id) ON DELETE CASCADE,
    entity_id  INTEGER REFERENCES entities(id),
    mention_score FLOAT,  -- confidence of the mention (0-1)
    PRIMARY KEY (post_id, entity_id)
);

CREATE INDEX ix_pem_entity_id ON post_entity_mentions(entity_id);
```

### New Table: `aspect_sentiments`

```sql
CREATE TABLE aspect_sentiments (
    id          INTEGER PRIMARY KEY,
    post_id     INTEGER REFERENCES posts(id) ON DELETE CASCADE,
    entity_id   INTEGER REFERENCES entities(id),
    aspect      VARCHAR(100) NOT NULL,   -- e.g., 'speed', 'accuracy', 'pricing'
    sentiment   FLOAT NOT NULL,          -- -1 to 1
    confidence  FLOAT,
    created_at  TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX ix_as_entity_aspect ON aspect_sentiments(entity_id, aspect);
```

### Modified: `sentiment_timeseries`

Add `source_breakdown` JSONB to hold per-source sentiment without schema changes per new source:

```sql
ALTER TABLE sentiment_timeseries ADD COLUMN source_breakdown JSONB;
-- Example value: {"hn": 0.3, "reddit": 0.1, "github": -0.1, "devto": 0.4}
```

The existing `reddit_sentiment` and `reddit_thread_count` columns become redundant but can remain for v1 backward compatibility. Zero downtime migration: populate `source_breakdown` in new jobs, read both in API.

---

## Data Flow Changes

### v2.0 Ingestion Flow

```
APScheduler fires collection_job (every 30 min, replaces 15+60 min)
    ↓
collection_job.py orchestrates all 5 clients concurrently:
    ├── HNClient.fetch_recent(entities)     → posts
    ├── RedditClient.fetch_recent(entities) → posts
    ├── DiscourseClient.fetch_recent()      → posts
    ├── GitHubClient.fetch_recent(entities) → posts
    └── DevToClient.fetch_recent(entities)  → posts
    ↓
deduplication_service.batch_check_duplicates(all_posts) [KEPT]
    ↓
storage_service.batch_insert_posts(new_posts) [MODIFIED for posts table]
    ↓ (queues new post IDs or marks posts as pending_sentiment)

APScheduler fires sentiment_job (every 60 min, or shortly after collection_job)
    ↓
sentiment_job fetches posts WHERE roberta_score IS NULL AND relevance_score IS NULL
    ↓
relevance_filter.score_batch(posts, entities)
    ↓ (filters out low-relevance posts — skip NLP if relevance < 0.3)
roberta_service.score_batch(relevant_posts)    [Tier 1 — fast]
    ↓
llm_service.augment_ambiguous(posts_needing_tier2)  [Tier 2 — selective]
    ↓
entity_tagger.tag_posts(posts)                 [populate post_entity_mentions]
    ↓
aspect_service.extract_aspects(high_confidence_posts)  [optional, expensive]
    ↓
storage_service.update_sentiment_scores(posts) [UPDATE posts, INSERT aspects]
    ↓

APScheduler fires aggregation_job (every 60 min, after sentiment_job)
    ↓
Recomputes sentiment_timeseries rollups from posts + post_entity_mentions
    ↓
Writes updated sentiment_timeseries rows (upsert by entity_id + timestamp + period)
```

### v2.0 API Flow (Frontend)

```
GET /api/entities/{id}/sentiment?source=hn&start=...&end=...
    ↓
Reads sentiment_timeseries.source_breakdown JSONB
    ↓
Returns breakdown: { overall: 0.2, hn: 0.3, reddit: 0.1, ... }

GET /api/entities/{id}/aspects
    ↓
Reads aspect_sentiments for entity
    ↓
Returns: [{ aspect: "speed", sentiment: 0.4 }, { aspect: "pricing", sentiment: -0.2 }]

GET /api/posts?entity_id=...&source=reddit&limit=20
    ↓
Reads posts via post_entity_mentions (no more ILIKE on title)
    ↓
Returns raw posts with sentiment_score, source_type
```

---

## New Component Details

### 1. Data Source Clients (`pipeline/clients/`)

All clients follow the same interface so `collection_job.py` can call them uniformly:

```python
# Common interface (informal — not enforced by ABC, just by convention)
async def fetch_recent(entity_names: list[str], since_hours: int = 24) -> list[PostDict]:
    ...
```

**HN Client (`hn_client.py`):**
- Uses `https://hn.algolia.com/api/v1/search` (free, no auth, no rate limit docs but reasonable)
- Query: `q="{entity_name}"&tags=story,comment&numericFilters=created_at_i>{since_ts}`
- Use `httpx.AsyncClient` — no library needed (Algolia API is simple JSON)
- Confidence: HIGH — HN Algolia API is stable and well-documented

**Reddit Client (`reddit_client.py`):**
- Use `asyncpraw` (official async wrapper, maintained by praw-dev)
- Read-only mode: `asyncpraw.Reddit(client_id, client_secret, user_agent)`
- Search `r/MachineLearning`, `r/LocalLLaMA`, `r/artificial` etc. by entity name
- Rate limits handled automatically by asyncpraw
- Confidence: HIGH — asyncpraw is the established solution for async Reddit access

**Discourse Client (`discourse_client.py`):**
- Target: discuss.huggingface.co, community.openai.com, forums.fast.ai
- Use `httpx.AsyncClient` with pagination (returns 20 posts/page)
- No auth needed for public forums; add `Api-Key` header if forums require it
- Query: `GET /search.json?q={entity_name}&order=latest`
- Confidence: MEDIUM — each Discourse forum may have slightly different config

**GitHub Client (`github_client.py`):**
- Target: issues and discussions for major AI repos (pytorch, transformers, etc.)
- Use `httpx.AsyncClient` with `Authorization: Bearer {GITHUB_TOKEN}` header
- Unauthenticated: 60 req/hour. Authenticated: 5000 req/hour — token required for useful throughput
- Search API: `GET /search/issues?q={entity}+repo:huggingface/transformers`
- Confidence: HIGH — GitHub Search API is stable

**Dev.to Client (`devto_client.py`):**
- Use `https://dev.to/api/articles?tag={entity}&per_page=30`
- No auth for read access; optional `api-key` header for higher rate limits
- Use `httpx.AsyncClient`
- Confidence: HIGH — Dev.to API is well-documented and stable

### 2. Two-Tier Sentiment Pipeline

**Tier 1: RoBERTa (`roberta_service.py`)**

```python
# Load once at startup (NOT per-request — expensive)
# Use cardiffnlp/twitter-roberta-base-sentiment-latest (156MB model)
# Run via loop.run_in_executor() — transformers inference is CPU-bound (blocking)

from transformers import pipeline as hf_pipeline
import asyncio

_sentiment_pipeline = None  # lazy init at first use

async def score_batch(texts: list[str]) -> list[float]:
    global _sentiment_pipeline
    if _sentiment_pipeline is None:
        loop = asyncio.get_event_loop()
        _sentiment_pipeline = await loop.run_in_executor(
            None, lambda: hf_pipeline("sentiment-analysis", model="cardiffnlp/twitter-roberta-base-sentiment-latest")
        )
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(None, lambda: _sentiment_pipeline(texts, truncation=True))
    # Map label to float: LABEL_2 (positive)=+1, LABEL_1 (neutral)=0, LABEL_0 (negative)=-1
    ...
```

**CRITICAL — Render memory constraint:** The `cardiffnlp/twitter-roberta-base-sentiment-latest` model is ~500MB on disk but requires ~700-900MB RAM when loaded. Render's free tier is 512MB RAM — this WILL fail. Minimum requirement: Render Starter plan ($7/mo) with 512MB RAM shared, or Standard ($25/mo) with 2GB RAM.

Recommend: Use Render Standard plan (2GB RAM) for the web service when RoBERTa is loaded. Alternatively, use ONNX-converted model via `onnxruntime` to reduce memory to ~300MB. Document this constraint explicitly in PITFALLS.md.

**Tier 2: Hosted LLM (`llm_service.py`)**

Use for ambiguous cases where RoBERTa confidence is low (< 0.7) or for aspect extraction:
- Groq API (fast, free tier) or OpenAI GPT-4o-mini (cheap per-token)
- Call via `httpx.AsyncClient` — no SDK needed
- Prompt: "Rate the sentiment toward {entity} in this text. Return JSON: {score: float -1 to 1, reasoning: str}"
- Only call for ~10-20% of posts (ambiguous ones) to keep costs low
- Confidence: HIGH — standard pattern for two-tier NLP pipelines

### 3. Relevance Filter (`relevance_filter.py`)

Before spending RoBERTa inference on a post, check relevance to entities:

```python
# Simple approach (v2.0): keyword matching with fuzzy variants
# Example: "GPT-4" also matches "gpt4", "gpt 4", "openai gpt"
# This avoids loading an embedding model (too expensive in memory)

ENTITY_ALIASES = {
    "GPT-4": ["gpt-4", "gpt4", "gpt 4"],
    "Claude": ["claude", "claude 3", "anthropic claude"],
    ...
}

def score_relevance(text: str, entity_name: str) -> float:
    aliases = ENTITY_ALIASES.get(entity_name, [entity_name.lower()])
    text_lower = text.lower()
    # Returns 1.0 if exact match, 0.5 if partial, 0.0 if none
    ...
```

This is synchronous and cheap — no GPU/model needed. Can run before storage to avoid saving irrelevant posts entirely.

### 4. Aspect-Level Sentiment (`aspect_service.py`)

Use `cardiffnlp/twitter-roberta-base-sentiment-latest` with text-pair approach, or DeBERTa v3 for true ABSA:

```python
# DeBERTa ABSA model: yangheng/deberta-v3-base-absa-v1.1
# Input: (text, aspect_term) pair
# Output: positive/neutral/negative per aspect

TRACKED_ASPECTS = ["speed", "accuracy", "pricing", "safety", "context_window", "coding", "api"]

async def extract_aspects(post_text: str, entity_name: str) -> list[AspectResult]:
    for aspect in TRACKED_ASPECTS:
        result = absa_classifier(post_text, text_pair=aspect)
        ...
```

**Memory concern:** DeBERTa v3 base is ~900MB in RAM. Loading BOTH RoBERTa and DeBERTa simultaneously on Render is infeasible without a 4GB+ instance. Strategy: run aspect extraction in a separate, infrequent batch job (daily), or use the same RoBERTa model with a simpler aspect extraction approach. Defer to phase research.

### 5. Collection Job (`collection_job.py`)

Replaces both `news_job.py` and `stories_job.py`:

```python
async def collect_posts_job(db_session: AsyncSession) -> dict:
    """Concurrent fetch from all 5 sources, deduplicate, store."""
    tasks = [
        hn_client.fetch_recent(ENTITY_NAMES),
        reddit_client.fetch_recent(ENTITY_NAMES),
        discourse_client.fetch_recent(),
        github_client.fetch_recent(ENTITY_NAMES),
        devto_client.fetch_recent(ENTITY_NAMES),
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    # Flatten, deduplicate, store
    ...
```

Use `return_exceptions=True` so one failing source doesn't abort all others — matching v1.0's per-entity error isolation pattern.

---

## Job Schedule Changes

| Job | v1.0 | v2.0 | Reason |
|-----|------|------|--------|
| `poll_news` (every 15 min) | REMOVE | — | Replaced by collection_job |
| `poll_stories` (every 60 min) | REMOVE | — | Replaced by collection_job |
| `collection_job` | NEW | every 30 min | Collects from all 5 sources |
| `sentiment_job` | NEW | every 60 min | Runs NLP on new posts |
| `aggregation_job` | NEW | every 60 min (offset +15 min from sentiment_job) | Recomputes timeseries rollups |

The `scheduler.py` `setup_jobs()` function needs to register 3 new jobs and unregister 2 old ones.

---

## Suggested Build Order (with Dependencies)

### Phase 1: Schema Migration (PREREQUISITE FOR ALL)
**Why first:** All new components write to new tables. Nothing else can proceed without the schema.

```
1. Alembic migration: add posts table (keep articles for now)
2. Alembic migration: add post_entity_mentions table
3. Alembic migration: add source_breakdown to sentiment_timeseries
4. Alembic migration: add aspect_sentiments table
5. Update db/models.py with new SQLAlchemy models
```

**Dependency:** None. Must complete before Phase 2.

### Phase 2: Data Source Clients (CAN PARALLELIZE)
**Why second:** Need raw data before pipeline can process it.

```
2a. hn_client.py (simplest — no auth, plain httpx)
2b. devto_client.py (simple — no auth, REST)
2c. reddit_client.py (asyncpraw — need API credentials)
2d. github_client.py (httpx — need GitHub token)
2e. discourse_client.py (httpx — may need forum-specific config)
```

**Dependency:** Phase 1 (models must exist to store test data).
**Parallelizable:** 2a through 2e can be built independently.

### Phase 3: Collection Job + Storage Integration
**Why third:** Wire clients into the scheduler pattern.

```
3a. collection_job.py (orchestrates all 5 clients)
3b. Modify storage_service.py for posts table
3c. Update scheduler.py: remove old jobs, add collection_job
3d. Test: verify posts appear in DB from each source
```

**Dependency:** Phase 1 + Phase 2.

### Phase 4: Relevance Filter
**Why fourth:** Filter junk before sentiment pipeline processes it.

```
4a. relevance_filter.py (keyword-based, synchronous)
4b. Wire into collection_job: filter before storage OR tag relevance_score on ingest
4c. Update post_entity_mentions population
```

**Dependency:** Phase 3.

### Phase 5: Tier-1 Sentiment (RoBERTa)
**Why fifth:** Core of the new pipeline.

```
5a. roberta_service.py (load model, score_batch function)
5b. Run in executor (avoid blocking async loop)
5c. sentiment_job.py (fetches unscored posts, runs roberta_service)
5d. Update scheduler.py: add sentiment_job (every 60 min)
5e. Test on Render: verify memory fits within plan limits
```

**Dependency:** Phase 3 + Phase 4. This is the most technically risky step — validate Render memory before building more.

### Phase 6: Aggregation Job + API Updates
**Why sixth:** Only useful once sentiment scores exist in posts.

```
6a. aggregation_job.py (recomputes sentiment_timeseries from posts)
6b. Populate source_breakdown JSONB in sentiment_timeseries
6c. Modify entities.py route: expose source_breakdown in response
6d. Add posts.py route: GET /api/posts?entity_id=...&source=...
6e. Update scheduler.py: add aggregation_job
```

**Dependency:** Phase 5.

### Phase 7: Tier-2 LLM + Aspect Sentiment (OPTIONAL, DEFERRABLE)
**Why last:** Optional enhancement — app is fully functional without it.

```
7a. llm_service.py (Groq or OpenAI for ambiguous posts)
7b. Wire into sentiment_job: call LLM for low-confidence RoBERTa results
7c. aspect_service.py (DeBERTa ABSA — research memory feasibility first)
7d. aspect_sentiments population in sentiment_job or separate job
7e. New API endpoint: GET /api/entities/{id}/aspects
```

**Dependency:** Phase 5. Research memory constraints before committing to DeBERTa loading.

### Phase 8: Frontend Evolution
**Why last:** Backend data must exist before frontend can display it.

```
8a. Source breakdown selector (hn/reddit/etc. toggle)
8b. Aspect sentiment tab component
8c. Update existing mention feed to use post_entity_mentions (no more ILIKE)
```

**Dependency:** Phase 6.

---

## Integration Points with Existing Code

### What Existing Code Touches (Must Not Break)

| Existing Code | Used By | Impact |
|---------------|---------|--------|
| `Entity` model | All routes + all jobs | Keep unchanged |
| `SentimentTimeseries` model | `entities.py` route | Keep + add `source_breakdown` nullable column |
| `deduplication_service` | `storage_service` | Keep as-is; update caller to pass post dicts |
| `entity_service.normalize_entity_name()` | `storage_service` | Keep as-is |
| `SchedulerExecutionLog` | `scheduler.py` | Keep as-is; new jobs auto-use it via `wrapped_job_execution` |
| `wrapped_job_execution()` | `scheduler.py` | Keep as-is; new jobs wrap the same way |

### What Is Safe to Delete After Migration

- `pipeline/clients/asknews_client.py` — once collection_job is running
- `pipeline/jobs/news_job.py` — once collection_job is running
- `pipeline/jobs/stories_job.py` — once collection_job is running
- `articles` table — after data is migrated to `posts` and no API routes reference it

**Strategy:** Keep `articles` table and `Article` model during v2.0 development. Only remove after confirming `posts` table has sufficient historical data (or backfill).

### articles → posts Migration Approach

Two options:

**Option A (Recommended): Parallel tables, then migrate**
- Create `posts` table alongside `articles`
- New collection jobs write to `posts`
- API routes progressively shift from `articles` to `posts`
- Drop `articles` in a later milestone after verifying coverage

**Option B: Rename and extend**
- `alembic op.rename_table('articles', 'posts')`
- Add `source_type` column (default `'news'` for existing rows)
- Simpler schema but requires updating ALL references in one migration

**Recommendation:** Option A. Lower risk — existing v1.0 queries still work. Option B is brittle during migration.

---

## Render Deployment Constraints

These are hard constraints for v2.0:

| Constraint | Detail | Mitigation |
|------------|--------|------------|
| Free tier: 512MB RAM | RoBERTa needs ~700-900MB | Upgrade to Standard ($25/mo, 2GB RAM) |
| Model download time | ~500MB download on first start | Pre-download in Dockerfile build step (`RUN python -c "from transformers import pipeline..."`) |
| Cold start delay | Model loading takes 5-15s | Load model lazily on first sentiment_job run, not on API startup |
| Docker image size | transformers + torch balloons to 4-6GB | Use `--no-cache-dir` pip flag, consider ONNX conversion (reduces to ~300MB) |
| DeBERTa + RoBERTa together | ~1.8GB RAM combined | Only load one model at a time, or use ONNX for both |
| No GPU on Render | CPU-only inference | RoBERTa on CPU: ~1-3s per batch of 10 — acceptable for batch jobs |

**Practical recommendation:** Load RoBERTa once when `sentiment_job` starts, process the batch, then let Python GC reclaim. Do NOT load the model at FastAPI startup (wastes memory for the entire API uptime).

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Loading ML Models at FastAPI Startup

**What people do:** Add model loading to `@app.on_event("startup")` so it's always ready.

**Why it's wrong:** The model consumes 700-900MB RAM for the entire lifetime of the API process, including when no sentiment job is running (most of the time). On Render's 2GB instance, this leaves only 1.1GB for everything else.

**Do this instead:** Load the model lazily inside `sentiment_job.py` — only when the job runs. Unload via `del model; gc.collect()` after the batch completes if memory is tight.

### Anti-Pattern 2: Synchronous ML Inference in Async Job

**What people do:** Call `pipeline(texts)` directly in an async function.

**Why it's wrong:** Hugging Face `pipeline()` is CPU-bound and blocks the event loop, freezing all other async tasks (including API request handling).

**Do this instead:** Use `await loop.run_in_executor(None, lambda: pipeline(texts))` to offload to a thread pool.

### Anti-Pattern 3: One Request Per Post to LLM Tier

**What people do:** `for post in ambiguous_posts: await llm_service.score(post)` — serial calls.

**Why it's wrong:** 100 ambiguous posts × 1s LLM latency = 100s per sentiment job run.

**Do this instead:** Batch LLM calls using `asyncio.gather()` with a semaphore to limit concurrency (avoid rate limit errors):

```python
semaphore = asyncio.Semaphore(5)  # max 5 concurrent LLM calls
async def score_with_limit(post):
    async with semaphore:
        return await llm_service.score(post)
results = await asyncio.gather(*[score_with_limit(p) for p in ambiguous_posts])
```

### Anti-Pattern 4: Ignoring Rate Limits per Source

**What people do:** Fetch as many posts as possible from each source, ignoring API limits.

**Why it's wrong:** HN Algolia: undocumented limits. Reddit (asyncpraw): auto-handled but real. GitHub: 5000/hr authenticated. Dev.to: 1000/hr. Discourse: varies by forum.

**Do this instead:** Implement per-client `since_hours` windowing (only fetch recent posts) and use the existing `deduplication_service` to avoid re-processing. Add per-client configurable rate limiting via `httpx` retry logic.

### Anti-Pattern 5: Blocking Posts Table with Long Migrations

**What people do:** `ALTER TABLE articles ADD COLUMN content_text TEXT` on a large production table.

**Why it's wrong:** On PostgreSQL, `ADD COLUMN` with default NULL is instant, but adding NOT NULL with a default requires table rewrite — can lock the table for minutes.

**Do this instead:** Always add new columns as `NULLABLE` first. Backfill. Add constraints in a separate migration after backfill.

### Anti-Pattern 6: ILIKE Entity Matching (Continuing v1 Pattern)

**What people do:** Continue using `Article.title.ilike(f"%{entity_name}%")` for the new posts table.

**Why it's wrong:** Does not handle aliases ("gpt4" vs "gpt-4"), is slow without full-text index, and misses body text mentions.

**Do this instead:** Populate `post_entity_mentions` table during ingestion using `relevance_filter.py` alias matching. Query via JOIN instead of ILIKE.

---

## Directory Structure (v2.0 additions highlighted)

```
backend/
├── main.py
├── config.py                          # MODIFY: add LLM keys, GitHub token
├── requirements.txt                   # MODIFY: add asyncpraw, transformers, torch
│
├── api/
│   ├── routes/
│   │   ├── entities.py               # MODIFY: add source_breakdown, aspects
│   │   ├── posts.py                  # NEW: raw post feed
│   │   └── health.py
│   └── schemas/
│       ├── entity.py                 # MODIFY: add source_breakdown fields
│       └── post.py                   # NEW
│
├── db/
│   ├── models.py                     # MODIFY: add Post, PostEntityMention, AspectSentiment
│   ├── session.py
│   └── migrations/
│       └── versions/                 # NEW: 4-8 migration files
│
└── pipeline/
    ├── scheduler.py                  # MODIFY: replace old jobs, add 3 new
    ├── jobs/
    │   ├── news_job.py               # REMOVE after migration
    │   ├── stories_job.py            # REMOVE after migration
    │   ├── collection_job.py         # NEW
    │   ├── sentiment_job.py          # NEW
    │   └── aggregation_job.py        # NEW
    ├── clients/
    │   ├── asknews_client.py         # REMOVE after migration
    │   ├── hn_client.py              # NEW
    │   ├── reddit_client.py          # NEW
    │   ├── discourse_client.py       # NEW
    │   ├── github_client.py          # NEW
    │   └── devto_client.py           # NEW
    └── services/
        ├── sentiment_service.py      # REMOVE (was AskNews-specific)
        ├── storage_service.py        # MODIFY for posts table
        ├── deduplication_service.py  # KEEP
        ├── entity_service.py         # KEEP
        ├── relevance_filter.py       # NEW
        ├── roberta_service.py        # NEW
        ├── llm_service.py            # NEW
        └── aspect_service.py         # NEW (Phase 7)
```

---

## Confidence Assessment

| Area | Confidence | Reason |
|------|-----------|--------|
| Client integration pattern | HIGH | Standard httpx async pattern, well-established |
| asyncpraw for Reddit | HIGH | Official async library, maintained by praw-dev |
| HN Algolia API | HIGH | Stable, no auth needed, JSON API |
| RoBERTa memory on Render | HIGH | Memory math is clear — free tier insufficient |
| DeBERTa ABSA feasibility | MEDIUM | Library exists, but memory co-loading with RoBERTa is risky |
| Schema migration safety | HIGH | Additive-only migrations, parallel table strategy |
| GitHub API rate limits | HIGH | Well-documented, token required |
| Discourse API consistency | MEDIUM | Varies by forum installation/version |
| LLM tier (Groq/OpenAI) | HIGH | Standard API pattern, well-documented |
| Aggregation job correctness | MEDIUM | Need to verify sentiment rollup logic after schema change |

---

## Sources

- asyncpraw documentation: [asyncpraw.readthedocs.io](https://asyncpraw.readthedocs.io)
- HN Algolia API: [hn.algolia.com/api](https://hn.algolia.com/api)
- Hugging Face Transformers + FastAPI deployment: [markaicode.com/serve-transformers-fastapi-rest-api-deployment](https://markaicode.com/serve-transformers-fastapi-rest-api-deployment/)
- PyABSA (ABSA framework): [github.com/yangheng95/PyABSA](https://github.com/yangheng95/PyABSA)
- DeBERTa ABSA model: [yangheng/deberta-v3-base-absa-v1.1 on Hugging Face](https://huggingface.co/yangheng/deberta-v3-base-absa-v1.1)
- Render memory limits: [community.render.com/t/the-free-instance-type-e-g-512mb-ram-0-1-cpu](https://community.render.com/t/the-free-instance-type-e-g-512mb-ram-0-1-cpu/39044)
- Alembic migration best practices: [alembic.sqlalchemy.org/en/latest/ops.html](https://alembic.sqlalchemy.org/en/latest/ops.html)
- Reducing Docker image size for transformer models: [towardsdatascience.com — reducing docker images for LLM](https://towardsdatascience.com/reducing-the-size-of-docker-images-serving-llm-models-b70ee66e5a76/)
- GitHub API rate limits: [docs.github.com/en/rest/rate-limit](https://docs.github.com/en/rest/rate-limit)
- Dev.to API docs: [developers.forem.com/api](https://developers.forem.com/api)

---

*Architecture research for: VibeCheck v2.0 integration of free data sources + sentiment pipeline*
*Researched: 2026-02-19*
