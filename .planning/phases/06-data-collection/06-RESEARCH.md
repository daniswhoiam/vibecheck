# Phase 6: Data Collection - Research

**Researched:** 2026-02-20
**Domain:** Multi-source data collection (HN Algolia, Reddit asyncpraw, Discourse REST, Dev.to Forem API), keyword filtering, deduplication, APScheduler integration
**Confidence:** HIGH (stack verified via official docs and live API probing; patterns from existing codebase)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Collection targets:**
- Research top 10 AI tools/models by usage (Kilo Code stats as starting reference) to drive keyword lists
- Reddit: two-layer approach — tool-specific subreddits (r/ChatGPT, r/ClaudeAI, r/cursor, etc.) plus broad AI/dev subs (r/artificial, r/LocalLLaMA, etc.) with stricter filtering on broad subs
- Discourse: Claude's discretion on which forums to target — research which AI tool Discourse forums are active and worth collecting from (Cursor and OpenAI mentioned as starting points)
- Hacker News: stories + top-level comments on relevant stories via Algolia API
- Dev.to: full articles via Forem API v1, filtered by relevant tags/keywords

**Filtering strictness:**
- Adaptive approach: start strict, loosen if data volume is insufficient
- Ambiguity-aware keyword matching: unambiguous tool names (ChatGPT, Copilot, GPT-4) match bare; ambiguous names (Claude, Cursor) require nearby context words (AI, model, coding, LLM, etc.)
- Exact deduplication only for v2.0: URL match + content hash. Near-duplicate detection (MinHash) deferred to COLL-10
- Rejected post handling: Claude's discretion on whether to log or silently discard based on storage/complexity tradeoffs

**Collection frequency:**
- Every 6 hours for all sources
- Sources staggered ~30 minutes apart to smooth resource usage
- On first run: backfill as much historical data as each free API allows
- Retry behavior on failure: Claude's discretion based on each API's characteristics

**Post content scope:**
- Store full text with a reasonable maximum character cap (Claude determines ceiling)
- Include top-level comments from Reddit and HN (not full threads)
- Dev.to: fetch and store full article body, not just excerpt
- Engagement metrics captured: upvotes, score, comment count (where available per source)
- No author/user identification data — defer to future phase
- GDPR compliance: strip or avoid storing any PII from collected posts

### Claude's Discretion

- Exact Discourse forums to target (research which are active)
- Reasonable max character cap for post content
- Retry strategy per source on failure
- Whether to log rejected posts or silently discard
- Specific subreddit list (tool-specific + broad, based on research)
- Stagger timing between sources

### Deferred Ideas (OUT OF SCOPE)

- Near-duplicate detection (MinHash similarity) — already tracked as COLL-09 in Future Requirements
- Author credibility weighting — deferred until PII/GDPR strategy is fully defined
- Per-source frequency tuning — start uniform at 6h, adjust based on production volume data
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| COLL-01 | System collects developer posts from Hacker News via Algolia API on a schedule | HN Algolia API: `/search_by_date` endpoint with `tags=story`, `numericFilters` for date range, `hitsPerPage` up to 1000; free, no auth required |
| COLL-02 | System collects developer posts from Reddit subreddits via asyncpraw on a schedule | asyncpraw 7.8.1: `subreddit.new(limit=100)` + comment fetch; requires Reddit app credentials (client_id/secret); read-only mode sufficient |
| COLL-03 | System collects developer posts from Discourse forums (Cursor, OpenAI) on a schedule | Discourse REST API: `/latest.json`, `/search.json?q=...` endpoints; public forums accessible without auth via httpx; paginated with `page` param |
| COLL-04 | System collects developer articles from Dev.to via Forem API v1 on a schedule | Forem API v1: `GET /api/articles?tag=...&page=N&per_page=30`; auth via `api-key` header + `accept: application/vnd.forem.api-v1+json`; public articles accessible without auth |
| COLL-05 | Keyword relevance filter rejects irrelevant posts before storage using tool names and context terms | Regex-based ambiguity-aware matching using existing CURATED_ENTITIES from constants.py; unambiguous vs. context-requiring classification |
| COLL-06 | Content deduplication prevents duplicate posts across all sources via hash-based detection | `compute_content_hash()` already exists in `pipeline/services/deduplication_service.py`; DB-level `content_hash UNIQUE` constraint on posts table catches duplicates on insert |
</phase_requirements>

