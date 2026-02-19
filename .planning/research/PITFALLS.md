# Pitfalls Research

**Domain:** Brownfield FastAPI + PostgreSQL — adding multi-source data collectors, ML sentiment pipeline, and LLM extraction to existing deployed app
**Researched:** 2026-02-19
**Confidence:** HIGH (verified against official docs, community reports, and Render platform specifics)

---

## Scope

This replaces the v1.0 PITFALLS.md. The v1.0 pitfalls around scheduler reliability, time-series schema, entity matching, and API cost overruns remain relevant but are considered solved for the existing system. This document covers **new failure modes introduced by the v2.0 milestone**: replacing AskNews with free multi-source collectors, adding a two-tier sentiment pipeline (RoBERTa + LLM), and evolving the schema and frontend without breaking what works.

---

## Critical Pitfalls

Mistakes that cause production outages, OOM kills, or complete data loss.

### Pitfall 1: RoBERTa OOM Kills the Render Dyno

**What goes wrong:**

RoBERTa-base requires ~480MB of RAM for model weights alone. FastAPI adds ~50-80MB. Render's starter tier is 512MB. Python runtime overhead pushes total memory use past the limit before any inference runs. The process is killed by the OS with no error message in the application logs — it simply stops responding. Render surfaces this as "service restarted" with no context.

Even on the $7/month Starter plan (512MB), the model cannot be loaded. The Standard plan at $25/month (2GB) is the minimum viable tier for in-process RoBERTa inference.

**Why it happens:**

Developers test the model locally (8-16GB RAM) where it works fine. Render's actual per-dyno memory cap is lower than expected, and Render adds approximately 300MB of overhead above what runs locally. OOM kills do not surface as Python exceptions — they surface as silent restarts.

**How to avoid:**

Option A (recommended for constrained budget): Use DistilRoBERTa instead of RoBERTa-base. DistilRoBERTa is 40% smaller (~300MB) with ~95% of RoBERTa accuracy. Combined with ONNX quantization, runtime memory drops to ~150-200MB.

Option B: Upgrade to Render Standard tier (2GB, $25/month) before attempting to load any transformer model. This is non-negotiable for RoBERTa-base.

Option C: Run sentiment inference as a separate Render background worker service on a larger instance, keeping the FastAPI web service on a smaller tier.

```python
# Prefer DistilRoBERTa + ONNX for constrained environments
# pip install optimum[onnxruntime]
from optimum.onnxruntime import ORTModelForSequenceClassification
from transformers import AutoTokenizer

# Load quantized ONNX model — ~150MB vs ~480MB for full RoBERTa
model = ORTModelForSequenceClassification.from_pretrained(
    "distilroberta-base",
    export=True,
    provider="CPUExecutionProvider"
)
tokenizer = AutoTokenizer.from_pretrained("distilroberta-base")
```

Never load the model inside a request handler. Load once at startup as a module-level singleton. Use `torch.no_grad()` context for all inference to prevent gradient accumulation.

**Warning signs:**

- Render dashboard shows "service restarted" without a Python traceback
- Memory metric climbs to 100% then service disappears
- Model loads fine locally but crashes on first deploy
- Health check endpoint stops responding on startup without error logs

**Phase to address:** Data pipeline phase (whichever phase introduces ML models). Do not add RoBERTa until memory budget is validated.

---

### Pitfall 2: sentence-transformers Embedding Model Causes Memory Exhaustion Over Time

**What goes wrong:**

sentence-transformers (e.g., `all-MiniLM-L6-v2`, ~90MB) initially looks safe on Render. But with repeated inference calls, memory grows continuously due to Python object retention during batch processing — embeddings for all texts in a batch remain in memory until the entire batch is complete. At moderate volume (1,000+ posts/day), the process slowly consumes all available RAM over hours until the dyno is OOM-killed.

**Why it happens:**

The library processes texts in batches internally, and intermediate tensors from earlier items in the batch are not released until the full batch completes. When run in the same process as FastAPI (shared memory space), there is no cleanup boundary between the embedding job and the web server.

**How to avoid:**

