# Technology Stack: VibeCheck Backend

**Project:** VibeCheck (Python data pipeline + FastAPI backend)
**Researched:** February 2026
**Knowledge Cutoff:** February 2025
**Overall Confidence:** MEDIUM-HIGH (FastAPI/SQLAlchemy HIGH, TimescaleDB choice MEDIUM, task scheduling MEDIUM)

## Recommended Stack

### Core Framework & API

| Technology | Version | Purpose | Why | Confidence |
|-----------|---------|---------|-----|------------|
| **FastAPI** | 0.115+ | REST API framework, async request handling | Modern async-first framework, automatic OpenAPI docs, excellent type hints support, ideal for data pipelines. Faster than Flask/Django for this use case. | HIGH |
| **Uvicorn** | 0.30+ | ASGI server | Standard, high-performance async server for FastAPI in production. Actively maintained. | HIGH |
| **Pydantic** | 2.7+ | Data validation & serialization | Built into FastAPI, excellent for request/response validation, including custom validators for sentiment scores (-1 to +1 range). | HIGH |
| **Python** | 3.11+ (target 3.12) | Runtime | 3.11 has excellent async/await support; 3.12 added performance improvements. FastAPI requires 3.8+, but 3.11+ recommended for production. | HIGH |

### Database & Data Layer

| Technology | Version | Purpose | Why | Confidence |
|-----------|---------|---------|-----|------------|
| **PostgreSQL** | 16+ | Primary data store | Time-series data via table design (not TimescaleDB for MVP). Better than alternatives because: excellent query performance for time-series aggregations, proven at scale, JSONB support for flexible sentiment/metadata storage. | HIGH |
| **SQLAlchemy** | 2.0+ (>=2.0.35) | ORM & database abstraction | Mature, async support via asyncpg, excellent migration tooling with Alembic. 2.0+ has cleaner syntax. Avoid SQLModel (thin wrapper, less mature). Better than Tortoise (not as battle-tested at scale). | HIGH |
| **asyncpg** | 0.30+ | PostgreSQL async driver | Fastest Python PostgreSQL driver; essential for non-blocking async queries with FastAPI. | HIGH |
| **Alembic** | 1.14+ | Database migrations | SQLAlchemy-integrated migration tool, essential for production deployments. | HIGH |

### Scheduled Tasks & Data Ingestion

| Technology | Version | Purpose | Why | Confidence |
|-----------|---------|---------|-----|------------|
| **APScheduler** | 3.10+ | Lightweight job scheduling | For 2 simple recurring tasks (news every 15min, stories hourly): APScheduler is sufficient and lighter-weight. Built-in backfill and persistence. No message broker needed at this scale (~100 jobs/day). | MEDIUM |
| **Background Tasks** | FastAPI built-in | Non-blocking background operations | Use FastAPI's BackgroundTasks for one-off operations (e.g., post-response cleanup). | HIGH |
| **Redis** (optional, Phase 2) | 7.0+ | Cache + job result storage | Consider for Phase 2 if you add WebSocket updates or distributed deployments. Skip for MVP. | N/A |

**Scheduling rationale:** APScheduler chosen over Celery because:
- Celery adds complexity (message broker, worker processes) not justified at 100 scheduled jobs/day
- No distributed worker pool needed yet (single Python process sufficient)
- APScheduler has persistent job state (SQLAlchemy backend) for recovery
- Can upgrade to Celery later without major refactoring (abstract task layer)

### Supporting Libraries

| Library | Version | Purpose | When to Use | Confidence |
|---------|---------|---------|------------|------------|
| **httpx** | 0.27+ | HTTP client (AskNews API) | Async HTTP with connection pooling. Superior to requests for async code. Use with httpx.AsyncClient context manager. | HIGH |
| **python-dotenv** | 1.0+ | Environment config | Load .env files for API keys, DB connection strings. Standard for 12-factor apps. | HIGH |
| **Structlog** | 24.1+ | Structured logging | JSON logging for parsing in production. Better than built-in logging for time-series data context (timestamps, entity IDs). | MEDIUM |
| **Pytest** | 8.0+ | Testing framework | Standard Python testing tool. Use pytest-asyncio for async tests. | HIGH |
| **pytest-asyncio** | 0.24+ | Async test support | Essential for testing FastAPI routes and async database queries. | HIGH |
| **Coverage.py** | 7.4+ | Code coverage | Measure test coverage (target 80%+). | MEDIUM |
| **black** | 24.1+ | Code formatting | Standard formatter for Python projects. Zero-config, opinionated. | MEDIUM |
| **ruff** | 0.2+ | Linting | Modern, fast linter replacing flake8/isort/pylint. Replaces black+flake8 stack. | MEDIUM |