---

## Summary

This phase connects four external data sources to the existing VibeCheck pipeline. The infrastructure is already mostly in place: APScheduler with `AsyncIOScheduler` is configured in `pipeline/scheduler.py` (with `setup_jobs()` as a placeholder), the `Post` model and `content_hash` unique constraint exist in `db/models.py`, `compute_content_hash()` lives in `pipeline/services/deduplication_service.py`, and `storage_service.py` is a stub waiting to be filled. The main work is implementing four source-specific collector modules and wiring them into the scheduler.

Each source uses a different client/protocol: HN uses a free REST API (no auth, httpx), Reddit requires asyncpraw with OAuth credentials, Discourse uses its public REST API (httpx, no auth for public forums), and Dev.to uses the Forem API v1 (httpx, optional API key for higher rate limits). All four must feed a common normalization layer that maps raw response data to `Post` objects, applies keyword filtering, computes content hashes, and persists to the database with duplicate rejection.

The existing CURATED_ENTITIES in `utils/constants.py` defines the 10 entities to track: GPT-4o, Claude, Gemini, Llama, Mistral, Cursor, Lovable, v0, GitHub Copilot, Replit. These drive the keyword filter. Ambiguity-aware filtering is the key design challenge: "Claude" and "Cursor" appear in non-AI contexts, so context words (LLM, AI, model, coding, etc.) must co-occur within a window.

**Primary recommendation:** Implement one collector module per source in `pipeline/clients/`, a shared `FilterService` and extended `StorageService` in `pipeline/services/`, then register four APScheduler interval jobs in `setup_jobs()` staggered 30 minutes apart.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | 0.28.1 (already pinned) | HTTP client for HN, Discourse, Dev.to | Already in requirements.txt; async-native; project standard |
| asyncpraw | 7.8.1 | Reddit API wrapper | Official async PRAW; latest stable; internally handles rate limits |
| apscheduler | 3.10.4 (already pinned) | Job scheduling | Already in requirements.txt; `AsyncIOScheduler` supports native `async def` jobs |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| re (stdlib) | stdlib | Regex-based keyword matching | Ambiguity-aware pattern matching; no extra dependency |
| hashlib (stdlib) | stdlib | SHA-256 content hashing | Already used in `compute_content_hash()`; no extra dependency |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| asyncpraw | praw (sync) | asyncpraw is required for async FastAPI context; sync PRAW would block event loop |
| httpx | aiohttp | aiohttp has slightly better raw concurrency; httpx already pinned in project, consistent with existing codebase |
| regex patterns | spaCy NER | spaCy would be more accurate but adds 100MB+ of model downloads; overkill for v2.0 |

**Installation (new dependency only):**
```bash
pip install asyncpraw==7.8.1
```

---

## Architecture Patterns

### Recommended Project Structure

```
backend/
├── pipeline/
│   ├── clients/
│   │   ├── __init__.py
│   │   ├── hackernews_client.py   # HN Algolia API (httpx)
│   │   ├── reddit_client.py       # asyncpraw subreddit collection
│   │   ├── discourse_client.py    # Discourse REST API (httpx)
│   │   └── devto_client.py        # Forem API v1 (httpx)
│   ├── jobs/
│   │   ├── __init__.py
│   │   ├── collect_hackernews.py  # Job function for scheduler
│   │   ├── collect_reddit.py
│   │   ├── collect_discourse.py
│   │   └── collect_devto.py
│   ├── services/
│   │   ├── deduplication_service.py  # Already exists
│   │   ├── filter_service.py          # NEW: keyword relevance filter
│   │   ├── storage_service.py         # Extend stub: save_post()
│   │   └── entity_service.py          # Already exists
│   └── scheduler.py               # setup_jobs() to be filled
```