1. Process posts in small chunks (batch_size=32 maximum), not all-at-once.
2. Call `torch.cuda.empty_cache()` after each batch (even on CPU, this triggers GC cleanup).
3. Run embedding computation in a separate background worker process, not in the FastAPI web process.
4. Use `model2vec` as a drop-in replacement for `all-MiniLM-L6-v2` — 50x smaller, 500x faster with comparable quality for semantic similarity tasks.

```python
# Safe batched embedding with memory management
import torch

def embed_posts_safe(model, posts: list[str], batch_size: int = 32) -> list:
    all_embeddings = []
    for i in range(0, len(posts), batch_size):
        chunk = posts[i:i + batch_size]
        with torch.no_grad():
            embeddings = model.encode(chunk, convert_to_numpy=True)
        all_embeddings.extend(embeddings)
        # Force cleanup between chunks
        del embeddings
        torch.cuda.empty_cache()  # Works on CPU too — triggers Python GC
    return all_embeddings
```

**Warning signs:**

- Memory grows steadily over 6-12 hours, then service restarts
- Log shows embedding jobs completing successfully but each one takes slightly longer
- RSS memory in Render metrics shows a sawtooth pattern that never fully recovers

**Phase to address:** Relevance filtering / embedding phase. Validate memory profile over a full 24-hour window before marking phase complete.

---

### Pitfall 3: Reddit OAuth App Misconfiguration Blocks All Requests

**What goes wrong:**

Reddit requires OAuth authentication for all API access — unauthenticated requests are rejected, not rate-limited. Using the wrong app type (web app vs. script app) for a server-side scraper causes `invalid_grant` errors on every request. Forgetting to set a valid redirect URI during app registration (even for script apps) causes registration to fail. Using synchronous PRAW inside an async FastAPI application blocks the event loop, causing request timeouts for all concurrent users.

**Why it happens:**

Reddit's OAuth2 setup has three app types with different credential flows. The "script" type (personal use, password flow) is correct for a server-side data collector, but it requires the Reddit account owner's username and password in addition to client_id and client_secret. Using asyncpraw instead of praw is not obvious from documentation. The redirect URI requirement for script apps is confusing since the redirect is never actually used.

**How to avoid:**

1. Register a "script" type app at `https://www.reddit.com/prefs/apps`. Set redirect URI to `http://localhost:8080` (required but never called).
2. Use `asyncpraw` (not `praw`) in async FastAPI contexts. PRAW will log a warning when run in an async environment, but the underlying problem is event loop blocking.
3. Store credentials in environment variables, not code. Required: `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USERNAME`, `REDDIT_PASSWORD`, `REDDIT_USER_AGENT`.
4. User-Agent must follow Reddit's format: `platform:app_id:version (by /u/username)`. Non-compliant user agents are aggressively rate-limited.

```python
import asyncpraw  # NOT praw — use async version for FastAPI

async def create_reddit_client():
    return asyncpraw.Reddit(
        client_id=os.getenv("REDDIT_CLIENT_ID"),
        client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
        username=os.getenv("REDDIT_USERNAME"),
        password=os.getenv("REDDIT_PASSWORD"),
        user_agent="linux:vibecheck:v2.0 (by /u/yourusername)"
    )
```

Rate limit: 100 QPM for authenticated apps. Monitor `X-Ratelimit-Remaining`, `X-Ratelimit-Reset`, `X-Ratelimit-Used` headers.

**Warning signs:**

- `prawcore.OAuthException: invalid_grant` on every request
- 429 responses despite low request volume (wrong user-agent)
- FastAPI becomes unresponsive when Reddit fetching runs (sync PRAW blocking event loop)
- Access tokens not refreshed after 1 hour — subsequent requests fail with auth errors

**Phase to address:** Data collection phase (Reddit collector). Validate auth flow in isolation before connecting to pipeline.

---

### Pitfall 4: Alembic Migration Drops Existing Tables on Brownfield Schema

**What goes wrong:**

When `alembic revision --autogenerate` runs against the existing database, it compares the ORM models to the live schema. If the import path is wrong (empty `target_metadata`), Alembic generates a migration that would **drop all existing tables** rather than detect them. Running `alembic upgrade head` on this migration in production destroys all data. The existing VibeCheck schema has `articles`, `entities`, `sentiment_timeseries`, and `scheduler_execution_log` tables that must be preserved or explicitly migrated.