### Why NOT certain choices

| Technology | Why We Don't Use | Alternative |
|-----------|-----------------|------------|
| **TimescaleDB** | Premature optimization. PostgreSQL with proper indexing handles sentiment time-series well until 10M+ rows. TimescaleDB adds operational complexity (separate extension, learning curve, higher hosting costs). Use native PostgreSQL, migrate later if needed. | PostgreSQL with `created_at` indices and time-based partitioning (Phase 2) |
| **Celery** | Overkill for 2 simple recurring tasks. Requires message broker (Redis/RabbitMQ), worker processes, and operational overhead. APScheduler is lighter and sufficient at this scale. | APScheduler now, upgrade to Celery if you add 100+ tasks or distributed workers |
| **SQLModel** | Built on SQLAlchemy but thin wrapper. Less mature, smaller community. Adds complexity without benefit for this project. | SQLAlchemy 2.0 directly |
| **Tortoise ORM** | Less battle-tested at scale than SQLAlchemy. Smaller ecosystem, fewer integrations. Good for simple projects, but sentiment tracking needs robust ORM. | SQLAlchemy 2.0 |
| **Synchronous FastAPI** | Blocking I/O on each API call and database query. With AskNews calls + DB queries, would bottleneck. Async is essential. | Async FastAPI (all routes, all queries async) |
| **Django/DRF** | Heavyweight framework with built-in ORM. Better for traditional monolithic apps. FastAPI + SQLAlchemy is lighter, more modular, better for data pipelines. | FastAPI |
| **Scheduled Cron Jobs** | Hard to monitor, debug, and scale. No observability. Python-based scheduling (APScheduler) allows unified logging and error handling. | APScheduler |

## Stack Diagram

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (Vite + React + TypeScript)  [managed separately] │
└────────────────────┬────────────────────────────────────────┘
                     │ REST API calls (httpx from Python side)
                     ▼
┌─────────────────────────────────────────────────────────────┐
│                  FastAPI (Uvicorn)                          │
│  - Request validation (Pydantic)                            │
│  - Route handlers (async)                                  │
│  - OpenAPI docs auto-generated                             │
└────────┬────────────────────┬──────────────────┬────────────┘
         │                    │                  │
    ┌────▼────┐       ┌──────▼─────┐    ┌──────▼───────┐
    │ httpx   │       │SQLAlchemy  │    │ APScheduler  │
    │ Client  │       │ ORM async  │    │ (recurring   │
    │(AskNews)│       │ (asyncpg)  │    │  jobs)       │
    └────┬────┘       └──────┬─────┘    └──────┬───────┘
         │                   │                  │
         └───────────────────┴──────────────────┘
                     │
         ┌───────────▼──────────────┐
         │   PostgreSQL 16+         │
         │  (sentiment time-series) │
         └──────────────────────────┘
```

## Installation & Project Setup

### Core Dependencies

```bash
# Core FastAPI stack
pip install fastapi==0.115.0
pip install uvicorn[standard]==0.30.0
pip install pydantic==2.7.0

# Database
pip install sqlalchemy==2.0.35
pip install asyncpg==0.30.0
pip install alembic==1.14.0
pip install psycopg2-binary==2.9.9  # Also needed for non-async ops

# Data ingestion
pip install httpx==0.27.0
pip install asknews-python-sdk==0.4.0  # AskNews SDK

# Scheduling
pip install apscheduler==3.10.4

# Configuration & logging
pip install python-dotenv==1.0.0
pip install structlog==24.1.0

# Development & testing
pip install pytest==8.0.0
pip install pytest-asyncio==0.24.0
pip install pytest-cov==5.0.0
pip install black==24.1.1
pip install ruff==0.2.0
```

### Development Setup

```bash
# Create virtual environment
python3.12 -m venv venv
source venv/bin/activate