### Pattern 1: Client → Job → Scheduler Separation

**What:** Each source has a `client` (pure API interaction, no DB) and a `job` (orchestrates fetch → filter → deduplicate → store). The scheduler calls the job.

**When to use:** Always — keeps HTTP logic testable without DB and keeps jobs thin.

**Example:**
```python
# pipeline/clients/hackernews_client.py
import httpx
from datetime import datetime, timezone
from typing import AsyncGenerator

HN_API_BASE = "https://hn.algolia.com/api/v1"

async def fetch_stories_since(
    query: str,
    since_timestamp: int,
    client: httpx.AsyncClient,
) -> AsyncGenerator[dict, None]:
    """Yield HN story hits since a given Unix timestamp."""
    page = 0
    while True:
        response = await client.get(
            f"{HN_API_BASE}/search_by_date",
            params={
                "query": query,
                "tags": "story",
                "numericFilters": f"created_at_i>{since_timestamp}",
                "hitsPerPage": 100,
                "page": page,
            }
        )
        response.raise_for_status()
        data = response.json()
        hits = data.get("hits", [])
        if not hits:
            break
        for hit in hits:
            yield hit
        if page >= data.get("nbPages", 1) - 1:
            break
        page += 1
```

### Pattern 2: Shared Post Normalization

**What:** Each client produces raw dicts; a normalizer maps them to a common `PostCreate` Pydantic model before storage.

**When to use:** Before calling `storage_service.save_post()` — ensures all sources produce consistent data.

**Example (HN normalizer):**
```python
from pydantic import BaseModel
from datetime import datetime

class PostCreate(BaseModel):
    source: str          # "hackernews" | "reddit" | "discourse" | "devto"
    external_id: str
    url: str | None
    title: str | None
    body: str | None
    published_at: datetime
    metadata: dict | None = None  # upvotes, score, comment_count

def normalize_hn_story(hit: dict) -> PostCreate:
    return PostCreate(
        source="hackernews",
        external_id=hit["objectID"],
        url=hit.get("url"),
        title=hit.get("title"),
        body=hit.get("story_text"),  # self-posts only
        published_at=datetime.fromtimestamp(hit["created_at_i"], tz=timezone.utc),
        metadata={
            "score": hit.get("points"),
            "comment_count": hit.get("num_comments"),
        }
    )
```

### Pattern 3: APScheduler Job Registration with Stagger

**What:** Register four interval jobs in `setup_jobs()`, each with a `minutes` offset to stagger start times.

**Example (from existing scheduler.py pattern):**
```python
# pipeline/scheduler.py — inside setup_jobs()
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timezone, timedelta

def setup_jobs() -> None:
    # Stagger: HN at :00, Reddit at :30, Discourse at :60, Dev.to at :90
    # (relative to first run; all repeat every 6 hours)
    now = datetime.now(timezone.utc)

    scheduler.add_job(
        run_collect_hackernews,
        trigger=IntervalTrigger(hours=6),
        next_run_time=now,
        id="collect_hackernews",
        replace_existing=True,
    )
    scheduler.add_job(
        run_collect_reddit,
        trigger=IntervalTrigger(hours=6),
        next_run_time=now + timedelta(minutes=30),
        id="collect_reddit",
        replace_existing=True,
    )
    # ... discourse at +60min, devto at +90min
```

> Note: Use `replace_existing=True` and explicit `id=` to prevent duplicate job registration on restart.

### Pattern 4: Per-Job Database Session

**What:** Each job function creates its own `AsyncSession` using `AsyncSessionLocal`. The existing `wrapped_job_execution` in `scheduler.py` already handles this pattern.