**Why it happens:**

Alembic's autogenerate only detects tables that are registered in `target_metadata`. If the metadata is populated by a different import path than what `env.py` imports, Alembic sees an empty schema vs. a live schema and generates DROP + CREATE for everything. This is documented but easy to get wrong, especially in Docker environments where import paths differ.

**How to avoid:**

1. Always run `alembic revision --autogenerate` and inspect the generated file before applying it. Never blindly run `alembic upgrade head` on autogenerated migrations.
2. Verify `env.py` imports from the correct module path. In Docker (WORKDIR=/app), imports must not use `backend.` prefix.
3. Create a backup before any migration: `pg_dump $DATABASE_URL > backup_$(date +%Y%m%d).sql`.
4. For the schema transition (AskNews schema → multi-source schema), consider a clean-break migration strategy:
   - Option A (data-preserving): Write explicit ADD COLUMN/CREATE TABLE migrations that keep existing tables and add new ones. New pipeline writes to new tables; old tables archived.
   - Option B (clean break): Drop and recreate schema, accept data loss from AskNews era. Only valid if historical AskNews data has no value.

```python
# env.py — verify this import matches Docker WORKDIR structure
from db.base import Base  # NOT from backend.db.base import Base
from db import models  # Ensure all models are imported, populating Base.metadata

target_metadata = Base.metadata

# Verify metadata has the expected tables before migration
print(f"Tables in metadata: {list(target_metadata.tables.keys())}")
```

**Warning signs:**

- Autogenerated migration file contains `drop_table()` calls for existing tables
- `alembic history` shows a gap between the last applied revision and `head`
- `alembic current` shows `(head)` but schema doesn't match models
- Import errors during `alembic upgrade` that differ from local execution

**Phase to address:** Schema migration phase. This must be the first task in any milestone that changes the database schema. No data pipeline work until migration strategy is validated.

---

### Pitfall 5: Frontend Breakage During Backend Schema Overhaul

**What goes wrong:**

The existing frontend (`src/services/api.ts`, `src/types/api.ts`) makes API calls to endpoints that return the current `articles`/`sentiment_timeseries` schema. The v2.0 pipeline replaces the data source but the frontend still expects the same response shapes. If the backend response changes (field names, nesting structure, null values) before the frontend is updated, the frontend silently breaks — charts show nothing, or worse, show wrong data with no error message.

The existing `entityTransformer.ts` and `trendCalculator.ts` are tightly coupled to the current data shape from `sentiment_timeseries.reddit_sentiment` and `sentiment_timeseries.sentiment_mean` fields. Any change to these field names or the addition of new source types breaks the transformer silently.

**Why it happens:**

Brownfield migrations often change the backend first and the frontend second. The gap between them — even one deployment — can expose broken state to users. The current frontend has no API versioning (`/v1/` prefix), so there is no backward-compatible URL to maintain.

**How to avoid:**

1. Treat the API contract as frozen during migration. Do not change any field names or remove any fields from existing endpoints until both backend and frontend are updated atomically.
2. For new data (multi-source posts, aspect-level sentiment), add **new endpoints** rather than modifying existing ones. The existing `/api/entities`, `/api/sentiment/timeseries` endpoints must continue to return valid data throughout the migration.
3. Use the Expand-Contract pattern: first add new fields alongside old ones, then update the frontend, then remove old fields.
4. Add TypeScript type guards in the frontend that explicitly check for expected fields at runtime, surfacing contract violations as visible errors rather than silent undefined access.

```typescript
// src/types/api.ts — add explicit runtime validation
function assertSentimentTimeseries(data: unknown): SentimentTimeseries {
  if (!data || typeof data !== 'object') {
    throw new Error(`Invalid sentiment timeseries response: ${JSON.stringify(data)}`);
  }
  const d = data as Record<string, unknown>;
  if (typeof d.sentiment_mean !== 'number' && d.sentiment_mean !== null) {
    console.warn('API contract violation: sentiment_mean missing or wrong type', d);
  }
  return data as SentimentTimeseries;
}
```

