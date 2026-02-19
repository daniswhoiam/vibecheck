# Phase 2: Data Pipeline - Research

**Researched:** 2026-02-05
**Domain:** Backend data ingestion pipeline with scheduled API polling, entity normalization, and deduplication
**Confidence:** HIGH (core stack verified) / MEDIUM (AskNews SDK specifics, scheduler integration patterns)

## Summary

Phase 2 implements the scheduled data pipeline that continuously fetches news articles and story clusters from AskNews, normalizes entity names, and stores deduplicated data in PostgreSQL. This phase is critical because:

1. **Data pipeline is the product's core** — Without reliable ingestion, sentiment tracking fails
2. **Silent failures are expensive** — Scheduler bugs, API cost overruns, and duplicate data accumulation go unnoticed
3. **Entity normalization must be correct from day 1** — Retroactive fixing of fragmented data is painful
4. **Deduplication strategy must handle edge cases** — External IDs vary, URLs change, content hashes require care

The standard approach uses **APScheduler's AsyncIOScheduler** for scheduling (same process as FastAPI), **AskNews Python SDK** with OAuth2 client credentials for API access, **tenacity** for robust retry logic with exponential backoff, and **explicit application-level deduplication** with URL hashing and external_id checks.

**Primary recommendation:** Build entity normalization rules FIRST (test against real AskNews data), then implement scheduler with comprehensive logging and health checks, then add deduplication. Do not deploy without proven entity mapping and scheduler reliability.

---

## Standard Stack

### Core Libraries

| Library | Version | Purpose | Why Standard | Confidence |
|---------|---------|---------|--------------|------------|
| **asknews** | 0.4.0+ | AskNews Python SDK for /news and /stories endpoints | Official, maintained, OAuth2 built-in, prompt-optimized responses | HIGH |
| **APScheduler** | 3.10+ | AsyncIOScheduler for 15-min and 60-min polling jobs | Lightweight, async-native, SQLAlchemy backend for persistence, no message broker overhead for 2 jobs | HIGH |
| **tenacity** | 8.2+ | Exponential backoff retry decorator for API calls | Industry standard, async support, configurable stop/wait strategies | HIGH |
| **httpx** | 0.27+ | Async HTTP client (if direct API calls needed) | Modern, async-first, connection pooling, session reuse | HIGH |
| **structlog** | 24.1+ | Structured JSON logging for scheduler + pipeline | Essential for observability, key-value context, timestamps | MEDIUM |

### Supporting Libraries

| Library | Version | Purpose | When to Use | Confidence |
|---------|---------|---------|-------------|------------|
| **hashlib** | Built-in | SHA256 hashing for URL deduplication | Article deduplication without UNIQUE constraints | HIGH |
| **asyncpg** | 0.30+ | PostgreSQL async driver (already in Phase 1) | Non-blocking database operations in async jobs | HIGH |
| **sqlalchemy** | 2.0+ | ORM for Article/Story/SentimentTimeseries writes (already in Phase 1) | Consistent with Phase 1, transaction support | HIGH |
| **python-dateutil** | 2.8+ | Timezone handling (UTC conversion) | Ensure all timestamps in UTC for consistency | MEDIUM |

### Why NOT Certain Choices

| Technology | Why We Don't Use | Better Alternative |
|-----------|-----------------|-------------------|
| **Celery + Redis** | Overkill for 2 simple recurring tasks (~100 jobs/day). Adds message broker, worker processes, operational complexity. | APScheduler (lighter) now, upgrade to Celery if 1000+ jobs/day |
| **Manual cron jobs** | Hard to monitor, debug, and observe. Silent failures common. | APScheduler with job execution logging |
| **Custom backoff logic** | Reinventing retry strategy error-prone (off-by-one, jitter bugs). | tenacity library (battle-tested) |
| **URL UNIQUE constraints** | Blocks bulk inserts, slow for deduplication checks. | Application-level checks + content hash |
| **Custom entity matching** | Regex/substring matching fragile. Won't catch all variations. | Curated ENTITY_VARIATIONS dict + normalization function |

---

## Architecture Patterns