**Example:**
```python
# pipeline/jobs/collect_hackernews.py
from db.session import AsyncSessionLocal

async def run_collect_hackernews(db_session) -> dict:
    """Job function: called by wrapped_job_execution."""
    collected = 0
    filtered = 0
    duplicates = 0
    async with httpx.AsyncClient() as client:
        async for hit in fetch_stories_since(..., client=client):
            post = normalize_hn_story(hit)
            if not filter_service.is_relevant(post):
                filtered += 1
                continue
            stored = await storage_service.save_post(post, db_session)
            if stored:
                collected += 1
            else:
                duplicates += 1
    return {"collected": collected, "filtered": filtered, "duplicates": duplicates}
```

### Pattern 5: Ambiguity-Aware Keyword Filter

**What:** Two-tier regex matching. Unambiguous names match as standalone words. Ambiguous names (Claude, Cursor, Gemini, Llama) require context words within ±150 characters.

**Example:**
```python
import re

UNAMBIGUOUS = {
    "chatgpt", "gpt-4o", "gpt-4", "copilot", "github copilot",
    "lovable", "replit", "v0.dev",
}
AMBIGUOUS = {
    "claude": ["llm", "ai", "model", "anthropic", "coding", "sonnet", "haiku", "opus"],
    "cursor": ["ai", "editor", "ide", "coding", "llm", "vibe"],
    "gemini": ["google", "ai", "llm", "model", "gemini pro", "gemini flash"],
    "llama": ["meta", "llm", "model", "ollama", "local"],
    "mistral": ["llm", "model", "ai", "mistral ai"],
}
CONTEXT_WINDOW = 150  # characters

def is_relevant(text: str) -> bool:
    text_lower = text.lower()
    # Check unambiguous names — bare word match
    for name in UNAMBIGUOUS:
        if re.search(r'\b' + re.escape(name) + r'\b', text_lower):
            return True
    # Check ambiguous names — require context
    for name, context_words in AMBIGUOUS.items():
        for m in re.finditer(r'\b' + re.escape(name) + r'\b', text_lower):
            start = max(0, m.start() - CONTEXT_WINDOW)
            end = min(len(text_lower), m.end() + CONTEXT_WINDOW)
            window = text_lower[start:end]
            if any(ctx in window for ctx in context_words):
                return True
    return False
```

### Anti-Patterns to Avoid

- **Sharing a single `AsyncSession` across jobs:** Each job run must create its own session via `async with AsyncSessionLocal()`. The existing `wrapped_job_execution` passes a session — use it only within one job invocation.
- **Blocking httpx calls in async context:** Always use `httpx.AsyncClient` (not `httpx.get()`). Never use `requests` library.
- **Catching exceptions silently in clients:** Let clients raise; the job layer (or `wrapped_job_execution`) handles logging so errors are captured in `SchedulerExecutionLog`.
- **Storing author information:** The `Post` model has no author column — deliberately omitted. Do not add author fields (GDPR concern, deferred).
- **Registering jobs without `replace_existing=True`:** Causes duplicate job accumulation on app restarts.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Reddit rate limiting | Custom sleep/backoff | asyncpraw (handles internally) | PRAW follows Reddit's rate limit headers automatically |
| Content hash | Custom deduplication | `compute_content_hash()` in existing `deduplication_service.py` | Already implemented; SHA-256 of normalized content |
| DB-level duplicate rejection | Application-layer duplicate check | `content_hash UNIQUE` constraint on posts table + catch `IntegrityError` on insert | DB constraint is atomic and race-condition safe |
| Job scheduling | Custom cron loop | APScheduler `AsyncIOScheduler` (already configured) | Already in `scheduler.py`; just register jobs in `setup_jobs()` |

**Key insight:** The deduplication contract is: compute `content_hash` on `(url or body_text)`, attempt INSERT, catch `IntegrityError` (unique constraint violation), log as duplicate and continue. This is simpler and more reliable than pre-checking existence.

---

## Common Pitfalls

### Pitfall 1: APScheduler Duplicate Jobs on Restart

**What goes wrong:** Jobs accumulate in memory on every hot-reload or app restart, causing multiple concurrent executions.

**Why it happens:** `scheduler.add_job()` without `id=` generates a new UUID each call.

**How to avoid:** Always pass `id="collect_hackernews"` (etc.) and `replace_existing=True`.