**Warning signs:**

- Frontend charts show empty state after backend deploy
- `entityTransformer.ts` returns all null/undefined values
- Network tab shows 200 responses but different JSON structure than expected
- TypeScript types pass but runtime values are undefined

**Phase to address:** Every phase that touches API response shapes. Establish an API contract test (even a simple one) that runs before each deployment.

---

## Moderate Pitfalls

Mistakes that cause delays, data quality issues, or operational pain (but not full outages).

### Pitfall 6: HN Algolia Pagination Silently Returns No Results

**What goes wrong:**

The HN Algolia API (`hn.algolia.com/api/v1/search_by_date`) has a hard pagination limit of 1,000 sorted results. Beyond page 10 (with `hitsPerPage=100`), the `nbHits` count may show more results but the API returns an empty `hits` array or results in undefined sort order. When using `numericFilters=created_at_i` for time-window queries, edge cases in the filter syntax can return 0 hits even when results exist — the API returns HTTP 200 with an empty array, not an error.

**Why it happens:**

The API treats sorting guarantees as a performance feature, not a correctness guarantee. Developers assume "200 OK + empty hits = no data" when it may mean "data exists but pagination limit hit."

**How to avoid:**

1. Never paginate beyond page 10 (1,000 results). Instead, narrow the time window and make multiple requests.
2. Use `search_by_date` endpoint with `created_at_i` numeric filters as ISO-unix timestamps, but validate that the filter syntax is correct before deploying.
3. Always check `nbHits` and `nbPages` in the response before assuming a result set is complete.
4. Cache responses for 15-30 minutes to avoid hammering the API (no auth required, but rate limits exist).

```python
async def fetch_hn_posts(query: str, from_ts: int, to_ts: int) -> list[dict]:
    """Fetch HN posts within time window, handling pagination limits."""
    all_hits = []
    page = 0
    max_pages = 10  # Hard limit — Algolia pagination breaks beyond this

    async with httpx.AsyncClient() as client:
        while page < max_pages:
            resp = await client.get(
                "https://hn.algolia.com/api/v1/search_by_date",
                params={
                    "query": query,
                    "tags": "story",
                    "numericFilters": f"created_at_i>{from_ts},created_at_i<{to_ts}",
                    "hitsPerPage": 100,
                    "page": page,
                }
            )
            data = resp.json()
            hits = data.get("hits", [])
            if not hits:
                break
            all_hits.extend(hits)
            if page >= data.get("nbPages", 0) - 1:
                break
            page += 1
            await asyncio.sleep(0.1)  # Polite pacing

    return all_hits
```

**Warning signs:**

- `hits` is empty but `nbHits` is non-zero in the API response
- Fetching "last 7 days" returns data but "last 30 days" returns nothing
- Time-window queries return different result counts on retry with identical parameters

**Phase to address:** HN data collector phase.

---

### Pitfall 7: Relevance Filtering False Positives and False Negatives Corrupt Sentiment Signal

**What goes wrong:**

Simple substring matching (e.g., checking if "Claude" appears in post text) generates large numbers of false positives — posts about "Claude Monet", "Claude Shannon", or "claude" the French name score sentiment for the wrong entity. False negatives occur when entity mentions are abbreviated ("GPT", "Cursor's new feature") and don't match the search term. Both corrupt the sentiment time-series with noise.

For ML-based relevance filtering using zero-shot classification or embeddings, the same problem surfaces as low-confidence scores being treated as binary pass/fail.

**Why it happens:**

Text contains inherent ambiguity. Single-token entity names (Claude, Gemini, Cursor) are especially prone to false positives. Developers test on obvious cases ("I love Claude 3!") and miss edge cases (posts where "claude" is a French name or part of an unrelated technical term). At scale (thousands of posts/day), even a 5% false positive rate injects substantial noise.

**How to avoid:**

1. Use context-aware entity detection, not just substring matching. Check that the entity mention occurs in a context related to AI/technology (check surrounding words: "AI", "model", "OpenAI", "Anthropic", etc.).
2. Implement a confidence threshold for ML-based relevance scoring. Posts scoring below 0.7 confidence should be flagged for manual review, not rejected outright.
3. Build a small validation set (50-100 labeled posts per entity) before deploying relevance filtering to production. Measure precision and recall against this set.
4. For low-ambiguity entities (e.g., "GPT-4o", "Cursor IDE"), substring matching is fine. For high-ambiguity names (Claude, Gemini, Codex), require additional context signals.

