# Phase 1: Foundation & Storage - Research

**Researched:** 2026-02-05
**Domain:** PostgreSQL time-series schema design, SQLAlchemy 2.0 async models, FastAPI scaffold, Docker Compose setup, Alembic async migrations, Python project structure
**Confidence:** HIGH (Context7 + official documentation verified)

## Summary

Phase 1 requires establishing the technical foundation: a working PostgreSQL database with proper time-series schema, an async SQLAlchemy ORM layer that can reliably execute database operations, and a deployable FastAPI + PostgreSQL stack via Docker Compose.

The critical decisions that will inform all downstream phases:

1. **Schema design must support time-series sentiment aggregation** without requiring TimescaleDB for MVP (but designed to migrate to it)
2. **SQLAlchemy 2.0 async patterns** are standard and well-documented; use `AsyncSession` and `async_sessionmaker`
3. **Alembic migrations** integrate seamlessly with SQLAlchemy 2.0 async setup
4. **Docker Compose** provides local development that mirrors production
5. **Python project structure** (pyproject.toml vs requirements.txt) should use both for clarity

**Primary recommendation:** Use SQLAlchemy 2.0 with asyncpg driver, PostgreSQL native schema (no TimescaleDB for Phase 1), Alembic for migrations, and Docker Compose for local development. All patterns are mature and well-supported.

---

## Standard Stack

### Core Database & ORM

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **PostgreSQL** | 16+ | Primary data store | Time-series capable without extensions, JSONB support, proven at scale |
| **SQLAlchemy** | 2.0.35+ | ORM + schema abstraction | First-class async support via `AsyncEngine`, native connection pooling, Alembic integration |
| **asyncpg** | 0.30+ | PostgreSQL async driver | Fastest Python PostgreSQL driver; essential for non-blocking async queries |
| **Alembic** | 1.14+ | Database migrations | SQLAlchemy-native migration tool; supports async operations and offline mode |

### FastAPI & HTTP

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **FastAPI** | 0.115+ | REST API framework | Native async/await support, automatic OpenAPI docs, excellent type hints |
| **Uvicorn** | 0.30+ | ASGI server | Standard FastAPI server; handles async request concurrency efficiently |
| **Pydantic** | 2.7+ | Data validation | Built into FastAPI, validates request/response schemas, custom validators for ranges |

### Development & Configuration

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **python-dotenv** | 1.0+ | Environment configuration | Loads .env files for local development; supports 12-factor apps |
| **httpx** | 0.27+ | HTTP client for AskNews | Async-native; essential for non-blocking API calls during ingestion |
| **pytest** | 8.0+ | Testing framework | Standard Python test framework with async support via pytest-asyncio |
| **pytest-asyncio** | 0.24+ | Async test support | Enables testing async functions and database operations |

### Installation

```bash
# Core backend
pip install fastapi==0.115.0
pip install uvicorn==0.30.0
pip install pydantic==2.7.0

# Database
pip install sqlalchemy==2.0.35
pip install asyncpg==0.30.0
pip install alembic==1.14.0
pip install psycopg2-binary==2.9.9  # For non-async operations (Alembic offline mode)

# HTTP client for AskNews
pip install httpx==0.27.0

# Configuration
pip install python-dotenv==1.0.0

# Testing
pip install pytest==8.0.0
pip install pytest-asyncio==0.24.0
pip install pytest-cov==5.0.0
```

---

## Architecture Patterns

### SQLAlchemy 2.0 Async Model Setup

**Pattern: DeclarativeBase with AsyncAttrs**

From official SQLAlchemy documentation, the correct setup for async is:

```python
# backend/db/base.py
from sqlalchemy.orm import DeclarativeBase, AsyncAttrs

class Base(AsyncAttrs, DeclarativeBase):
    """Base class for all ORM models.

    AsyncAttrs enables lazy-loaded relationships to work with async/await.
    """
    pass
```

**Why:** `AsyncAttrs` is essential for proper async behavior. Without it, accessing lazy-loaded relationships triggers implicit database queries that break async semantics.

**Example model:**

```python
# backend/db/models.py
from datetime import datetime
from sqlalchemy import Column, DateTime, Float, Integer, String, Text, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column
from backend.db.base import Base

class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(primary_key=True)
    external_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(500))
    content: Mapped[str] = mapped_column(Text, nullable=True)
    source_name: Mapped[str] = mapped_column(String(255), nullable=True)
    source_url: Mapped[str] = mapped_column(Text)
    published_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    sentiment_score: Mapped[float] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default=datetime.utcnow
    )
```