**Warning signs:** `scheduler.get_jobs()` returns more jobs than expected after restart.

---

### Pitfall 2: asyncpraw Session Not Closed

**What goes wrong:** AIOHTTP connector warnings; potential connection leak.

**Why it happens:** asyncpraw uses an aiohttp session internally that must be explicitly closed.

**How to avoid:** Always use `async with asyncpraw.Reddit(...) as reddit:` pattern, or call `await reddit.close()`.

---

### Pitfall 3: HN Algolia Pagination Cut-Off

**What goes wrong:** Only first 1000 hits returned per query (Algolia hard limit: 1000 hits = 10 pages × 100 per page).

**Why it happens:** Algolia caps `page * hitsPerPage` at 1000.

**How to avoid:** For backfill, split time ranges into smaller windows (e.g., per-week chunks) and query each separately. For ongoing collection (6h intervals), 1000 results per query is more than sufficient.

**Warning signs:** `nbPages` is 10 and results feel truncated despite many matching stories.

---

### Pitfall 4: Discourse Forum Login Walls

**What goes wrong:** `/latest.json` returns 403 or redirects to login for some Discourse instances.

**Why it happens:** Forum admin may have set `login_required: true`.

**How to avoid:** Test target forums (forum.cursor.com, community.openai.com) before implementing. If login is required, use API key auth (`Api-Key` + `Api-Username` headers). Public read typically works without auth.

**Warning signs:** Response status 403 or HTML login page returned instead of JSON.

---

### Pitfall 5: "Claude" / "Cursor" False Positives

**What goes wrong:** High volume of irrelevant posts captured because "Claude" matches Claude Monet, Claude Debussy; "Cursor" matches database cursors.

**Why it happens:** Common English words used as entity names.

**How to avoid:** Implement the ambiguity-aware filter (Pattern 5 above) from the start. Start strict — it is easier to loosen than to purge bad data.

**Warning signs:** Posts about impressionist painters or SQL cursors appearing in the database.

---

### Pitfall 6: Content Hash Collision Strategy

**What goes wrong:** Duplicate posts from different sources (e.g., someone cross-posts the same article) are silently dropped even though they are from different sources.

**Why it happens:** `content_hash` is a unique constraint globally, not per-source.

**How to avoid:** This is intentional per CONTEXT.md (exact deduplication v2.0). The `(source, external_id)` unique constraint additionally prevents same-source duplicates. Cross-source deduplication via content hash is a feature, not a bug.

---

### Pitfall 7: GDPR PII in Scraped Content

**What goes wrong:** Post body contains email addresses, usernames in text, or other PII.

**Why it happens:** Dev.to articles and Reddit comments may include user-provided contact info.

**How to avoid:** Strip author fields (already excluded from `Post` model). For body text, apply a simple regex to redact email patterns before storing. Username mentions (u/handle, @handle) are borderline — acceptable in public posts, but do not index them separately.

---

## Code Examples

Verified patterns from official sources and existing codebase:

### HN Algolia API: Stories Since Timestamp

```python
# Source: live API probe https://hn.algolia.com/api/v1/search_by_date
import httpx
from datetime import datetime, timezone

HN_API_BASE = "https://hn.algolia.com/api/v1"

async def fetch_hn_stories(since_unix: int, client: httpx.AsyncClient) -> list[dict]:
    """Fetch HN stories since a Unix timestamp. Returns list of hit dicts."""
    results = []
    page = 0
    while True:
        r = await client.get(
            f"{HN_API_BASE}/search_by_date",
            params={
                "tags": "story",
                "numericFilters": f"created_at_i>{since_unix}",
                "hitsPerPage": 100,
                "page": page,
            },
            timeout=30.0,
        )
        r.raise_for_status()
        data = r.json()
        hits = data.get("hits", [])
        results.extend(hits)
        nb_pages = data.get("nbPages", 1)
        if page >= nb_pages - 1 or not hits:
            break
        page += 1
        if page * 100 >= 1000:  # Algolia hard cap
            break
    return results

# HN hit fields used:
# hit["objectID"] → external_id
# hit["title"]    → title
# hit["url"]      → url (None for Ask HN)
# hit["story_text"] → body (self-posts only)
# hit["created_at_i"] → published_at (Unix epoch)
# hit["points"]   → metadata.score
# hit["num_comments"] → metadata.comment_count
```