```python
# Context-aware entity detection
AI_CONTEXT_SIGNALS = {
    "claude": ["anthropic", "claude 3", "claude.ai", "llm", "ai", "model", "claude opus", "claude sonnet"],
    "gemini": ["google", "google gemini", "gemini pro", "gemini ultra", "llm", "bard"],
    "cursor": ["cursor ide", "cursor.sh", "anysphere", "copilot", "code editor", "ai coding"],
}

def is_relevant_post(text: str, entity_name: str) -> bool:
    text_lower = text.lower()
    entity_lower = entity_name.lower()

    if entity_lower not in text_lower:
        return False  # Entity not mentioned

    # For ambiguous entity names, require context
    if entity_lower in AI_CONTEXT_SIGNALS:
        context_signals = AI_CONTEXT_SIGNALS[entity_lower]
        has_context = any(signal in text_lower for signal in context_signals)
        if not has_context:
            return False  # Likely false positive

    return True
```

**Warning signs:**

- Sentiment for "Claude" entity is positive on days with Claude Monet exhibition news
- Same post appears in results for multiple unrelated entities
- Entity sentiment spikes or drops sharply on days with no AI news (false positives driving noise)
- Recall audit shows entity X has 10x fewer relevant posts than entity Y of equal community interest

**Phase to address:** Relevance filtering phase. Do not skip validation against labeled examples.

---

### Pitfall 8: LLM API Reliability — Structured Extraction Fails Silently

**What goes wrong:**

LLM API calls (OpenAI, Anthropic) for aspect-level sentiment extraction fail in three ways: (1) the API returns a valid HTTP 200 but the JSON response doesn't match the expected schema; (2) the API returns 429/503 during batch processing, and retry logic with exponential backoff adds 2-5 minutes of latency per batch; (3) the LLM generates syntactically valid but semantically wrong extraction (e.g., extracting sentiment about the wrong aspect). All three failures are invisible unless explicitly validated.

**Why it happens:**

LLMs are probabilistic — the same prompt produces different outputs on different calls. Temperature=0 reduces but does not eliminate variation. Production rate limits on hosted LLM APIs are more aggressive than expected during batch workloads (sentiment scoring 10,000 posts/day can easily exceed tier limits). Developers test with 10 examples; production runs with 10,000.

**How to avoid:**

1. Always validate LLM output against a Pydantic schema before storing. Never store raw LLM text.
2. Use exponential backoff with jitter for 429/503 responses. Max 3 retries per request. Use `tenacity` (already in requirements.txt).
3. Budget LLM API calls before deploying. At 1 call per post × 10,000 posts/day, you need a tier that supports that volume. Pre-compute what percentage of posts actually need LLM extraction (RoBERTa handles bulk scoring; LLM only for high-value posts).
4. Use instructor or pydantic-based output parsing that automatically retries with the error message when schema validation fails.

```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from pydantic import BaseModel
import openai

class AspectSentiment(BaseModel):
    entity: str
    aspect: str  # "performance", "pricing", "usability", etc.
    sentiment_score: float  # -1 to 1
    confidence: float  # 0 to 1
    evidence: str  # Quote from text supporting this score

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type((openai.RateLimitError, openai.APIConnectionError))
)
async def extract_aspect_sentiment(text: str, entity: str) -> AspectSentiment | None:
    # Use structured output mode (JSON schema enforcement)
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[...]
    )
    try:
        return AspectSentiment.model_validate_json(response.choices[0].message.content)
    except Exception:
        return None  # Fail gracefully, don't propagate schema errors
```

**Warning signs:**

- Aspect sentiment table has NULL values for fields the LLM was supposed to fill
- LLM call duration spikes during batch runs (retry storms)
- Monthly LLM API cost exceeds budget (check call volume before enabling on all posts)
- LLM assigns sentiment to wrong entity in multi-entity posts