# Install all dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Fill in: DATABASE_URL, ASKNEWS_API_KEY, etc.

# Initialize database
alembic upgrade head

# Run tests
pytest --cov=app tests/

# Format code
black app/
ruff check app/

# Run development server
uvicorn app.main:app --reload
```

### Database Connection String

```python
# .env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/vibecheck_dev

# SQLAlchemy engine creation
from sqlalchemy.ext.asyncio import create_async_engine

engine = create_async_engine(
    os.getenv("DATABASE_URL"),
    echo=False,  # Set to True for SQL logging in development
    future=True,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # Verify connections before use
)
```

## Version Constraints & Compatibility

| Component | Min Version | Reason |
|-----------|------------|--------|
| Python | 3.11 | 3.10 works but lacks certain async optimizations |
| FastAPI | 0.115+ | Stable, recent fixes for async context handling |
| SQLAlchemy | 2.0+ | Required for async support via 2.0+ API |
| PostgreSQL | 14+ | 16+ recommended for JSON improvements |
| asyncpg | 0.29+ | Stability for production async queries |

## Deployment Considerations

### Production ASGI Server

```bash
# Use Gunicorn with Uvicorn workers for production
pip install gunicorn==21.2.0

# Run with multiple workers
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 60 \
  --access-logfile - \
  --error-logfile -