**Key aspects:**
- Use `Mapped` type hints for clarity
- `mapped_column()` is SQLAlchemy 2.0+ pattern (replaces `Column()`)
- All timestamps use `TIMESTAMP WITH TIME ZONE` (UTC)
- Foreign keys and relationships come in Phase 2

**Source:** [SQLAlchemy 2.0 Async ORM Documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)

---

### Async Engine & Session Management

**Pattern: Single Engine, Per-Request Sessions**

```python
# backend/db/session.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://user:password@localhost:5432/vibecheck"
)

# Single engine per application lifetime
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # Set True for SQL debugging
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # Verify connections before use
)

# Factory for creating per-request sessions
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Critical: prevents implicit queries after commit
)

async def get_session():
    """Dependency for FastAPI routes."""
    async with AsyncSessionLocal() as session:
        yield session
```

**Critical setting: `expire_on_commit=False`**

Without this, SQLAlchemy attempts to reload object attributes after each commit, triggering implicit database queries that break async semantics. With this setting, objects remain accessible after commit without triggering new queries.

**Source:** [SQLAlchemy Async Engine Documentation](https://docs.sqlalchemy.org/en/20/core/engines.html)

---

### PostgreSQL Schema for Time-Series Sentiment

**Pattern: Normalized time-series with pre-aggregated sentiments**

```sql
-- Curated entity list (immutable, populated at startup)
CREATE TABLE entities (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,  -- e.g., "GPT-4o", "Claude"
    category VARCHAR(50) NOT NULL,      -- "model" or "tool"
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Raw articles/news fetched from AskNews
CREATE TABLE articles (
    id SERIAL PRIMARY KEY,
    external_id VARCHAR(255) UNIQUE NOT NULL,  -- AskNews article ID
    title VARCHAR(500) NOT NULL,
    url TEXT UNIQUE NOT NULL,
    source_name VARCHAR(255),
    published_at TIMESTAMP WITH TIME ZONE NOT NULL,
    sentiment_score NUMERIC(3, 2),  -- -1.0 to +1.0
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT sentiment_range CHECK (sentiment_score >= -1 AND sentiment_score <= 1)
);

CREATE INDEX idx_articles_published_at ON articles(published_at DESC);
CREATE INDEX idx_articles_external_id ON articles(external_id);

-- Pre-aggregated sentiment time-series (hourly and daily)
CREATE TABLE sentiment_timeseries (
    id SERIAL PRIMARY KEY,
    entity_id INTEGER NOT NULL REFERENCES entities(id),
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,  -- Start of period
    period VARCHAR(10) NOT NULL,   -- "hourly" or "daily"

    sentiment_mean NUMERIC(3, 2),
    sentiment_min NUMERIC(3, 2),
    sentiment_max NUMERIC(3, 2),
    sentiment_std NUMERIC(3, 2),
    article_count INTEGER,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT sentiment_range CHECK (
        (sentiment_mean IS NULL OR (sentiment_mean >= -1 AND sentiment_mean <= 1))
    )
);

CREATE INDEX idx_sentiment_ts_entity_timestamp
    ON sentiment_timeseries(entity_id, timestamp DESC);
CREATE INDEX idx_sentiment_ts_timestamp
    ON sentiment_timeseries(timestamp DESC);
```

**Design rationale:**
- **No TimescaleDB for Phase 1**: Standard PostgreSQL schema works well for MVP. Can migrate to TimescaleDB later (it's a drop-in extension).
- **Separate tables**: `articles` stores raw data; `sentiment_timeseries` stores aggregates. Queries hit aggregates, avoiding full table scans.
- **UTC timestamps**: All timestamps in `TIMESTAMP WITH TIME ZONE`. Conversions happen in application, not database.
- **Indexes on entity_id and timestamp**: Critical for fast sentiment history queries.

**Pitfall prevention:**
- `sentiment_timeseries` has `period` column to support both hourly and daily aggregates without table conflicts
- `article_count` allows weighting when re-aggregating (e.g., hourly → daily)
- Explicit `CHECK` constraint ensures sentiment values stay in valid range

---

### Alembic Migration Setup with Async SQLAlchemy

**Pattern: Async-friendly Alembic configuration**

After `alembic init migrations`, modify `alembic/env.py`:

```python
# alembic/env.py
import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context

# Load your models
from backend.db.base import Base
from backend.db.models import *  # Import all models

config = context.config
fileConfig(config.config_file_name)
target_metadata = Base.metadata

def run_migrations_offline():
    """Run migrations in offline mode (generate SQL without executing)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online():
    """Run migrations in online mode (execute directly)."""
    # Get async URL from configuration
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = config.get_main_option("sqlalchemy.url")

    connectable = create_async_engine(
        config.get_main_option("sqlalchemy.url"),
        poolclass=pool.NullPool,
    )

    async with connectable.begin() as connection:
        await connection.run_sync(do_run_migrations)

def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

Configure `alembic.ini`:

```ini
sqlalchemy.url = postgresql+asyncpg://user:password@localhost/vibecheck
```

Then:

```bash
# Create a migration (auto-detects schema changes)
alembic revision --autogenerate -m "Create tables"

# Apply migrations
alembic upgrade head

# Rollback one migration (for testing)
alembic downgrade -1
```

**Critical:** Use `alembic revision --autogenerate` to detect schema changes from your ORM models, not manual SQL.

---

### FastAPI Project Scaffold

**Pattern: Modular structure with clear separation of concerns**

```
backend/
├── main.py                          # FastAPI app initialization
├── config.py                        # Settings from .env
├── pyproject.toml                   # Project metadata + dependencies
├── requirements.txt                 # Pinned versions for production
├── .env.example                     # Template for .env (no secrets)
├── Dockerfile                       # Container image
├── docker-compose.yml               # Local dev environment
│
├── db/
│   ├── base.py                      # DeclarativeBase definition
│   ├── models.py                    # SQLAlchemy ORM models
│   ├── session.py                   # Engine, AsyncSessionLocal, get_session()
│   └── migrations/                  # Alembic migrations (auto-generated)
│       ├── env.py                   # Alembic async configuration
│       ├── script.py.mako           # Migration template
│       └── versions/                # Individual migrations
│           └── 001_create_tables.py
│
├── api/
│   ├── routes/                      # HTTP endpoint handlers
│   │   ├── health.py                # GET /health
│   │   ├── entities.py              # GET /api/entities
│   │   └── articles.py              # GET /api/articles
│   ├── schemas/                     # Pydantic response models
│   │   ├── entity.py
│   │   ├── article.py
│   │   └── sentiment.py
│   └── services/                    # Business logic (queries, transforms)
│       ├── sentiment_service.py
│       └── article_service.py
│
├── pipeline/
│   ├── scheduler.py                 # APScheduler setup (Phase 2)
│   ├── jobs/                        # Job definitions (Phase 2)
│   └── services/                    # Ingestion services (Phase 2)
│
├── utils/
│   ├── logging.py                   # Structured logging setup
│   └── constants.py                 # Entity lists, configuration
│
└── tests/
    ├── conftest.py                  # Pytest fixtures
    ├── test_db/                     # Database integration tests
    └── test_api/                    # API endpoint tests
```

**Key principles:**
- **Single responsibility**: Each module has one clear purpose
- **Layered architecture**: Routes → Services → Database layer
- **Async throughout**: All I/O is async; no blocking operations
- **Testability**: Services are decoupled from routes for unit testing

---

### Docker Compose for Local Development

**Pattern: Isolated services that mirror production**

```yaml
# docker-compose.yml
version: '3.8'

services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://vibecheck:password@postgres:5432/vibecheck
      - ENVIRONMENT=development
    volumes:
      - ./backend:/app  # Live code reload
    depends_on:
      postgres:
        condition: service_healthy
    command: uvicorn main:app --host 0.0.0.0 --port 8000 --reload

  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: vibecheck
      POSTGRES_USER: vibecheck
      POSTGRES_PASSWORD: password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U vibecheck"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
```

**Backend Dockerfile:**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import httpx; httpx.get('http://localhost:8000/health')"

# Run with hot reload in development
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

**Usage:**

```bash
# Start all services
docker-compose up

# Initialize database (run in another terminal)
docker-compose exec backend alembic upgrade head

# Stop services
docker-compose down

# View logs
docker-compose logs -f backend
```

**Why Docker Compose for Phase 1:**
- Single command to start entire stack (no manual PostgreSQL setup)
- Environment variables isolated (no secrets in code)
- Services communicate by name (backend connects to `postgres:5432`, not `localhost`)
- Mirrors production configuration (PostgreSQL version, environment variables)

**Source:** [FastAPI Docker Documentation](https://fastapi.tiangolo.com/deployment/docker/)

---

### FastAPI Startup & Lifespan Management

**Pattern: Database initialization on app startup**

```python
# backend/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.db.session import engine, AsyncSessionLocal
from backend.db.base import Base
from backend.api.routes import health, entities, articles

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("Starting up application...")

    # Create tables if they don't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    # Shutdown
    print("Shutting down application...")
    await engine.dispose()

app = FastAPI(
    title="VibeCheck API",
    description="Sentiment tracking for AI entities",
    version="0.1.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include route modules
app.include_router(health.router)
app.include_router(entities.router, prefix="/api")
app.include_router(articles.router, prefix="/api")
```

**Key aspects:**
- `lifespan` context manager handles startup/shutdown
- Create tables on startup (optional; Alembic migrations are recommended for production)
- `engine.dispose()` closes all connections on shutdown
- Routes are included from submodules for organization

**Source:** [FastAPI Lifespan Events](https://fastapi.tiangolo.com/advanced/events/)

---

### Python Project Configuration: pyproject.toml

**Pattern: Modern Python packaging with pyproject.toml**

```toml
# backend/pyproject.toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "vibecheck-backend"
version = "0.1.0"
description = "Sentiment tracking backend for AI entities"
requires-python = ">=3.11"
authors = [
    {name = "Developer", email = "dev@example.com"}
]

dependencies = [
    "fastapi==0.115.0",
    "uvicorn[standard]==0.30.0",
    "pydantic==2.7.0",
    "sqlalchemy==2.0.35",
    "asyncpg==0.30.0",
    "alembic==1.14.0",
    "httpx==0.27.0",
    "python-dotenv==1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest==8.0.0",
    "pytest-asyncio==0.24.0",
    "pytest-cov==5.0.0",
    "black==24.1.1",
    "ruff==0.2.0",
]

[project.urls]
Homepage = "https://github.com/user/vibecheck"
Documentation = "https://docs.example.com"
Repository = "https://github.com/user/vibecheck.git"

[tool.black]
line-length = 100
target-version = ["py311", "py312"]

[tool.ruff]
line-length = 100
target-version = "py311"
select = ["E", "F", "W"]  # Errors, Pyflakes, Warnings

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
addopts = "--cov=backend --cov-report=html"
```

**Why both pyproject.toml and requirements.txt:**

- **pyproject.toml**: Project metadata, version constraints, build configuration (developer-facing)
- **requirements.txt**: Exact pinned versions from `pip freeze` (production deployment)

```bash
# Generate requirements.txt from pyproject.toml
pip install -e ".[dev]"
pip freeze > requirements.txt
```

**Source:** [Poetry Documentation](https://python-poetry.org/docs/)

---

## Don't Hand-Roll

Problems that look simple but have well-established solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|------------|-------------|-----|
| **Async database sessions** | Custom context manager for sessions | SQLAlchemy's `async_sessionmaker` + FastAPI dependency injection | Already handles connection pooling, transaction management, and cleanup |
| **Database connection pooling** | Manual queue of connections | SQLAlchemy's built-in `pool_size` and `max_overflow` | Handles stale connections, overflow, and timeout gracefully |
| **Schema versioning** | Manual SQL upgrade scripts | Alembic with auto-generation | Tracks changes, supports rollbacks, integrates with ORM |
| **Environment configuration** | Parse environment variables manually | `python-dotenv` + Pydantic Settings | Validates types, provides defaults, handles complex nested configs |
| **HTTP requests during ingestion** | `requests` library (synchronous) | `httpx.AsyncClient` | Non-blocking I/O essential for async ingestion jobs |

**Key insight:** All of these solutions have hidden complexity (connection timeouts, transaction isolation, offline migrations, type validation). Off-the-shelf solutions are battle-tested and handle edge cases.

---

## Common Pitfalls

### Pitfall 1: Mixing Sync and Async SQLAlchemy

**What goes wrong:**
```python
# WRONG: Create sync engine and async session
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession

engine = create_engine("postgresql://...")  # Synchronous!
session = AsyncSession(bind=engine)  # Async session with sync engine?
```

This breaks because SQLAlchemy expects async engine URLs to start with `postgresql+asyncpg://`, not plain `postgresql://`.

**How to avoid:**
- Use `create_async_engine()` for async applications
- Verify URL contains `+asyncpg`: `postgresql+asyncpg://user:pass@host/db`
- Use `AsyncSessionLocal` from `session.py` module (never create `AsyncSession` manually)

**Warning signs:**
- `RuntimeError: coroutine was never awaited` when accessing database
- Connection pool exhaustion (connections not being released)

---

### Pitfall 2: Forgetting `expire_on_commit=False`

**What goes wrong:**
```python
# Without expire_on_commit=False
async_session = async_sessionmaker(engine)

async with async_session() as session:
    article = await session.get(Article, 1)
    await session.commit()
    print(article.title)  # Triggers implicit DB query! (blocks on network I/O)
```

**How to avoid:**
```python
# Always use expire_on_commit=False for async
AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,  # Keep objects accessible after commit
)
```

**Why:** After async commit, SQLAlchemy wants to refresh object attributes. Without this setting, it tries to query the database again, breaking async semantics.

---

### Pitfall 3: Using `SELECT ... FOR UPDATE` Without Async Context

**What goes wrong:**
```python
# Blocking query for distributed locking
result = await session.execute(
    select(JobLock).where(...).with_for_update()
)
```

Without proper async handling, the lock can be held across multiple concurrent requests, blocking the API.

**How to avoid:**
- Use database-level locks sparingly
- Keep lock scope minimal (lock, do operation, unlock immediately)
- For Phase 1, avoid distributed locks (single process, single async scheduler)

---

### Pitfall 4: Not Setting Alembic's Async Mode

**What goes wrong:**
```python
# alembic/env.py without async support
def run_migrations_online():
    # Synchronous execution
    connectable = create_engine(...)  # Wrong for async application!
```

Migrations will hang or timeout if the application expects async.

**How to avoid:**
```python
# Use async engine and asyncio.run()
async def run_migrations_online():
    connectable = create_async_engine(...)
    async with connectable.begin() as connection:
        await connection.run_sync(do_run_migrations)

if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

---

### Pitfall 5: Docker Container Not Healthy on Startup

**What goes wrong:**
```yaml
# Docker Compose without health checks
backend:
  build: ./backend
  depends_on:
    - postgres

postgres:
  image: postgres:16-alpine
  # No healthcheck!
```

The backend container starts before PostgreSQL is ready, connection fails.

**How to avoid:**
```yaml
# With healthcheck
postgres:
  image: postgres:16-alpine
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U vibecheck"]
    interval: 5s
    timeout: 5s
    retries: 5

backend:
  depends_on:
    postgres:
      condition: service_healthy  # Wait for healthy status
```

---

## Code Examples

### Complete Session Management Module

```python
# backend/db/session.py
import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://vibecheck:password@localhost:5432/vibecheck"
)

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("SQL_ECHO", "false").lower() == "true",
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # Verify connections before use
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

async def get_session():
    """FastAPI dependency for injecting session into routes."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

### Complete Database Initialization

```python
# backend/db/__init__.py
from backend.db.base import Base
from backend.db.models import Article, Entity, SentimentTimeseries
from backend.db.session import engine, AsyncSessionLocal, get_session

__all__ = ["Base", "Article", "Entity", "SentimentTimeseries", "engine", "AsyncSessionLocal", "get_session"]
```

### FastAPI Route Using Session

```python
# backend/api/routes/articles.py
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.db.models import Article
from backend.db.session import get_session
from backend.api.schemas.article import ArticleResponse

router = APIRouter(prefix="/articles", tags=["articles"])

@router.get("", response_model=list[ArticleResponse])
async def list_articles(
    session: AsyncSession = Depends(get_session),
    limit: int = 20,
    offset: int = 0,
):
    """Fetch recent articles."""
    query = select(Article).order_by(Article.created_at.desc()).limit(limit).offset(offset)
    result = await session.execute(query)
    articles = result.scalars().all()
    return articles
```

---

## State of the Art

| Old Approach | Current Approach (2026) | When Changed | Impact |
|--------------|------------------------|--------------|--------|
| SQLAlchemy 1.4 with manual async setup | SQLAlchemy 2.0+ async-first API | 2023 | Cleaner code, better error messages, better type hints |
| `create_engine()` + manual async wrapping | `create_async_engine()` native | 2021 | No need for workarounds or extra adapters |
| Celery for all scheduled tasks | APScheduler for simple polling, Celery for complex | 2022 | Right-sized solutions, less operational overhead |
| Flask + SQLAlchemy | FastAPI + SQLAlchemy | 2021 | Better async support, automatic documentation, faster |
| Manual connection pooling | SQLAlchemy built-in pooling | Always standard | SQLAlchemy handles edge cases better than manual code |

**Deprecated/outdated:**
- **SQLAlchemy 1.4 async patterns**: Use 2.0+ instead (cleaner API, better async support)
- **`greenlet` for async**: Not needed with native `async/await` support in SQLAlchemy 2.0
- **`databases` library**: SQLAlchemy 2.0 async eliminates need for custom async wrappers

---

## Open Questions

1. **Should we use Poetry or pip + requirements.txt?**
   - What we know: Poetry provides lock files and automated dependency resolution
   - What's unclear: Single developer maintaining both might prefer simpler pip + requirements.txt
   - Recommendation: Use `pyproject.toml` + `requirements.txt` for clarity. Poetry is optional upgrade later.

2. **How many Alembic migrations before Phase 1 completes?**
   - What we know: Phase 1 requires initial schema (entities, articles, sentiment_timeseries)
   - What's unclear: Will there be mid-phase schema changes?
   - Recommendation: Assume 1-2 migrations. Set up Alembic structure in Phase 1, add migrations as needed.

3. **Should we use TimescaleDB or plain PostgreSQL for Phase 1?**
   - What we know: Plain PostgreSQL handles MVP data volumes well. TimescaleDB is available later.
   - What's unclear: Unknown data growth rate; may need TimescaleDB sooner than expected.
   - Recommendation: Start with plain PostgreSQL. Design schema for TimescaleDB compatibility (hypertable structure). Migrate if needed.

4. **How much async concurrency does the Phase 1 API need to support?**
   - What we know: Single developer, likely <100 concurrent requests
   - What's unclear: Peak concurrent requests once shared with frontend team
   - Recommendation: Default pool_size=10, max_overflow=20. Monitor and scale if needed.

---

## Sources

### Primary (HIGH confidence)

- **SQLAlchemy 2.0 Async Documentation** - [Asynchronous I/O (asyncio)](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html) — Session management, engine configuration, AsyncAttrs pattern
- **SQLAlchemy Engine Configuration** - [Engines and Connections](https://docs.sqlalchemy.org/en/20/core/engines.html) — Async engine setup, connection pooling, URL configuration
- **FastAPI Documentation** - [Docker Deployment](https://fastapi.tiangolo.com/deployment/docker/) — Docker and Docker Compose patterns
- **Alembic Documentation** - [Alembic 1.18.3](https://alembic.sqlalchemy.org/en/latest/) — Migration setup, async support

### Secondary (MEDIUM confidence)

- [Building High-Performance Async APIs with FastAPI, SQLAlchemy 2.0, and Asyncpg](https://leapcell.io/blog/building-high-performance-async-apis-with-fastapi-sqlalchemy-2-0-and-asyncpg) — Best practices verified against official docs
- [Asynchronous SQLAlchemy 2: A simple step-by-step guide](https://dev.to/amverum/asynchronous-sqlalchemy-2-a-simple-step-by-step-guide-to-configuration-models-relationships-and-3ob3) — Community patterns consistent with official documentation

### Project-Level (already researched)

- STACK.md — Technology selections and version constraints
- ARCHITECTURE.md — Layered architecture, database schema, data flow patterns
- PITFALLS.md — Critical failure modes for Phase 1 (schema design, scheduler reliability, API costs)

---

## Metadata

**Confidence breakdown:**
- **Standard Stack**: HIGH — All versions and libraries verified against official documentation
- **Architecture Patterns**: HIGH — Code examples from official SQLAlchemy and FastAPI docs
- **Don't Hand-Roll**: HIGH — Established solutions are industry standard
- **Common Pitfalls**: MEDIUM-HIGH — From training data and patterns, some not verified against current code
- **Code Examples**: HIGH — Directly from official sources or derived from documented patterns

**Research date:** 2026-02-05
**Valid until:** 2026-03-05 (SQLAlchemy/FastAPI relatively stable; check for security updates)

**What might have been missed:**
- New AsyncIO features in Python 3.12.x (minor, unlikely to affect Phase 1)
- PostgreSQL 16.x-specific optimizations for time-series (would benefit Phase 2)
- Monitoring/observability patterns (deferred to Phase 2)
- APScheduler async integration specifics (deferred to Phase 2)