**Phase to address:** LLM extraction phase. Validate schema coverage (% of posts with valid extraction) before enabling in production.

---

### Pitfall 9: Reddit Burst Requests Trigger Rate Limiting Despite Low Average

**What goes wrong:**

Reddit enforces rate limits over a **rolling 10-minute window**, not per-minute averages. A data collector that fetches all subreddits for all entities in a tight loop (e.g., 100 requests in 30 seconds) will be throttled even though the average over 10 minutes is within the 100 QPM limit. PRAW's default rate limit handling waits only up to 5 seconds; waits longer than that are ignored, causing the next request to fail.

**Why it happens:**

Developers test one entity at a time. Production runs 10-20 entities simultaneously. Sequential-entity collection that felt slow in testing becomes burst traffic in production. Async concurrent Reddit fetching across all entities simultaneously is especially dangerous.

**How to avoid:**

1. Add inter-request delays (0.6s minimum) between Reddit API calls, regardless of `asyncpraw`'s internal rate limiting.
2. Stagger entity collection across the scheduling window. Don't fetch all 20 entities simultaneously — fetch one every 3 minutes across the hourly job.
3. Monitor `X-Ratelimit-Remaining` header. At <10 remaining, pause for `X-Ratelimit-Reset` seconds.
4. Use a simple token bucket or semaphore to limit concurrent Reddit requests to 1-2 at a time.

```python
import asyncio

# Global semaphore to prevent burst requests
reddit_semaphore = asyncio.Semaphore(2)  # Max 2 concurrent Reddit requests

async def fetch_subreddit_posts(reddit, subreddit_name: str, query: str, limit: int = 25):
    async with reddit_semaphore:
        subreddit = await reddit.subreddit(subreddit_name)
        posts = []
        async for post in subreddit.search(query, limit=limit, sort="new"):
            posts.append(post)
        await asyncio.sleep(0.6)  # Mandatory inter-request delay
        return posts
```

**Warning signs:**

- 429 responses appearing in batches (not isolated incidents)
- Reddit token expires mid-collection (token refresh failed under load)
- Collection of all entities for one cycle takes >1 hour (backoff cascading)

**Phase to address:** Reddit collector phase. Load-test the full entity set before claiming the collector works.

---

## Minor Pitfalls

Smaller mistakes that create technical debt or require rework.

### Pitfall 10: Render Cold Start Kills Scheduled Job Startup

**What goes wrong:**

Render free/starter tier services spin down after inactivity and take 15-30 seconds to cold-start. If APScheduler is running inside the FastAPI process (current architecture), the scheduler doesn't start until the first HTTP request wakes the dyno. Scheduled jobs that should run at 2:00 AM are skipped because no request arrives to wake the service.

**How to avoid:**

Keep a Render Cron Job separate from the web service. Or upgrade to a paid plan that prevents sleep. Alternatively, trigger jobs via HTTP from an external pinger (UptimeRobot free tier, GitHub Actions cron) to keep the dyno warm and trigger collections.

**Phase to address:** Scheduler architecture phase.

---

### Pitfall 11: Alembic `on_conflict_do_update` Constraint Name Mismatch

**What goes wrong:**

The existing `sentiment_service.py` references a constraint named `uq_sentiment_timeseries_entity_timestamp_period` in its upsert logic. If the new schema migration adds new tables with similar upsert patterns but the constraint names don't match what's in the ORM, every upsert will fail with a `LookupError: Can't find constraint...` at runtime.

**How to avoid:**

Always use named constraints in SQLAlchemy models. When adding new tables with upsert patterns, define the constraint name explicitly in `__table_args__` and reference the same name in the `on_conflict_do_update` call. Add an integration test that actually inserts and upserts a row.

**Phase to address:** Schema migration phase.

---

### Pitfall 12: Dev.to and Discourse Rate Limits Are Undocumented

**What goes wrong:**

Dev.to and Discourse instances don't publish rate limits prominently. Dev.to's API returns `429` without a `Retry-After` header for unauthenticated requests after ~30 requests/minute. Discourse instances (Indie Hackers, Elixir Forum, etc.) each have independent rate limits. An aggressive poller gets IP-banned from one community Discourse instance, blocking all future data from that source.