```

### Database Connection Pool

- SQLAlchemy pool_size=10, max_overflow=20 for ~50 concurrent requests
- Scale pool size proportionally: pool_size = (expected_concurrent_requests / 2)
- Use `pool_pre_ping=True` to verify stale connections in pool

### Environment Isolation

- Development: SQLite in-memory or local PostgreSQL with loose constraints
- Production: PostgreSQL 16+ with connection pooling, SSL enforcement
- Testing: Separate test database with truncation between test suites

## Migration from Alternatives

If you later need to switch:

| From | To | Effort | Reason |
|------|-----|--------|--------|
| APScheduler | Celery + Redis | Medium | Abstract task layer now, concrete implementation later |
| PostgreSQL | TimescaleDB | Low | Drop-in extension, same SQL dialect |
| SQLAlchemy | Tortoise ORM | High (not recommended) | Different ORM paradigm, would require rewrite |
| httpx | aiohttp | Low | Both async HTTP clients, similar APIs |

## High-Confidence Decisions

✓ **FastAPI + Uvicorn**: Industry standard for async Python APIs
✓ **SQLAlchemy 2.0 + asyncpg**: Mature, tested, best-in-class async ORM
✓ **PostgreSQL**: Proven time-series capabilities without TimescaleDB overhead
✓ **APScheduler**: Right-sized for 100 jobs/day, can upgrade later
✓ **Python 3.12**: Latest stable, excellent async/await performance

## Medium-Confidence Decisions

? **APScheduler over Celery**: True if you stay under 1000 jobs/day. Reassess if adding distributed processing
? **PostgreSQL over TimescaleDB**: True if aggregations stay under 100M rows. Reassess at scale
? **httpx over aiohttp**: Both solid; httpx slightly better DX, aiohttp slightly lighter

## Gaps & Phase 2 Candidates

- **Caching**: Redis for sentiment query caching (Phase 2)
- **Message queue**: RabbitMQ/Redis if adding WebSocket updates or distributed workers (Phase 2)
- **Monitoring**: Prometheus + Grafana for production metrics (Phase 2)
- **API rate limiting**: Use FastAPI middleware or external service (Phase 2)
- **Full-text search**: Elasticsearch if adding article search (Phase 2+)

## Sources

- FastAPI documentation: https://fastapi.tiangolo.com (knowledge cutoff Feb 2025)
- SQLAlchemy 2.0 migration guide: https://docs.sqlalchemy.org/en/20/ (2.0+ async stable)
- APScheduler docs: https://apscheduler.readthedocs.io (3.10+ recommended)
- asyncpg: https://magicstack.github.io/asyncpg (0.29+ production-ready)
- Uvicorn: https://www.uvicorn.org (0.29+ production-ready)

## Next Steps for Phase 1

1. Create FastAPI project structure (see ARCHITECTURE.md)
2. Set up PostgreSQL schema for articles, sentiment time-series, entities
3. Build AskNews API integration layer with httpx
4. Implement APScheduler jobs for 15-min news polling, hourly story polling
5. Create REST endpoints: sentiment history, entity comparison, trending entities
6. Write integration tests with pytest-asyncio

---

**Stack Summary:** Modern async Python (3.12) with FastAPI/SQLAlchemy/PostgreSQL, lightweight APScheduler for polling, zero unnecessary complexity. Right-sized for VibeCheck's data pipeline scale.

---

# v2.0 Stack Additions: Free Data Sources + Sentiment Pipeline

**Researched:** 2026-02-19
**Confidence:** HIGH
**Scope:** NEW libraries only — do not re-add what v1.0 already has.

## What Changes in v2.0

- Remove: `asknews` SDK and its httpx<0.26.0 constraint
- Upgrade: `httpx` from 0.25.2 to 0.28.1 (no longer version-constrained)
- Add: Reddit ingestion, HN/Discourse/Dev.to/GitHub via httpx (already available), local ML inference, LLM client

---

## New Core Libraries

### Data Ingestion — Reddit

| Library | Version | Purpose | Why Recommended |
|---------|---------|---------|-----------------|
| asyncpraw | 7.8.1 | Reddit API (r/LocalLLaMA, r/cursor, r/copilot, etc.) | Official async PRAW from praw-dev; integrates with existing asyncio/FastAPI event loop without blocking; handles OAuth, rate limiting, and token refresh automatically; same API as sync PRAW |

**Do not use sync `praw`** — it blocks the event loop. asyncpraw is the officially maintained async sibling from the same team.

HN Algolia API, Discourse REST API, Dev.to API, and GitHub REST API all use standard httpx (already in project, just upgraded).

### Sentiment Pipeline — Tier 1 (Local Transformer)

| Library | Version | Purpose | Why Recommended |
|---------|---------|---------|-----------------|
| transformers | 4.57.3 | Load and run `cardiffnlp/twitter-roberta-base-sentiment-latest` | Stable branch; v5.x RC is opt-in only — do not use v5 in production yet; 4.57.3 is tested against the cardiffnlp RoBERTa model family |
| torch (CPU-only) | 2.6.x | PyTorch inference backend | Install CPU-only wheel to avoid pulling 2-3GB of CUDA libraries into Docker image; 10-20 texts/second on CPU is sufficient for this post volume |
| scipy | >=1.11.0 | Softmax over RoBERTa logits | Required for the standard twitter-roberta preprocessing pattern; transitive dep of torch/sentence-transformers |

**Critical Dockerfile pattern — install torch before pip install -r requirements.txt:**
```dockerfile
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu --no-cache-dir
```
Without this explicit CPU index, pip pulls CUDA variants even inside a CPU-only container.

### Sentiment Pipeline — Relevance Filtering

| Library | Version | Purpose | Why Recommended |
|---------|---------|---------|-----------------|
| sentence-transformers | 5.2.3 | Semantic embeddings with `all-MiniLM-L6-v2` | Latest stable (Feb 17 2026); model is 22MB, 384-dimension, 14,200 sentences/second on CPU; cosine similarity at threshold 0.35-0.45 catches relevant posts without tool-name keyword matches |
| datasketch | 1.9.0 | MinHash near-duplicate detection | Latest stable; `num_perm=128, threshold=0.8` catches cross-posted content between HN/Reddit/Discourse; pure Python + NumPy, no extra infrastructure |

### Sentiment Pipeline — Tier 2 LLM Client

| Library | Version | Purpose | Why Recommended |
|---------|---------|---------|-----------------|
| openai | >=2.21.0 | OpenAI-compatible client for Groq or DeepInfra | Both Groq and DeepInfra expose identical OpenAI API format; swap `base_url` + `api_key` to switch providers with zero code changes; supports structured output / JSON mode for Pydantic schema extraction |

---

## Tier 2 Provider Selection

Use **Groq** as primary provider:
- Free tier, no credit card, fast (~500 tok/sec on Llama 3.3 70B)
- Endpoint: `https://api.groq.com/openai/v1`
- Models: `llama-3.1-8b-instant` for high volume, `llama-3.3-70b-versatile` for complex comparative posts
- Rate limits apply at org level (RPM + TPM); implement tenacity retry with exponential backoff on 429s