### asyncpraw: Fetch Subreddit Posts (Read-Only)

```python
# Source: asyncpraw.readthedocs.io/en/stable/getting_started/quick_start.html
import asyncpraw

async def fetch_reddit_posts(
    subreddit_name: str,
    limit: int = 100,
    client_id: str = ...,
    client_secret: str = ...,
) -> list[dict]:
    async with asyncpraw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent="VibeCheck/2.0 (sentiment tracker by u/vibecheck_bot)",
    ) as reddit:
        subreddit = await reddit.subreddit(subreddit_name)
        posts = []
        async for submission in subreddit.new(limit=limit):
            posts.append({
                "id": submission.id,
                "title": submission.title,
                "selftext": submission.selftext,
                "url": submission.url,
                "score": submission.score,
                "num_comments": submission.num_comments,
                "created_utc": submission.created_utc,
                "permalink": f"https://reddit.com{submission.permalink}",
            })
        return posts
```

### Discourse: Latest Topics (public, no auth)

```python
# Source: meta.discourse.org community knowledge + Discourse API docs
import httpx

async def fetch_discourse_latest(
    base_url: str,
    client: httpx.AsyncClient,
    page: int = 0,
) -> list[dict]:
    r = await client.get(
        f"{base_url}/latest.json",
        params={"page": page},
        headers={"User-Agent": "VibeCheck/2.0"},
        timeout=30.0,
    )
    r.raise_for_status()
    data = r.json()
    return data.get("topic_list", {}).get("topics", [])

# Discourse topic fields:
# topic["id"]            → external_id
# topic["title"]         → title
# topic["created_at"]    → published_at (ISO 8601)
# topic["views"]         → metadata.views
# topic["posts_count"]   → metadata.comment_count
# topic["slug"]          → for constructing URL: {base_url}/t/{slug}/{id}

# For per-topic post body, fetch: GET /t/{slug}/{id}.json
# Returns posts_stream with post bodies
```

### Dev.to (Forem API v1): Articles by Tag

```python
# Source: developers.forem.com/api/v1 + WebSearch verification
import httpx

DEVTO_API_BASE = "https://dev.to/api"
DEVTO_ACCEPT = "application/vnd.forem.api-v1+json"

async def fetch_devto_articles(
    tag: str,
    page: int = 1,
    per_page: int = 30,
    client: httpx.AsyncClient = ...,
    api_key: str | None = None,
) -> list[dict]:
    headers = {
        "Accept": DEVTO_ACCEPT,
        "User-Agent": "VibeCheck/2.0",
    }
    if api_key:
        headers["api-key"] = api_key
    r = await client.get(
        f"{DEVTO_API_BASE}/articles",
        params={"tag": tag, "page": page, "per_page": per_page},
        headers=headers,
        timeout=30.0,
    )
    r.raise_for_status()
    return r.json()

# Dev.to article fields:
# article["id"]            → external_id
# article["title"]         → title
# article["body_markdown"] → body (full text via /articles/{id})
# article["description"]   → short excerpt (in list endpoint)
# article["url"]           → canonical URL
# article["published_at"]  → published_at
# article["positive_reactions_count"] → metadata.score
# article["comments_count"]           → metadata.comment_count
# NOTE: /api/articles list returns "description" (excerpt), NOT full body.
#       Must fetch /api/articles/{id} to get body_markdown.
```

### Storage: Save Post with Duplicate Rejection