**How to avoid:**

1. Use authenticated requests for Dev.to (requires API key, free to obtain). Authenticated tier is significantly more generous.
2. For Discourse: implement conservative defaults (max 10 requests/minute per instance) and treat `429` responses as source-specific bans requiring exponential backoff starting at 60 seconds.
3. Add per-source rate limit tracking, not a single global counter.

**Phase to address:** Data collector phase for Dev.to and Discourse.

---

### Pitfall 13: GitHub Data Collector Hits Secondary Rate Limits

**What goes wrong:**

GitHub's GraphQL API has both primary rate limits (5,000 points/hour) and secondary rate limits (undocumented, based on concurrent connection volume). Fetching repository issues and discussions concurrently across many repos triggers secondary limits, returning `403 You have exceeded a secondary rate limit`. These are separate from the primary limit and have no documented reset time.

**How to avoid:**

1. Use GitHub Apps authentication (60,000 requests/hour) instead of personal access tokens (5,000/hour) for production.
2. Add 1-second delays between GraphQL requests. Never parallelize GitHub requests.
3. For secondary rate limits: catch `403` responses with `secondary rate limit` in the message, back off for 60 seconds minimum.

**Phase to address:** GitHub collector phase.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Load RoBERTa in-process with FastAPI | Simpler deployment | OOM kills dyno, blocks on cold start | Never on Render starter tier |
| Use PRAW (sync) instead of asyncpraw | Less setup friction | Blocks FastAPI event loop, causes timeouts | Never in async FastAPI context |
| Substring match for entity relevance | Fast to implement | High false positive rate corrupts sentiment | MVP only, with explicit TODO to replace |
| Store LLM raw text instead of validated schema | Faster iteration | Downstream consumers break on format changes | Never in production pipeline |
| Skip Alembic, use `create_all()` directly | Easier schema changes | No migration history, can't upgrade without downtime | Never for production database |
| Single global Reddit rate limit counter | Simple | Burst requests still trigger throttling | Never — use rolling window tracking |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Reddit (asyncpraw) | Using `praw.Reddit()` in async code | Use `asyncpraw.Reddit()`, await all calls |
| Reddit auth | Missing redirect_uri for script app | Set `http://localhost:8080` even though it's never called |
| HN Algolia | Paginating past page 10 | Narrow time window instead of paginating deep |
| RoBERTa/transformers | Loading model inside request handler | Load once at module startup, reuse singleton |
| Alembic brownfield | Running autogenerate without inspecting output | Always inspect generated migration for DROP TABLE calls |
| LLM structured extraction | Storing raw text response | Always validate against Pydantic schema before storing |
| Dev.to API | Unauthenticated requests | Get free API key, use in `api-key` header |
| sentence-transformers | Embedding all posts in one batch | Chunk into max 32-item batches with explicit cleanup |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| In-process ML model loading | Startup takes 60+ seconds, cold start OOM | Separate worker, quantize model | First deploy to Render |
| Synchronous Reddit requests | FastAPI becomes unresponsive during collection | asyncpraw + semaphore | First concurrent user during collection |
| Deep HN Algolia pagination | Empty results after page 10 | Narrow time windows | Any query returning >1,000 results |
| LLM batch without rate limit awareness | 429 cascades, batch takes hours | Token bucket per API, exponential backoff | First production batch over 500 posts |
| Missing DB index on new posts table | Slow sentiment join queries | Add `(entity_id, created_at DESC)` index from day 1 | At ~10,000 posts |

---

## "Looks Done But Isn't" Checklist