### Pattern 1: AsyncIOScheduler in FastAPI Lifespan

**What:** Start APScheduler's AsyncIOScheduler in FastAPI app startup, shut down on app shutdown.

**When to use:** Always for Phase 2. Simple integration, same process, single container deployment.

**Example:**
```python
# backend/main.py
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

scheduler = AsyncIOScheduler(timezone='UTC')

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting scheduler")
    scheduler.start()

    # Verify jobs are registered
    jobs = scheduler.get_jobs()
    if not jobs:
        logger.warning("No jobs registered!")
    else:
        logger.info(f"Scheduler started with {len(jobs)} jobs")

    yield

    # Shutdown
    logger.info("Shutting down scheduler")
    scheduler.shutdown(wait=True)

app = FastAPI(lifespan=lifespan)

# In startup event, add jobs:
@app.on_event("startup")
async def setup_jobs():
    scheduler.add_job(
        poll_news_job,
        "interval",
        minutes=15,
        id="poll_news",
        name="Poll AskNews News Endpoint",
        max_instances=1,  # Only one runs at a time
        coalesce=True,    # Skip missed runs if overloaded
        misfire_grace_time=60,  # Don't run if >1min late
    )
    scheduler.add_job(
        poll_stories_job,
        "interval",
        hours=1,
        id="poll_stories",
        name="Poll AskNews Stories Endpoint",
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60,
    )
```