```python
# Pattern: attempt INSERT, catch IntegrityError for duplicate content_hash
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from db.models import Post
from pipeline.services.deduplication_service import compute_content_hash

MAX_BODY_CHARS = 50_000  # 50K chars; ~37K tokens — covers longest articles

async def save_post(post_data: PostCreate, session: AsyncSession) -> bool:
    """Insert a post. Returns True if saved, False if duplicate."""
    # Compute content hash from URL (preferred) or body text
    hash_input = post_data.url or (post_data.body or "")
    content_hash = compute_content_hash(hash_input)

    # Truncate body to max length
    body = post_data.body[:MAX_BODY_CHARS] if post_data.body else None

    post = Post(
        source=post_data.source,
        external_id=post_data.external_id,
        url=post_data.url,
        title=post_data.title,
        body=body,
        content_hash=content_hash,
        published_at=post_data.published_at,
        metadata=post_data.metadata,
    )
    session.add(post)
    try:
        await session.commit()
        return True
    except IntegrityError:
        await session.rollback()
        return False  # Duplicate — silently discard
```

---

## Claude's Discretion Recommendations

### Discourse Forums to Target

Based on research: the Cursor community forum is confirmed on Discourse (`forum.cursor.com`). For OpenAI, the community forum at `community.openai.com` runs Discourse. Both are public and accessible without authentication.

**Recommended Discourse targets:**
1. `https://forum.cursor.com` — active AI coding editor community; directly in scope
2. `https://community.openai.com` — large, active; broad AI tool discussion

**Rationale:** Both are public Discourse instances. Claude.ai and Anthropic do not have a Discourse forum. r/ClaudeAI covers Claude discussion on Reddit instead.

### Max Character Cap for Post Content

**Recommendation: 50,000 characters (50K)**

Rationale: Average Dev.to article is 5,000–15,000 chars. Long-form articles can reach 40,000+ chars. 50K covers ~99% of content without open-ended storage growth. This is ~37,000 tokens — well within model context for Tier 2 LLM analysis. Truncation should be logged at DEBUG level.

### Retry Strategy Per Source on Failure

**Recommendation:** Simple 3-attempt exponential backoff within the job execution, with increasing delays:

| Attempt | Delay |
|---------|-------|
| 1 | Immediate |
| 2 | 5 seconds |
| 3 | 30 seconds |

If all 3 attempts fail, the job fails gracefully (logged in `SchedulerExecutionLog` as "failed"). The next scheduled run (6 hours later) will retry from the last-seen timestamp. Do NOT use per-source backoff libraries — keep it simple with `asyncio.sleep`.

**Per-source notes:**
- HN: free, generous limits — minimal retry needed
- Reddit: asyncpraw handles rate limits internally; HTTP 5xx → retry
- Discourse: public REST, very reliable — minimal retry
- Dev.to: free tier may have rate limits → use `Retry-After` header if present

### Rejected Posts: Log or Silently Discard

**Recommendation: Silently discard.**

Rationale: Logging rejected posts would require a separate table or log file. Given the adaptive filtering approach ("start strict, loosen if volume insufficient"), the volume of rejected posts could be 10-100x the stored posts. Storage/complexity cost is not justified in v2.0. Instead, maintain a counter of rejected posts per job run (already returned in job stats dict → `SchedulerExecutionLog.metadata_json`). This gives enough visibility without storing every rejected post.

### Specific Subreddit List

**Tool-specific (loose filtering — any entity mention):**
- r/ChatGPT (9M+ members)
- r/ClaudeAI
- r/cursor
- r/GithubCopilot
- r/LocalLLaMA (covers Llama, Mistral, local models)

**Broad AI/dev (strict filtering — must match ambiguous names with context):**
- r/artificial
- r/MachineLearning
- r/programming
- r/learnmachinelearning
- r/ChatGPTCoding

**Rationale:** r/LocalLLaMA is the primary hub for Llama and Mistral discussion. r/programming and r/ChatGPTCoding capture GitHub Copilot and general coding tool discussion. Tool-specific subs are trusted (mentions of "Cursor" in r/cursor are almost always the editor). Broad subs need the ambiguity filter applied.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| PRAW (sync Reddit wrapper) | asyncpraw 7.8.1 | ~2021 | Async-native; no blocking |
| Forem API v0 | Forem API v1 | 2022 | v0 deprecated; v1 requires `Accept` header |
| AskNews paid API | Free source collection (HN/Reddit/Discourse/Dev.to) | v2.0 (now) | Eliminates API cost |