**DeepInfra** as fallback:
- Pay-per-token, very low cost
- Endpoint: `https://api.deepinfra.com/v1/openai`

**GPT-4o-mini** if quality matters over cost:
- ~$0.15/1M input tokens; ~$20-30/month at 10k posts/day with 40% Tier 2 routing

```python
from openai import AsyncOpenAI

client = AsyncOpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.environ["GROQ_API_KEY"],
)
```

---

## Updated requirements.txt Additions

```
# Remove from existing requirements.txt:
# asknews>=0.4.0
# httpx==0.25.2  (replace with below)

# Upgrade existing:
httpx==0.28.1

# Reddit ingestion
asyncpraw==7.8.1

# Tier 1 sentiment inference
# torch installed separately in Dockerfile with CPU-only index
transformers==4.57.3
scipy>=1.11.0

# Relevance filtering + dedup
sentence-transformers==5.2.3
datasketch==1.9.0

# Tier 2 LLM client (Groq/DeepInfra/OpenAI)
openai>=2.21.0
```

---

## What NOT to Add

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| praw (sync) | Blocks FastAPI event loop; identical API to asyncpraw | asyncpraw==7.8.1 |
| Full CUDA torch | Adds 2-3GB to Docker image; OOMs on Render Standard ($25) at 2GB RAM | `torch --index-url https://download.pytorch.org/whl/cpu` |
| transformers>=5.0 | v5 is RC-only as of Feb 2026; not production-stable | transformers==4.57.3 |
| groq (official SDK) | Redundant — openai client's base_url swap is identical; fewer deps | openai + base_url override |
| TimescaleDB / pgvector | Adds operational complexity; not needed for v2.0 MVP scale | Standard PostgreSQL 16 |
| Redis | Not needed; APScheduler already uses PostgreSQL; no distributed workers | requests-cache with SQLite if HTTP caching needed |
| VADER / TextBlob | Fail on developer sarcasm and technical comparisons | transformers pipeline (Tier 1) |
| SetFitABSA / PyABSA | Pre-trained on restaurant/laptop reviews; need fine-tuning; LLM covers this | Tier 2 LLM structured extraction |
| YouTube Data API | 1 quota unit/request but complex OAuth; low value vs HN+Reddit | Skip for v2.0; add in v3 if needed |

---

## Version Compatibility Matrix

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| transformers==4.57.3 | torch>=2.4, Python>=3.10 | Project uses Python 3.12 — compatible |
| sentence-transformers==5.2.3 | Python>=3.10, transformers 4.x | v5.x as of Feb 2026; Python 3.12 compatible |
| asyncpraw==7.8.1 | Python>=3.9 | asyncprawcore 3.0.2 transport layer |
| httpx==0.28.1 | Python>=3.8, openai>=2.x | Remove asknews first; 0.28.x drops `proxies` arg (not used) |
| openai>=2.21.0 | Python>=3.9, httpx (transitive) | httpx is a transitive dep; pin httpx==0.28.1 to avoid conflicts |
| datasketch==1.9.0 | Python>=3.9, numpy>=1.11 | numpy is already transitive dep of torch/sentence-transformers |

---

## Deployment Implications (Render)

### Memory Budget for v2.0

| Component | RAM |
|-----------|-----|
| twitter-roberta-base-sentiment-latest | ~500MB loaded |
| all-MiniLM-L6-v2 | ~100MB loaded |
| FastAPI + SQLAlchemy + asyncpg | ~150MB |
| OS + Python runtime | ~100MB |
| **Total** | **~850MB** |

**Render tier required:**

| Tier | RAM | Price | Suitable? |
|------|-----|-------|-----------|
| Free | 512MB | $0 | No — OOM |
| Starter | 512MB | $7/mo | No — OOM |
| Standard | 2GB | $25/mo | Yes — 1.15GB headroom |
| Pro | 4GB | $80/mo | Yes — if volume grows |

**Upgrade to Standard ($25/month) is required for v2.0.** Free and Starter tiers will OOM when loading both ML models.

### Model Cold Start Strategy

Models download from HuggingFace Hub on first run (~600MB total). On Render, the container filesystem is ephemeral — models re-download on each new deploy. Options:

1. **Accept cold-start delay** (~30-60 seconds on first request after deploy). Use background loading with a readiness check. This is the recommended approach for v2.0 — simpler, no extra cost.
2. **Bake models into Docker image**: Increases image size by ~600MB but eliminates download delay. Add to Dockerfile: `RUN python -c "from transformers import pipeline; pipeline('sentiment-analysis', model='cardiffnlp/twitter-roberta-base-sentiment-latest')"`.
3. **Render Disk ($0.25/GB/month)**: Attach a 2GB disk, set `HF_HOME` to the disk path. Models persist across deploys.

For v2.0, option 1 (accept cold start) is recommended — lowest complexity, sufficient for a background pipeline that doesn't serve real-time requests.

### Load Models at Startup, Not Per-Request

```python
# In main.py lifespan event:
from contextlib import asynccontextmanager
from transformers import pipeline
from sentence_transformers import SentenceTransformer

sentiment_model = None
embedding_model = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global sentiment_model, embedding_model
    sentiment_model = pipeline(
        "sentiment-analysis",
        model="cardiffnlp/twitter-roberta-base-sentiment-latest",
        device=-1  # CPU
    )
    embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    yield
    # cleanup if needed
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| asyncpraw 7.8.1 | praw 7.8.1 (sync) | Never in this async-first project |
| sentence-transformers 5.2.3 | openai embeddings API | If no local inference needed; costs ~$0.02/1M tokens but adds latency/dependency |
| datasketch MinHash | SHA-256 hash only | Exact-duplicate-only scenario; MinHash is required for cross-platform near-duplicate detection |
| openai client + base_url | groq official SDK | Only if Groq adds features outside OpenAI spec |
| CPU-only torch | GPU Render instance | Only if processing exceeds ~100k posts/day; GPU instances start at $500+/month |
| transformers pipeline | onnxruntime ONNX export | If inference speed becomes bottleneck; ONNX can be 2-3x faster on CPU but adds export complexity |

---

## Sources (v2.0 Research)

- [asyncpraw PyPI](https://pypi.org/project/asyncpraw/) — version 7.8.1, Python 3.9+, async-native (HIGH confidence, verified Feb 2026)
- [asyncpraw GitHub](https://github.com/praw-dev/asyncpraw) — asyncprawcore 3.0.2 transport, maintained by praw-dev team (HIGH confidence)
- [sentence-transformers PyPI](https://pypi.org/project/sentence-transformers/) — version 5.2.3 released Feb 17 2026, Python >=3.10 (HIGH confidence)
- [HuggingFace sentence-transformers GitHub](https://github.com/huggingface/sentence-transformers) — now under HuggingFace org, actively maintained (HIGH confidence)
- [transformers PyPI](https://pypi.org/project/transformers/) — version 4.57.3 stable, v5.x RC is opt-in (HIGH confidence)
- [cardiffnlp/twitter-roberta-base-sentiment-latest HuggingFace](https://huggingface.co/cardiffnlp/twitter-roberta-base-sentiment-latest) — model confirmed active, pipeline API usage documented (HIGH confidence)
- [datasketch PyPI](https://pypi.org/project/datasketch/) — version 1.9.0, Python>=3.9, NumPy required (HIGH confidence)
- [openai PyPI](https://pypi.org/project/openai/) — version 2.21.0 released Feb 14 2026, Python>=3.9 (HIGH confidence)
- [Groq OpenAI-compatible API](https://console.groq.com/docs/overview) — base_url confirmed, free tier available (HIGH confidence)
- [DeepInfra OpenAI-compatible API](https://deepinfra.com/docs/openai_api) — base_url confirmed (HIGH confidence)
- [httpx PyPI](https://pypi.org/project/httpx/) — version 0.28.1 latest stable (HIGH confidence)
- [Render community RAM specs](https://community.render.com/t/clarification-on-free-tier-instance-ram-allocation/26734) — 512MB free/starter, Standard 2GB at $25/month (MEDIUM confidence — verify at render.com/pricing before upgrading)
- [PyTorch CPU-only install](https://github.com/pytorch/pytorch/issues/146786) — `--index-url https://download.pytorch.org/whl/cpu` required to avoid CUDA bloat (HIGH confidence)

---
*Stack research for: VibeCheck v2.0 — free data source ingestion and two-tier sentiment pipeline*
*Researched: 2026-02-19*