**Source:** [APScheduler documentation](https://apscheduler.readthedocs.io/en/3.x/userguide.html), verified community implementations

---

### Pattern 2: Async Job with Retry Logic and Structured Logging

**What:** Implement scheduled job as async function with tenacity retry decorator and per-job execution tracking.

**When to use:** Every scheduled job. Ensures resilience and observability.

**Example:**
```python
# backend/pipeline/jobs/news_job.py
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from datetime import datetime, UTC
import uuid
import structlog

logger = structlog.get_logger()

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=16),
    retry=retry_if_exception_type((TimeoutError, ConnectionError)),
    reraise=True
)
async def fetch_from_asknews_with_retry(entity_name: str):
    """Fetch news from AskNews with exponential backoff on transient errors."""
    try:
        async with asknews_client() as client:
            response = await client.news.search(
                query=entity_name,
                string_guarantee=[entity_name],
                limit=10
            )
            return response
    except Exception as e:
        logger.error("asknews_fetch_failed", entity=entity_name, error=str(e))
        raise

async def poll_news_job():
    """Scheduled job: fetch news every 15 minutes."""
    execution_id = str(uuid.uuid4())
    start_time = datetime.now(UTC)

    logger.info("poll_news_job_started",
        execution_id=execution_id,
        timestamp=start_time.isoformat()
    )

    try:
        articles_count = 0

        for entity_name in CURATED_ENTITIES:
            try:
                articles = await fetch_from_asknews_with_retry(entity_name)
                processed = await process_and_store_articles(articles, entity_name)
                articles_count += len(processed)

                logger.info("entity_processed",
                    execution_id=execution_id,
                    entity=entity_name,
                    articles_found=len(articles),
                    articles_stored=len(processed)
                )
            except Exception as e:
                logger.error("entity_processing_failed",
                    execution_id=execution_id,
                    entity=entity_name,
                    error=str(e),
                    exc_info=True
                )
                # Continue with next entity instead of failing entire job
                continue

        duration = (datetime.now(UTC) - start_time).total_seconds()
        logger.info("poll_news_job_completed",
            execution_id=execution_id,
            articles_stored=articles_count,
            duration_seconds=duration,
            status="success"
        )

    except Exception as e:
        duration = (datetime.now(UTC) - start_time).total_seconds()
        logger.error("poll_news_job_failed",
            execution_id=execution_id,
            duration_seconds=duration,
            error=str(e),
            exc_info=True
        )

        # Log to database for audit trail
        await db.execute("""
            INSERT INTO scheduler_execution_log
            (execution_id, job_name, status, error, duration_seconds)
            VALUES (%s, %s, %s, %s, %s)
        """, (execution_id, "poll_news", "failure", str(e), duration))

        raise
```

**Source:** [Tenacity documentation](https://tenacity.readthedocs.io/), APScheduler patterns from STACK.md

---

### Pattern 3: Entity Normalization at Insertion Time

**What:** Map extracted entity names from AskNews to canonical names before storing in database.

**When to use:** Every article insertion. Prevents entity name fragmentation.

**Example:**
```python
# backend/pipeline/constants.py
ENTITY_VARIATIONS = {
    'gpt_4o': {
        'canonical': 'GPT-4o',
        'variations': [
            'GPT-4o', 'GPT 4o', 'gpt-4o', 'GPT4o', 'GPT-4-O',
            "OpenAI's GPT-4o", 'GPT-4o mini', 'GPT 4o mini'
        ]
    },
    'claude': {
        'canonical': 'Claude',
        'variations': [
            'Claude', 'claude', 'Anthropic Claude', 'Claude 3',
            'Claude Opus', 'Claude Sonnet', 'Claude Haiku', 'claude-opus'
        ]
    },
    'gemini': {
        'canonical': 'Gemini',
        'variations': [
            'Gemini', 'Google Gemini', 'Gemini 1.5', 'gemini-pro'
        ]
    },
    'cursor': {
        'canonical': 'Cursor',
        'variations': [
            'Cursor', 'cursor', 'Cursor IDE', 'Anysphere Cursor', 'cursor-ai'
        ]
    },
    'v0': {
        'canonical': 'v0',
        'variations': [
            'v0', 'Vercel v0', 'v0.dev'
        ]
    },
    # ... 5 more entities (total 10)
}

# backend/pipeline/services/entity_service.py
async def normalize_entity_name(extracted_name: str) -> str | None:
    """Map extracted entity name to canonical form, or None if not in curated list."""
    if not extracted_name:
        return None

    normalized = extracted_name.strip().lower()

    for entity_key, entity_data in ENTITY_VARIATIONS.items():
        for variation in entity_data['variations']:
            # Bidirectional matching: "GPT 4o" matches "GPT-4o" and vice versa
            if variation.lower() in normalized or normalized in variation.lower():
                return entity_data['canonical']

    return None  # Not in curated list

async def insert_article_with_normalized_entity(article_data: dict) -> bool:
    """Insert article, normalizing entity name. Return True if inserted, False if skipped."""
    canonical_entity = normalize_entity_name(article_data.get('entity_name'))

    if not canonical_entity:
        logger.debug("article_entity_not_curated",
            extracted_entity=article_data.get('entity_name'),
            title=article_data.get('title')
        )
        return False  # Skip articles about non-curated entities

    # Store both original and normalized names for audit trail
    try:
        async with db.transaction():
            await db.execute("""
                INSERT INTO articles
                (external_id, entity_name, extracted_entity_name, title, sentiment, source_url)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (external_id) DO NOTHING
            """, (
                article_data.get('external_id'),
                canonical_entity,
                article_data.get('entity_name'),
                article_data.get('title'),
                article_data.get('sentiment'),
                article_data.get('url')
            ))
        return True
    except Exception as e:
        logger.error("article_insert_failed", error=str(e), exc_info=True)
        return False
```

**Source:** Derived from PITFALLS.md entity matching patterns, verified via NLP research

---

### Pattern 4: URL-Based Deduplication with Content Hash

**What:** Check for duplicates using external_id (primary), then URL hash (secondary) before inserting.

**When to use:** Every article/story insertion. Prevents duplicate accumulation.

**Example:**
```python
# backend/pipeline/services/deduplication_service.py
import hashlib

async def compute_url_hash(url: str) -> str:
    """Generate SHA256 hash of URL for deduplication."""
    return hashlib.sha256(url.encode()).hexdigest()

async def check_article_exists(external_id: str, url: str) -> bool:
    """Check if article already exists via external_id or URL hash."""
    # Primary check: external_id (most reliable)
    existing = await db.fetchval(
        "SELECT 1 FROM articles WHERE external_id = %s LIMIT 1",
        (external_id,)
    )
    if existing:
        logger.debug("article_duplicate_by_external_id", external_id=external_id)
        return True

    # Secondary check: URL hash (handles URL variations)
    url_hash = compute_url_hash(url)
    existing = await db.fetchval(
        "SELECT 1 FROM articles WHERE url_hash = %s LIMIT 1",
        (url_hash,)
    )
    if existing:
        logger.debug("article_duplicate_by_url", url=url[:50])
        return True

    return False

async def batch_insert_articles(articles: list[dict]) -> int:
    """Insert articles, skipping duplicates. Return count of inserted articles."""
    if not articles:
        return 0

    # Filter out duplicates before batch insert
    to_insert = []
    for article in articles:
        exists = await check_article_exists(
            article.get('external_id'),
            article.get('url')
        )
        if not exists:
            to_insert.append(article)

    if not to_insert:
        logger.debug("all_articles_already_exist", count=len(articles))
        return 0

    # Batch insert (much faster than row-by-row)
    query = """
        INSERT INTO articles
        (external_id, url, url_hash, entity_name, title, sentiment, source_url, published_at)
        VALUES %s
        ON CONFLICT (external_id) DO NOTHING
    """

    values = [
        (
            a.get('external_id'),
            a.get('url'),
            compute_url_hash(a.get('url')),
            a.get('entity_name'),
            a.get('title'),
            a.get('sentiment'),
            a.get('source_url'),
            a.get('published_at')
        )
        for a in to_insert
    ]

    from psycopg import sql

    async with db.transaction():
        result = await db.execute(
            sql.SQL(query),
            values
        )

    logger.info("batch_insert_completed",
        attempted=len(articles),
        duplicates_skipped=len(articles) - len(to_insert),
        inserted=len(to_insert)
    )

    return len(to_insert)
```

**Source:** PITFALLS.md deduplication patterns, PostgreSQL best practices

---

### Pattern 5: Job Execution Logging and Health Checks

**What:** Track every job execution (start, end, status, duration, errors) in database and expose health endpoint.

**When to use:** Production deployments. Enables monitoring and debugging.

**Example:**
```python
# backend/pipeline/scheduler.py
import asyncio

# Track last execution time per job in memory
job_last_run = {}

async def get_job_health() -> dict:
    """Check health of scheduled jobs."""
    now = datetime.now(UTC)
    health = {
        'status': 'healthy',
        'jobs': {}
    }

    expected_intervals = {
        'poll_news': 15 * 60,  # 15 minutes in seconds
        'poll_stories': 60 * 60,  # 60 minutes in seconds
    }

    for job_name, expected_interval in expected_intervals.items():
        last_run = job_last_run.get(job_name)

        if last_run is None:
            health['jobs'][job_name] = {
                'status': 'not_started',
                'last_run': None
            }
        else:
            age_seconds = (now - last_run).total_seconds()
            threshold_seconds = expected_interval * 2  # Alert if 2x overdue

            status = 'healthy' if age_seconds < threshold_seconds else 'unhealthy'
            health['jobs'][job_name] = {
                'status': status,
                'last_run': last_run.isoformat(),
                'age_seconds': age_seconds
            }

            if status == 'unhealthy':
                health['status'] = 'unhealthy'

    return health

# In main.py, expose health endpoint
@app.get("/health/scheduler")
async def scheduler_health():
    """Health check for scheduler jobs."""
    health = await get_job_health()
    status_code = 200 if health['status'] == 'healthy' else 503
    return JSONResponse(health, status_code=status_code)

# Wrap job execution with logging
async def poll_news_job_with_tracking():
    job_last_run['poll_news'] = datetime.now(UTC)
    try:
        await poll_news_job()
    except Exception as e:
        logger.exception("poll_news_job_exception", error=str(e))
        raise

# Register wrapped version
scheduler.add_job(
    poll_news_job_with_tracking,
    "interval",
    minutes=15,
    id="poll_news",
    max_instances=1,
)
```

**Source:** PITFALLS.md scheduler reliability patterns, FastAPI health check patterns

---

## Don't Hand-Roll

Problems that look simple but have existing, battle-tested solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|------------|------------|-----|
| **Retry logic with backoff** | Custom sleep loops, random.jitter, max attempt counting | [tenacity library](https://tenacity.readthedocs.io/) | Edge cases: exponential overflow, jitter distribution, exception filtering |
| **Entity matching variations** | Regex patterns for each entity | Curated ENTITY_VARIATIONS dict + bidirectional substring matching | News text has subtle variations (spacing, punctuation, abbreviations) you won't anticipate |
| **URL deduplication** | UNIQUE constraint on url column | Application-level hash check + external_id UNIQUE | UNIQUE constraints block bulk inserts; hashing is faster and more flexible |
| **Scheduled job observability** | Printf debugging with timestamps | Structured logging (structlog) + health endpoint | Silent failures common without logging; structlog captures context (entity, count, duration) |
| **API rate limit handling** | Hope the API docs are right | Read response headers (X-RateLimit-Remaining) and implement backoff | APIs lie in docs; real behavior discovered in production via headers |

**Key insight:** AskNews API polling is where silent failures cause damage. Use battle-tested libraries (tenacity, structlog) not custom code. Entity matching is where manual curation beats algorithms. Deduplication is where application logic beats database constraints (at scale).

---

## Common Pitfalls

### Pitfall 1: Silent Scheduler Failures (CRITICAL)

**What goes wrong:**
- Job runs but database connection is dead → silent rollback, no alert
- Job crashes with exception → caught by scheduler, logged, but no monitoring alerts
- Data collection stops after server restart → scheduler initialization failed silently
- Job runs multiple times simultaneously → clock skew or missed max_instances=1 check

**Why it happens:**
- Schedulers are fire-and-forget systems designed for minimal overhead
- No observability by default — job execution is invisible unless you instrument it
- Single developer with one running instance means scheduler crashes = data collection stops

**Prevention:**
1. **Add explicit health check endpoint** that reports when each job last ran
2. **Log job start, completion, and failure** with execution_id, entity count, duration
3. **Set max_instances=1, misfire_grace_time=60** to prevent concurrent runs
4. **Store execution log in database** for audit trail and monitoring

**Warning signs:**
- [ ] Data gaps in sentiment_timeseries (no articles for days)
- [ ] Duplicate articles appearing (job ran twice simultaneously)
- [ ] No logs from scheduled jobs in past 24 hours
- [ ] Health check endpoint returning unhealthy but app still running

---

### Pitfall 2: Unexpected API Cost Overruns (CRITICAL)

**What goes wrong:**
- Retry logic retrying failed requests exponentially → 5 retries × 10 entities = 50 API calls instead of 10
- Testing queries against production AskNews API → $5-10 per test run
- Job gets queued up (scheduler hung) → jobs pile up, all make API calls when scheduler resumes
- Entity filtering too broad → search "GPT" matches "GPT-4o", "GPT-4", "GPT-J", "GPT-2" = 4x calls
- Budget invisible until bill arrives → spending $800/month instead of $250/month

**Why it happens:**
- "I'll just retry if it fails" without considering exponential backoff implications
- No in-process tracking of API call counts
- AskNews rate limiting not respected (reading response headers)

**Prevention:**
1. **Hard cap on API calls** with counter that stops scheduling when threshold is hit
2. **Explicit retry policy**: max 3 retries, exponential backoff (1s, 4s, 16s), jitter
3. **Respect API rate limit headers** (X-RateLimit-Remaining) and back off accordingly
4. **Test with fixtures, not live API** during development
5. **Log total daily API call count** at end of day for visibility

**Warning signs:**
- [ ] Monthly billing spike without corresponding data growth
- [ ] API rate limit errors (429 responses) in logs
- [ ] Same entity records appearing multiple times from same time window

---

### Pitfall 3: Entity Name Fragmentation (CRITICAL)

**What goes wrong:**
- News about "Claude" appears as "Claude", "Claude 3", "Claude Opus", "Anthropic Claude"
- Same entity appears under 10 different names in database
- Sentiment averages are wrong because data is split across variants
- Retroactive fixing requires full re-processing of 6 months of data

**Why it happens:**
- News writers use variations naturally (abbreviations, full names, company names)
- Name variations not discovered until you have real data
- No validation of entity matching before production

**Prevention:**
1. **Define ENTITY_VARIATIONS dict upfront** with all known variations
2. **Test entity normalization against real articles** before deploying
3. **Normalize at insertion time** (map all variations to canonical name)
4. **Store extracted_entity_name alongside normalized name** for audit trail
5. **Quarterly audit of unmapped entities** to catch new variations

**Warning signs:**
- [ ] Entity sentiment averages change dramatically when new variation appears
- [ ] User reports "missing articles about X entity"
- [ ] Database has 50 similar-but-different entity names instead of 10

---

### Pitfall 4: Deduplication Failures (HIGH)

**What goes wrong:**
- Same article inserted twice with different external_id variations
- URL slightly changes (trailing slash, utm_source parameter) → same content, different row
- No UNIQUE constraint → bulk inserts fast, but duplicates accumulate
- UNIQUE constraint on url → blocks bulk inserts, slows down entire pipeline

**Why it happens:**
- External IDs vary by API response (sometimes missing, sometimes formatted differently)
- URLs have parameters that change (utm_source, session ID) but content is same
- Assuming one deduplication strategy covers all cases

**Prevention:**
1. **Primary check: external_id (most reliable)** if AskNews provides consistent IDs
2. **Secondary check: URL hash (handles parameter variations)**
3. **Never use UNIQUE constraint on URL** — check application logic instead
4. **Batch insert with ON CONFLICT DO NOTHING** instead of row-by-row checks

**Warning signs:**
- [ ] Same article appearing in database with different IDs
- [ ] Duplicate count growing linearly with article count

---

### Pitfall 5: Timezone Inconsistencies (MEDIUM)

**What goes wrong:**
- Some timestamps stored in UTC, others in app's local time
- Aggregations group by "day" but midnight varies by timezone
- User sees "sentiment for today" but it's actually "sentiment for UTC today"

**Prevention:**
1. **All timestamps in UTC** (`TIMESTAMP WITH TIME ZONE`)
2. **All calculations in UTC**
3. **Convert to user's timezone only in API response**

---

## Code Examples

### AskNews SDK OAuth2 Authentication and Usage

```python
# backend/pipeline/asknews_client.py
from asknews_sdk import AskNewsSDK
from datetime import datetime, UTC
import structlog

logger = structlog.get_logger()

class AskNewsClient:
    def __init__(self, api_key: str):
        self.client = AskNewsSDK(
            api_key=api_key,
            scopes=["news", "stories"]  # Only request needed scopes
        )

    async def fetch_news(self, entity_name: str, limit: int = 10) -> list[dict]:
        """Fetch news articles for a single entity."""
        try:
            # Use string_guarantee to enforce that entity must appear in results
            response = await self.client.news.search_news(
                query=entity_name,
                string_guarantee=[entity_name],  # Must contain this string
                limit=limit
            )

            logger.info("asknews_news_fetched",
                entity=entity_name,
                articles_count=len(response.articles) if response.articles else 0
            )

            # Transform response to standard format
            articles = []
            if response.articles:
                for article in response.articles:
                    articles.append({
                        'external_id': getattr(article, 'id', None),
                        'title': getattr(article, 'title', ''),
                        'entity_name': entity_name,
                        'sentiment': getattr(article, 'sentiment', None),
                        'url': getattr(article, 'url', ''),
                        'source_url': getattr(article, 'source_url', ''),
                        'published_at': getattr(article, 'published_at', datetime.now(UTC)),
                    })

            return articles

        except Exception as e:
            logger.error("asknews_news_failed",
                entity=entity_name,
                error=str(e),
                exc_info=True
            )
            raise

    async def fetch_stories(self, entity_name: str) -> list[dict]:
        """Fetch story clusters for a single entity."""
        try:
            response = await self.client.stories.search_stories(
                query=entity_name,
                limit=10
            )

            stories = []
            # Process story clusters and extract sentiment time-series
            # (Implementation depends on AskNews /stories response structure)

            return stories

        except Exception as e:
            logger.error("asknews_stories_failed",
                entity=entity_name,
                error=str(e),
                exc_info=True
            )
            raise

# Usage in job:
async def poll_news_job():
    client = AskNewsClient(api_key=os.getenv("ASKNEWS_API_KEY"))

    for entity in CURATED_ENTITIES:
        articles = await client.fetch_news(entity)
        await process_articles(articles)
```

**Source:** [AskNews Python SDK documentation](https://github.com/emergentmethods/asknews-python-sdk)

---

### Tenacity Retry with Exponential Backoff

```python
# backend/pipeline/services/retry_service.py
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    retry_if_exception,
    wait_random_exponential
)
import asyncio

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=16),
    retry=retry_if_exception_type((asyncio.TimeoutError, ConnectionError)),
    reraise=True,
    before_sleep=lambda retry_state: logger.warning(
        "retry_attempt",
        attempt=retry_state.attempt_number,
        wait_seconds=retry_state.next_action.sleep
    )
)
async def call_asknews_with_retry(func, *args, **kwargs):
    """Call AskNews API with exponential backoff on transient errors."""
    return await func(*args, **kwargs)

# For more granular control:
@retry(
    stop=stop_after_attempt(3),
    wait=wait_random_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception(lambda e: e.response.status_code in (408, 429, 500, 502, 503)),
    reraise=True
)
async def call_asknews_respecting_rates(client, query):
    """Call AskNews with retry on specific status codes."""
    response = await client.news.search_news(query=query)

    # Respect rate limit headers
    remaining = int(response.headers.get('X-RateLimit-Remaining', -1))
    if remaining == 0:
        logger.warning("rate_limit_exhausted")
        # Backoff handled automatically by tenacity

    return response
```

**Source:** [Tenacity documentation](https://tenacity.readthedocs.io/)

---

### Structured Logging with Structlog

```python
# backend/config/logging.py
import structlog
from datetime import datetime, UTC

# Configure structlog for JSON output
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Usage in jobs:
async def poll_news_job():
    execution_id = str(uuid.uuid4())
    start_time = datetime.now(UTC)

    logger.info("poll_news_start",
        execution_id=execution_id,
        timestamp=start_time.isoformat(),
        entities_count=len(CURATED_ENTITIES)
    )

    articles_stored = 0
    errors = []

    for entity in CURATED_ENTITIES:
        try:
            articles = await fetch_news(entity)
            stored = await store_articles(articles)
            articles_stored += len(stored)

            logger.info("entity_processed",
                execution_id=execution_id,
                entity=entity,
                articles_found=len(articles),
                articles_stored=len(stored)
            )
        except Exception as e:
            logger.error("entity_failed",
                execution_id=execution_id,
                entity=entity,
                error=str(e),
                exc_info=True
            )
            errors.append((entity, str(e)))

    duration = (datetime.now(UTC) - start_time).total_seconds()

    status = "success" if not errors else "partial_failure"
    logger.info("poll_news_complete",
        execution_id=execution_id,
        status=status,
        articles_stored=articles_stored,
        errors_count=len(errors),
        duration_seconds=duration
    )
```

**Source:** [Structlog documentation](https://www.structlog.org/), industry logging best practices

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|-----------------|--------------|--------|
| **Cron jobs** | APScheduler with in-process scheduling | ~2020s | Better observability, easier to monitor and debug |
| **Manual retry loops** | tenacity decorator library | ~2015+ | Standardized exponential backoff, less error-prone |
| **Unstructured string logs** | Structured JSON logging (structlog) | ~2020s | Searchable logs, context preservation, easier parsing |
| **Database constraints for uniqueness** | Application-level deduplication | ~2010s (rediscovered) | Better performance at scale, more flexible |
| **Monolithic schedulers (Celery)** | Lightweight schedulers (APScheduler) for simple cases | ~2020s | Lower operational overhead for <1000 jobs/day |

**Deprecated/outdated:**
- **Custom retry logic:** Modern libraries (tenacity) handle exponential backoff better
- **Manual scheduling via cron + SystemD:** APScheduler provides better observability
- **Synchronous AskNews calls:** Async/await is now standard in Python data pipelines

---

## Open Questions

1. **AskNews `/stories` endpoint response structure**
   - What we know: Returns story clusters with sentiment time-series and Reddit data
   - What's unclear: Exact JSON schema, how sentiment is aggregated across clusters, Reddit thread structure
   - Recommendation: Fetch live response from AskNews /stories endpoint, inspect structure, design SentimentTimeseries storage accordingly

2. **External ID consistency in AskNews**
   - What we know: Articles have external_id field
   - What's unclear: Is external_id always unique per article? Can it change between requests for same article?
   - Recommendation: In first week of production, log external_id collisions and URL changes to validate deduplication strategy

3. **Rate limit enforcement on Spelunker tier**
   - What we know: Spelunker tier is $250/mo with 1,500 base requests
   - What's unclear: How are requests counted (per /news call or per entity searched)? Is there burst capacity?
   - Recommendation: Implement counter and test with 1-week baseline before declaring budget reliable

---

## Sources

### Primary (HIGH confidence)

- **APScheduler 3.10+ documentation** - Async job scheduling, scheduler lifecycle, job configuration
  - https://apscheduler.readthedocs.io/
  - [APScheduler AsyncIOScheduler integration with FastAPI](https://www.nashruddinamin.com/blog/running-scheduled-jobs-in-fastapi)
  - [APScheduler job execution events and logging](https://betterstack.com/community/guides/scaling-python/apscheduler-scheduled-tasks/)

- **AskNews SDK documentation** - API endpoints, authentication, response structure
  - https://docs.asknews.app/en
  - https://github.com/emergentmethods/asknews-python-sdk
  - https://pypi.org/project/asknews/

- **Tenacity retry library** - Exponential backoff, async support, exception filtering
  - https://tenacity.readthedocs.io/
  - https://github.com/jd/tenacity

- **Structlog documentation** - Structured JSON logging, context preservation
  - https://www.structlog.org/

### Secondary (MEDIUM confidence)

- **PostgreSQL deduplication strategies** - Hash-based deduplication, ON CONFLICT handling
  - https://www.alibabacloud.com/blog/postgresql-data-deduplication-methods_596032
  - https://neon.com/postgresql/postgresql-tutorial/how-to-delete-duplicate-rows-in-postgresql

- **Entity normalization in NLP** - Name variation handling, entity linking
  - https://arxiv.org/abs/2406.15483 (Duplicate Detection with GenAI)
  - https://bmcbioinformatics.biomedcentral.com/articles/10.1186/s12859-017-1857-8

### Project Context (from existing docs)

- STACK.md - Technology selections (APScheduler 3.10+, httpx 0.27+)
- ARCHITECTURE.md - Layered architecture, scheduler patterns, async patterns
- PITFALLS.md - Critical failure modes (API costs, scheduler reliability, entity fragmentation)

---

## Metadata

**Confidence breakdown:**
- **Standard stack:** HIGH - APScheduler, AskNews SDK, tenacity are established patterns with current documentation
- **Architecture patterns:** HIGH - APScheduler + FastAPI lifespan is standard integration, async job patterns verified
- **Pitfalls:** HIGH - Based on domain knowledge and PITFALLS.md detailed analysis
- **AskNews specifics:** MEDIUM - SDK API verified but edge cases (external_id consistency, rate limiting) require validation in Phase 2

**Research date:** 2026-02-05
**Valid until:** 2026-03-05 (library updates common, but async patterns stable)
**Libraries requiring version checks:** asknews-python-sdk (verify current version > 0.4.0), APScheduler (verify 3.10+)

---

## Recommended Reading Order

1. **Start here:** PITFALLS.md sections on "Silent Scheduler Failures" and "API Cost Overruns" (understand what to prevent)
2. **Then read:** ARCHITECTURE.md section on "Async Patterns: Scheduled Jobs + Request Handling" (understand async execution model)
3. **Then read:** This RESEARCH.md sections on Standard Stack and Code Examples (understand implementation patterns)
4. **Finally:** Plan Phase 2 with specific focus on entity normalization testing and scheduler health checks