**Deprecated/outdated:**
- `asyncpraw` < 7.x: older auth patterns differ
- Forem v0 API: deprecated, will be removed; use v1 with `Accept: application/vnd.forem.api-v1+json`

---

## Open Questions

1. **Dev.to article body fetch performance**
   - What we know: The `/api/articles` list endpoint returns only a description/excerpt, NOT the full body. Full body requires a second GET to `/api/articles/{id}` per article.
   - What's unclear: Whether Dev.to rate-limits per-article fetches differently than list fetches. The exact rate limit numbers were not confirmed from official docs.
   - Recommendation: Implement a semaphore-limited concurrent fetch pattern (e.g., max 5 concurrent article fetches). If rate limited (429), apply `Retry-After` header.

2. **HN Top-Level Comments for Relevant Stories**
   - What we know: The CONTEXT.md specifies collecting top-level comments from relevant HN stories. HN Algolia API has a `/search_by_date?tags=comment` endpoint, but comments are not directly linked to a story query easily.
   - What's unclear: Whether to (a) fetch stories → fetch comments per story via `/items/{id}`, or (b) query Algolia for comments directly by keyword.
   - Recommendation: Option (a) — fetch relevant stories first, then fetch top-level comments via `GET https://hacker-news.firebaseio.com/v0/item/{id}.json` (official HN Firebase API) for stories that pass the relevance filter. Comments are already in the `hit.children` array from Algolia.

3. **Discourse forum.cursor.com rate limits**
   - What we know: Public Discourse has no documented hard rate limit for read-only JSON endpoints. Heavy scraping may trigger Cloudflare or server-side throttling.
   - What's unclear: Whether `forum.cursor.com` has custom rate limiting enabled.
   - Recommendation: Use a polite `User-Agent`, add 1-second delay between paginated requests, and implement retry-on-429 with `Retry-After`.

---

## Sources

### Primary (HIGH confidence)

- Live HN Algolia API probe: `https://hn.algolia.com/api/v1/search_by_date?query=ChatGPT&tags=story&hitsPerPage=20` — confirmed response structure, field names, pagination behavior
- asyncpraw docs: `https://asyncpraw.readthedocs.io/en/stable/getting_started/quick_start.html` — read-only auth, subreddit iteration, comment fetch patterns
- asyncpraw PyPI: `https://pypi.org/project/asyncpraw/` — confirmed latest version 7.8.1
- Existing codebase: `backend/pipeline/services/deduplication_service.py`, `backend/db/models.py`, `backend/pipeline/scheduler.py`, `backend/utils/constants.py` — verified existing infrastructure

### Secondary (MEDIUM confidence)

- APScheduler docs: `https://apscheduler.readthedocs.io/en/3.x/userguide.html` — `replace_existing=True`, interval trigger patterns
- Discourse meta community post: `https://meta.discourse.org/t/discourse-rest-api-comprehensive-examples/274354` — confirmed `/latest.json`, `/search.json?q=...` endpoints
- WebSearch on Forem API v1: confirmed `Accept: application/vnd.forem.api-v1+json` header requirement and article endpoint structure
- WebSearch on Reddit subreddits: confirmed active communities for each tracked entity

### Tertiary (LOW confidence — flag for validation)

- Dev.to rate limits: not confirmed from official docs; assume conservative limits apply
- Discourse forum.cursor.com rate limits: not confirmed; apply polite defaults
- HN Firebase API for comment fetch: general knowledge, not verified against live API in this session

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries verified from official sources/PyPI; APScheduler and httpx already pinned in project
- Architecture: HIGH — patterns derived from existing codebase structure and official library docs
- Pitfalls: MEDIUM — most verified from official docs or direct codebase analysis; some (Discourse rate limits) are inferred

**Research date:** 2026-02-20
**Valid until:** 2026-03-20 (APIs are stable; asyncpraw/APScheduler change slowly)