- [ ] **Reddit collector:** Validate that `asyncpraw` is used (not `praw`), and that the OAuth app type is "script"
- [ ] **RoBERTa deployment:** Verify memory usage under load on the actual Render instance tier (not local)
- [ ] **Alembic migration:** Inspect autogenerated migration for DROP TABLE before applying to production; create pg_dump backup first
- [ ] **HN collector:** Test pagination with `created_at_i` numeric filter and verify non-zero hits
- [ ] **Relevance filtering:** Validate precision/recall against 50+ labeled posts per entity before enabling
- [ ] **LLM extraction:** Confirm 100% of stored aspect sentiment records are schema-validated (no raw text in DB)
- [ ] **Frontend compatibility:** Confirm existing `/api/entities` and `/api/sentiment/timeseries` responses are unchanged after backend deploy
- [ ] **Embedding memory:** Measure RSS growth over 24 hours on Render before claiming the service is stable

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| OOM kill from RoBERTa | MEDIUM | Upgrade Render tier or switch to DistilRoBERTa ONNX; restart service |
| Alembic migration dropped tables | HIGH | Restore from pg_dump backup; fix env.py import; re-run migration |
| Reddit app type wrong (invalid_grant) | LOW | Create new Reddit app with "script" type; update env vars; redeploy |
| Frontend broken by API change | MEDIUM | Revert backend deploy; apply Expand-Contract pattern; redeploy together |
| LLM extraction stored malformed data | MEDIUM | Delete malformed rows; fix schema validation; re-run extraction |
| Entity relevance false positives | MEDIUM | Add context-signal filtering; recompute sentiment timeseries for affected periods |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| RoBERTa OOM | ML model phase — first task | Memory metric on Render stays below 80% for 24 hours |
| Embedding memory leak | Relevance filtering phase | RSS metric is stable (not growing) over 12-hour window |
| Reddit OAuth misconfiguration | Reddit collector phase — before pipeline integration | Auth flow works in isolation; 100 test requests succeed |
| Alembic drop-tables migration | Schema migration phase — first task in any DB-change milestone | Migration applied to staging with no DROP TABLE calls; backup taken first |
| Frontend breakage | Every API-change phase | Existing frontend endpoints return same response shape after deploy |
| HN pagination silent failures | HN collector phase | Validate result count matches expected for known time windows |
| Relevance false positives | Relevance filtering phase | Precision ≥ 0.85 on labeled validation set before production enable |
| LLM structured extraction failures | LLM extraction phase | 0 NULL values in required schema fields after 24-hour production run |
| Reddit burst rate limiting | Reddit collector phase — load testing | Full entity set collection completes without 429 responses |
| LLM API budget overrun | LLM extraction phase | Per-day API call count validated against tier limits before enabling |

---

## Sources

- [Reddit Data API Wiki](https://support.reddithelp.com/hc/en-us/articles/16160319875092-Reddit-Data-API-Wiki) — MEDIUM confidence (official, but enforcement details vary)
- [asyncpraw OAuth Documentation](https://asyncpraw.readthedocs.io/en/stable/getting_started/authentication.html) — HIGH confidence (official)
- [Render Community: OOM errors](https://community.render.com/t/more-info-about-oom-errors-would-be-helpful/19698) — HIGH confidence (Render platform behavior)
- [HuggingFace transformers OOM issue #1742](https://github.com/huggingface/transformers/issues/1742) — HIGH confidence (confirmed community pattern)
- [Milvus: Sentence Transformers memory footprint](https://milvus.io/ai-quick-reference/how-can-you-reduce-the-memory-footprint-of-sentence-transformer-models-during-inference-or-when-handling-large-numbers-of-embeddings) — MEDIUM confidence (third-party but well-documented)
- [Algolia HN API documentation](https://hn.algolia.com/api) — HIGH confidence (official)
- [Algolia paginationLimitedTo parameter](https://www.algolia.com/doc/api-reference/api-parameters/paginationLimitedTo/) — HIGH confidence (official docs)
- [Render free tier memory specs](https://community.render.com/t/the-free-instance-type-e-g-512mb-ram-0-1-cpu/39044) — HIGH confidence (Render forum, confirmed with pricing)
- [LLM retry strategies 2025](https://markaicode.com/llm-api-retry-logic-implementation/) — MEDIUM confidence (current practice, not official)
- [Alembic brownfield discussion](https://github.com/sqlalchemy/alembic/discussions/1425) — HIGH confidence (official SQLAlchemy repo)

---

*Pitfalls research for: VibeCheck v2.0 — brownfield FastAPI + PostgreSQL with multi-source collectors and ML sentiment pipeline*
*Researched: 2026-02-19*
*Replaces: .planning/research/PITFALLS.md (v1.0, 2026-02-05)*
