# Phase 5: Infrastructure - Research

**Researched:** 2026-02-19
**Domain:** Database schema migration (TimescaleDB + pgvector), AskNews removal, hosting platform evaluation
**Confidence:** HIGH (schema/migration patterns), MEDIUM (hosting recommendations)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **Full data wipe**: Drop ALL existing data (articles, sentiment_timeseries, entities) — fresh start
- **No backup needed** — data is not valuable enough to preserve
- **Alembic migrations can be destructive** — no need for additive-only strategy
- **Leave Render entirely** — no Render dependency going forward
- **Phase 5 is codebase-only** — schema, dependencies, code cleanup. Actual deployment is out of scope
- **TimescaleDB** for time-series partitioning and continuous aggregates
- **pgvector** for embedding storage and semantic search (VECTOR(384) from all-MiniLM-L6-v2)
- **Many-to-many entity-post relationships** via `post_entity_mentions` table
- **No author/PII storage** — posts are anonymous
- **Aspect scores as numeric float (-1.0 to 1.0)**, no evidence text stored
- **LLM Tier 2** for aspect extraction (not DeBERTa)
- **Content hash (SHA-256)** for deduplication

### Claude's Discretion

- Post content storage depth (title+snippet vs. full body)
- Engagement metric design (raw vs. normalized vs. both)
- Aspect list refinement (7 initial aspects are a starting point)
- Aspect storage mechanism (enum vs. reference table)
- Schema details that align with external research doc recommendations

### Deferred Ideas (OUT OF SCOPE)

- PII masking during post ingestion — belongs in Phase 6
- Actual deployment to new hosting platform — separate effort
- Entity re-seeding — later phase
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INFRA-01 | System migrates to new schema (posts, tool_mentions, aspect_sentiments) via Alembic without breaking existing data | Destructive migration pattern: drop old tables, create new ones. TimescaleDB hypertable creation via `op.execute()`. pgvector extension registration in env.py. |
| INFRA-02 | AskNews SDK removed and httpx upgraded to 0.28.1 | Full audit of 14 files with AskNews imports. Replace `asknews`, `structlog`, `tenacity` removals assessed. httpx 0.28.x is latest stable. |
| INFRA-03 | Render deployment upgraded to Standard tier ($25/mo) for ML model support | Overridden by CONTEXT.md — user decided to leave Render. Phase 5 preps codebase for new platform; actual deployment is out of scope. Research covers platform options. |
</phase_requirements>

---

## Summary

Phase 5 is a clean-slate infrastructure reset for VibeCheck. The three work streams are: (1) replace the database schema to support the new multi-source sentiment pipeline, (2) strip all AskNews dependencies from the codebase, and (3) update Docker Compose to use TimescaleDB+pgvector and document hosting platform options.

The schema redesign is the most technically complex part. The current database has `entities`, `articles`, `sentiment_timeseries`, and `scheduler_execution_log` tables. All except `scheduler_execution_log` and `entities` will be dropped and replaced with `posts` (TimescaleDB hypertable), `post_entity_mentions` (many-to-many junction), and `aspect_sentiments`. The new `posts` table requires two PostgreSQL extensions — TimescaleDB (hypertable) and pgvector (VECTOR(384) embedding column). Both extensions must be created via `op.execute()` in Alembic before the table definitions.

The AskNews removal touches 14 files. The core client (`asknews_client.py`) and both jobs (`news_job.py`, `stories_job.py`) need wholesale replacement or deletion. Supporting packages `asknews`, `tenacity`, and `structlog` can be removed from `requirements.txt`; `httpx` gets upgraded from 0.25.2 to 0.28.1. The key constraint: `httpx` was pinned to 0.25.2 specifically to satisfy `asknews`'s `<0.26.0` requirement — once `asknews` is gone, the pin is removable.

**Primary recommendation:** Use a single Alembic migration that drops old tables, creates extensions, and creates new tables. Use `timescale/timescaledb-ha:pg16-latest` as the Docker Compose postgres image (includes both TimescaleDB and pgvector). For hosting research, Oracle Cloud Free Tier is the only true $0/month option; Fly.io is the best developer experience at ~$10-15/month for app + self-managed Postgres.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| alembic | 1.14.0 (current) | Database migrations | Already in project. Latest is 1.18.4 but upgrade not needed this phase. |
| sqlalchemy | 2.0.35 (current) | ORM + async engine | Already in project. |
| pgvector | 0.3.x | Python pgvector type for SQLAlchemy | Official pgvector Python client; supports asyncpg + SQLAlchemy mapped_column |
| asyncpg | 0.30.0 (current) | Async PostgreSQL driver | Already in project. Works with pgvector. |
| httpx | 0.28.1 | HTTP client for future data sources | Drop-in replacement; removing asknews pin unlocks upgrade |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| timescaledb-ha Docker image | pg16-latest | PostgreSQL + TimescaleDB + pgvector in one image | Docker Compose postgres service replacement |
| python-dotenv | 1.0.0 (current) | Environment variable management | Already in project, keep |
| apscheduler | 3.10.4 (current) | Job scheduling | Keep — still needed for future pipeline jobs |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `timescale/timescaledb-ha:pg16-latest` | Build custom Dockerfile from `postgres:16` + compile TimescaleDB + pgvector | Custom build is more complex, HA image gives both extensions pre-installed |
| Destructive Alembic migration | Multi-step additive migration | Additive is safer but user confirmed fresh start is acceptable |
| `VECTOR(384)` | No embedding column initially | Research doc recommends 384 dims (all-MiniLM-L6-v2 dimensions); include from start per user decision |

**Installation:**
```bash
pip install pgvector==0.3.6
```

---

## Architecture Patterns

### Recommended Project Structure (changes only)

```
backend/
├── db/
│   └── models.py              # Replace: Entity (keep), new Post, PostEntityMention, AspectSentiment
├── alembic/versions/
│   └── 006_reset_schema.py    # New: single destructive migration
├── pipeline/
│   └── clients/
│       └── asknews_client.py  # DELETE entirely
│   └── jobs/
│       ├── news_job.py        # DELETE or empty stub
│       └── stories_job.py     # DELETE or empty stub
├── requirements.txt           # Remove asknews, tenacity, structlog; upgrade httpx
└── docker-compose.yml         # Change postgres image to timescaledb-ha
```

### Pattern 1: Destructive Alembic Migration

**What:** A single migration that drops all old tables, creates extensions, creates new tables, and converts `posts` to a TimescaleDB hypertable.

**When to use:** When doing a fresh-start schema reset with no data preservation requirement.

**Example:**
```python
# Source: Alembic docs + pgvector discussions/1324 + alembic/discussions/1465
def upgrade() -> None:
    # === 1. Drop old tables (order matters for FK constraints) ===
    op.drop_table('sentiment_timeseries', if_exists=True)
    op.drop_table('articles', if_exists=True)
    op.drop_table('entities', if_exists=True)

    # === 2. Create required extensions ===
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # === 3. Create entities table (kept, will be re-seeded later) ===
    op.create_table(
        'entities',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(255), unique=True, nullable=False),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )

    # === 4. Create posts table ===
    op.create_table(
        'posts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source', sa.String(50), nullable=False),        # 'hackernews', 'reddit', etc.
        sa.Column('external_id', sa.String(255), nullable=False),   # platform's ID
        sa.Column('url', sa.Text(), nullable=True),
        sa.Column('title', sa.String(500), nullable=True),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('content_hash', sa.String(64), nullable=False, unique=True),  # SHA-256
        sa.Column('metadata', sa.JSON(), nullable=True),            # JSONB for flexible fields
        sa.Column('embedding', Vector(384), nullable=True),         # pgvector column
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column('published_at', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source', 'external_id', name='uq_posts_source_external_id'),
    )

    # === 5. Convert posts to TimescaleDB hypertable (partition by published_at) ===
    op.execute(
        "SELECT create_hypertable('posts', 'published_at', if_not_exists => TRUE)"
    )

    # === 6. Create post_entity_mentions (many-to-many) ===
    op.create_table(
        'post_entity_mentions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('post_id', sa.Integer(), sa.ForeignKey('posts.id'), nullable=False),
        sa.Column('entity_id', sa.Integer(), sa.ForeignKey('entities.id'), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.UniqueConstraint('post_id', 'entity_id', name='uq_post_entity_mentions'),
    )

    # === 7. Create aspect_sentiments ===
    op.create_table(
        'aspect_sentiments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('post_id', sa.Integer(), sa.ForeignKey('posts.id'), nullable=False),
        sa.Column('entity_id', sa.Integer(), sa.ForeignKey('entities.id'), nullable=False),
        sa.Column('aspect', sa.String(50), nullable=False),         # 'performance', 'cost', etc.
        sa.Column('score', sa.Float(), nullable=False),             # -1.0 to 1.0
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.CheckConstraint('score >= -1.0 AND score <= 1.0', name='ck_aspect_sentiments_score'),
        sa.UniqueConstraint('post_id', 'entity_id', 'aspect', name='uq_aspect_sentiments'),
    )

    # === 8. Useful indexes ===
    op.create_index('ix_posts_published_at', 'posts', ['published_at'])
    op.create_index('ix_posts_content_hash', 'posts', ['content_hash'])
    op.create_index('ix_posts_source', 'posts', ['source'])
    op.create_index('ix_post_entity_mentions_entity_id', 'post_entity_mentions', ['entity_id'])
    op.create_index('ix_aspect_sentiments_post_id', 'aspect_sentiments', ['post_id'])
    op.create_index('ix_aspect_sentiments_entity_aspect', 'aspect_sentiments',
                    ['entity_id', 'aspect'])
```

### Pattern 2: pgvector Type Registration in Alembic env.py

**What:** Register pgvector's `Vector` type with asyncpg's dialect so `alembic check` doesn't detect false drift.

**When to use:** Any project using pgvector with Alembic autogenerate or `alembic check`.

**Example:**
```python
# Source: github.com/sqlalchemy/alembic/discussions/1324
# In backend/alembic/env.py, inside do_run_migrations():
import pgvector.sqlalchemy

def do_run_migrations(connection):
    # Register vector type to prevent alembic check from seeing false drift
    connection.dialect.ischema_names['vector'] = pgvector.sqlalchemy.Vector
    context.configure(
        connection=connection,
        target_metadata=target_metadata
    )
    with context.begin_transaction():
        context.run_migrations()
```

### Pattern 3: TimescaleDB Schema Filtering in env.py

**What:** Exclude TimescaleDB's internal schemas from Alembic autogenerate inspection.

**When to use:** Any project using TimescaleDB with `alembic revision --autogenerate`.

**Example:**
```python
# Source: github.com/sqlalchemy/alembic/discussions/1465
TIMESCALE_SCHEMAS = {
    '_timescaledb_cache',
    '_timescaledb_catalog',
    '_timescaledb_config',
    '_timescaledb_internal',
    'timescaledb_information',
}

def include_object(object, name, type_, reflected, compare_to):
    if type_ == "schema" and name in TIMESCALE_SCHEMAS:
        return False
    return True

# In context.configure():
context.configure(
    connection=connection,
    target_metadata=target_metadata,
    include_schemas=True,
    include_object=include_object,
)
```

### Pattern 4: ORM Model with pgvector

**What:** SQLAlchemy 2.0 mapped_column with Vector type for embedding storage.

**Example:**
```python
# Source: github.com/pgvector/pgvector-python
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import Mapped, mapped_column
import numpy as np

class Post(Base):
    __tablename__ = "posts"
    id: Mapped[int] = mapped_column(primary_key=True)
    embedding: Mapped[np.ndarray | None] = mapped_column(Vector(384), nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    # ... other columns
```

### Pattern 5: TimescaleDB Hypertable Auto-Index Exclusion

**What:** TimescaleDB auto-creates an index on the time partitioning column. Without filtering, Alembic `--autogenerate` will try to drop it every time.

**When to use:** When using TimescaleDB hypertables with Alembic.

**Example:**
```python
# Source: github.com/sqlalchemy/alembic/discussions/1465
def include_object(object, name, type_, reflected, compare_to):
    # Exclude TimescaleDB auto-created index on published_at
    if type_ == "index" and name == "posts_published_at_idx":
        return False
    # Exclude TimescaleDB internal schemas
    if type_ == "schema" and name.startswith("_timescaledb"):
        return False
    return True
```

### Anti-Patterns to Avoid

- **Running `CREATE EXTENSION` outside of Alembic:** If the extension doesn't exist when models are imported, SQLAlchemy will fail to load the `Vector` type definition. Always use `op.execute("CREATE EXTENSION IF NOT EXISTS vector")` in a migration that runs before any table using `Vector`.
- **Using `alembic revision --autogenerate` after converting to hypertable without `include_object` filtering:** TimescaleDB creates internal indexes and chunks; Alembic will detect them as drift and generate spurious DROP statements.
- **Pinning postgres image as `postgres:16` in Docker Compose:** The standard image doesn't have TimescaleDB or pgvector. Must use `timescale/timescaledb-ha:pg16-latest` or equivalent.
- **Importing `pgvector` types in models before extension exists in DB:** The migration must create the `vector` extension before running `alembic upgrade head`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Vector similarity search | Custom cosine distance in Python | pgvector `<=>` operator via SQLAlchemy | pgvector operates in-DB, handles index scans, no data transfer overhead |
| Hypertable partitioning | Manual date-partitioned tables | `create_hypertable()` via TimescaleDB | Automatic partition management, time_bucket() queries, continuous aggregates |
| Content deduplication | Custom hash logic | SHA-256 via Python's `hashlib` + `content_hash` column with unique constraint | DB-enforced deduplication at insert time |
| Extension creation in app startup | `CREATE EXTENSION IF NOT EXISTS` in FastAPI lifespan | Alembic migration step | Extensions are DB state, belong in migrations not app code |

**Key insight:** Both TimescaleDB and pgvector expose their complexity through SQL DDL statements, not Python APIs. The Alembic migration is the right place to set them up — not app startup code.

---

## Schema Design Decisions (Claude's Discretion)

Based on the research doc recommendations and the 7 initial aspects, here are the resolved design choices:

### Post Content Storage
**Recommendation: title + body (full text where available)**

Rationale: Sentiment analysis quality degrades significantly on title-only data. The research doc explicitly recommends storing `body` for aspect-level extraction. Storage cost is trivial at this scale (1,000–10,000 posts/day). Store `body` as `TEXT` (nullable, since some sources only provide titles/snippets).

### Engagement Metrics
**Recommendation: Store raw metrics in `metadata` JSONB column**

Rationale: Each source has different engagement metrics (HN: points/comments, Reddit: upvotes/score/ratio, GitHub: reactions/comments). A JSONB column handles this heterogeneity without schema churn. Do not normalize — normalization assumptions change as sources are added.

Example metadata structure:
```json
{"upvotes": 342, "num_comments": 47, "score": 0.89, "award_count": 2}
```

### Aspect List
**Recommendation: Use 7 aspects from research, store as VARCHAR(50) enum-like string**

The 7 aspects from the research doc: `performance`, `cost`, `reliability`, `ux`, `speed`, `code_quality`, `context_window`

These cover the categories the sources actually discuss. Store as `VARCHAR(50)` string (not a PostgreSQL ENUM type), because:
- ENUMs require a migration to add new values
- String column + application-level validation is more flexible
- An application-level constant set (e.g., `VALID_ASPECTS`) enforces the list without schema lock-in

### Aspect Storage Mechanism
**Recommendation: String column (no reference table)**

A reference table adds joins without meaningful benefit at this scale. A `CHECK` constraint or application-level validation provides sufficient safety. The `uq_aspect_sentiments` unique constraint on `(post_id, entity_id, aspect)` prevents duplicates.

---

## AskNews Removal Scope

### Files to Delete

| File | Action |
|------|--------|
| `backend/pipeline/clients/asknews_client.py` | Delete entirely |
| `backend/pipeline/jobs/news_job.py` | Delete entirely |
| `backend/pipeline/jobs/stories_job.py` | Delete entirely |

### Files to Clean Up

| File | Change |
|------|--------|
| `backend/requirements.txt` | Remove `asknews`, `tenacity`, `structlog`; upgrade `httpx==0.25.2` → `httpx==0.28.1` |
| `backend/pipeline/scheduler.py` | Remove job registrations for `news_job` and `stories_job` |
| `backend/api/routes/admin.py` | Remove any AskNews-specific admin routes |
| `backend/pipeline/services/storage_service.py` | Remove `batch_insert_articles()` and other article-specific functions |
| `backend/pipeline/services/deduplication_service.py` | Remove AskNews-specific deduplication logic |
| `backend/pipeline/services/sentiment_service.py` | Remove AskNews-specific `extract_story_sentiment()` |
| `backend/utils/constants.py` | Keep `ENTITY_NAMES` (still needed), remove AskNews-specific constants |
| `backend/db/models.py` | Remove `Article`, `SentimentTimeseries` classes; add `Post`, `PostEntityMention`, `AspectSentiment` |
| `backend/alembic/env.py` | Update imports, add pgvector registration, add TimescaleDB schema filtering |
| `.env.example` | Remove `ASKNEWS_API_KEY` |
| `docker-compose.yml` | Remove `ASKNEWS_API_KEY` from env; change postgres image |

### httpx Version Note
The comment in `requirements.txt` explicitly states: `# Note: httpx version constrained by asknews dependency (<0.26.0)`. Once `asknews` is removed, upgrading to `httpx==0.28.1` is safe and recommended. httpx 0.28.x introduces minor breaking changes around `httpx.Auth` — the `APIKeyAuth` class in `asknews_client.py` is being deleted anyway, so no migration is needed.

---

## Docker Compose Update

Replace the `postgres` service image:

**Before:**
```yaml
postgres:
  image: postgres:16-alpine
```

**After:**
```yaml
postgres:
  image: timescale/timescaledb-ha:pg16-latest
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
```

**Notes:**
- `timescale/timescaledb-ha:pg16-latest` includes TimescaleDB, pgvector, and pgvectorscale pre-installed. No custom Dockerfile needed for the database.
- The pg16 HA image is confirmed to include pgvector as of early 2026 (pg18 has a known pgvector gap, avoid it).
- Pin to `pg16-latest` not `latest` to avoid unexpected PostgreSQL major version changes.

---

## Hosting Platform Research

Per CONTEXT.md, phase 5 only prepares the codebase. Actual deployment is out of scope. This section informs the decision for the deployment phase.

### Platform Comparison

| Platform | App Compute | PostgreSQL | Est. Monthly | Notes |
|----------|-------------|------------|--------------|-------|
| **Oracle Cloud Free Tier** | 4 ARM cores / 24GB RAM (always free) | Self-hosted on same VM | **$0** | Best for $0 budget. ARM64 Docker images needed. TimescaleDB ARM64 images available. |
| **Fly.io** | Shared-CPU 256MB (~$2/mo), 1GB (~$5/mo) | Self-hosted Postgres app (~$5-10/mo) OR Managed Basic ($38/mo) | **$10-15/mo (self-hosted PG)** | Best DX. Use Fly Postgres app (not managed) to control costs. |
| **Railway** | Usage-based | $92.50+/mo (managed) | **$100+/mo** | Nicest DX but most expensive for Postgres |
| **Hetzner VPS** | CX22 (2 CPU, 4GB, €6/mo) | Self-hosted Docker | **~$7/mo** | Very cheap, requires manual VPS management |
| **Render** | (Being abandoned per decision) | — | — | User decided to leave |

### Recommendation for Deployment Phase

**$0 budget**: Oracle Cloud Free Tier with Docker Compose. 4 ARM cores + 24GB RAM handles FastAPI + TimescaleDB + future ML models with room to spare. Requires ARM64-compatible Docker images — `timescale/timescaledb-ha:pg16-latest` supports `linux/arm64`.

**Small budget (~$10-15/mo)**: Fly.io with a self-hosted Postgres app (not managed Postgres). Deploy FastAPI as a Fly Machine and run Postgres as a separate Fly app with a persistent volume. Avoids $38/mo managed Postgres cost.

**Codebase preparation for new platform:** Phase 5 should remove all Render-specific configuration (environment variable names, Render-specific secrets) and ensure the app is fully configurable via standard environment variables (`DATABASE_URL`, `ENVIRONMENT`, etc.). This is already mostly the case — no Render SDK or Render-specific features are used in the codebase.

---

## Common Pitfalls

### Pitfall 1: TimescaleDB Alembic Index Drift
**What goes wrong:** After converting `posts` to a hypertable, TimescaleDB auto-creates an index (e.g., `posts_published_at_idx`). On the next `alembic revision --autogenerate`, Alembic detects this index as "not in the model" and generates a migration to drop it.
**Why it happens:** Alembic compares DB state to model metadata. TimescaleDB indexes aren't defined in SQLAlchemy models.
**How to avoid:** Add `include_object` filter to `env.py` that excludes the TimescaleDB auto-created index by name, and excludes all TimescaleDB internal schemas.
**Warning signs:** Autogenerated migration contains `op.drop_index('posts_published_at_idx')`.

### Pitfall 2: pgvector Extension Missing at Migration Time
**What goes wrong:** The `vector` extension doesn't exist when the migration runs, causing `CREATE TABLE ... embedding VECTOR(384)` to fail.
**Why it happens:** Extension must be installed before any table referencing the type is created.
**How to avoid:** Always call `op.execute("CREATE EXTENSION IF NOT EXISTS vector")` in the same migration before the `op.create_table()` calls. The `IF NOT EXISTS` clause makes it idempotent.
**Warning signs:** `ERROR: type "vector" does not exist` during migration.

### Pitfall 3: alembic check Fails After pgvector Column Addition
**What goes wrong:** Running `alembic check` reports drift even on a freshly migrated database because it doesn't recognize the `vector` type.
**Why it happens:** Alembic's PostgreSQL dialect doesn't know the `vector` type by default.
**How to avoid:** Register the type in `do_run_migrations()`: `connection.dialect.ischema_names['vector'] = pgvector.sqlalchemy.Vector`
**Warning signs:** `alembic check` reports columns with vector type as having changed type.

### Pitfall 4: Hypertable on Non-TimescaleDB Database
**What goes wrong:** Migration runs locally against a plain PostgreSQL instance (not TimescaleDB) and fails at `SELECT create_hypertable(...)`.
**Why it happens:** Developer's local DB image doesn't have TimescaleDB installed.
**How to avoid:** Update Docker Compose in step one of the phase. All developers must use the TimescaleDB image. Add a comment in the migration about the image requirement.
**Warning signs:** `ERROR: function create_hypertable(unknown, unknown, if_not_exists => boolean) does not exist`.

### Pitfall 5: Leftover AskNews References Break Startup
**What goes wrong:** App fails to start because removed files are still imported somewhere.
**Why it happens:** Incomplete audit of all import sites.
**How to avoid:** After removing files, run `grep -r "asknews\|AskNewsClient\|news_job\|stories_job" backend/` to find remaining references. Grep is already done: 14 files need attention (see AskNews Removal Scope above).
**Warning signs:** `ImportError: cannot import name 'AskNewsClient'` at startup.

### Pitfall 6: Missing `url_hash` Column in New Schema
**What goes wrong:** The old migration `435b852d9d02_add_url_hash_to_articles.py` added `url_hash` to the `articles` table. The reset migration must not reference the old migration chain.
**Why it happens:** If the destructive migration uses `down_revision` pointing to an old migration, upgrading from a fresh DB will try to run old migrations first.
**How to avoid:** The destructive migration should have `down_revision = None` (fresh start) OR point to the last migration in the chain. Given full data wipe, use a sequential approach: write migration that marks previous chain as "squashed" and starts fresh.

---

## Code Examples

### Content Hash Generation (for deduplication)
```python
# Source: Python standard library
import hashlib

def compute_content_hash(title: str, body: str | None, url: str | None) -> str:
    """SHA-256 hash of normalized post content for deduplication."""
    content = f"{title or ''}{body or ''}{url or ''}"
    return hashlib.sha256(content.encode('utf-8')).hexdigest()
```

### Aspect Sentiments Constants (application-level enforcement)
```python
# backend/utils/constants.py — add alongside ENTITY_NAMES
VALID_ASPECTS = frozenset({
    "performance",
    "cost",
    "reliability",
    "ux",
    "speed",
    "code_quality",
    "context_window",
})

ASPECT_SCORE_RANGE = (-1.0, 1.0)
```

### pgvector Similarity Query (for future use, document pattern now)
```python
# Source: github.com/pgvector/pgvector-python
from pgvector.sqlalchemy import Vector
from sqlalchemy import select

# Find similar posts to a query embedding
async def find_similar_posts(embedding: list[float], limit: int = 10, session: AsyncSession):
    result = await session.execute(
        select(Post)
        .order_by(Post.embedding.cosine_distance(embedding))
        .limit(limit)
    )
    return result.scalars().all()
```

### Alembic Migration Downgrade (for reset scenario)
```python
def downgrade() -> None:
    """Downgrade drops the new schema. Cannot restore old data (fresh start decision)."""
    op.drop_table('aspect_sentiments', if_exists=True)
    op.drop_table('post_entity_mentions', if_exists=True)
    op.drop_table('posts', if_exists=True)  # Also drops hypertable and chunks
    op.drop_table('entities', if_exists=True)
    op.execute("DROP EXTENSION IF EXISTS vector")
    op.execute("DROP EXTENSION IF EXISTS timescaledb CASCADE")
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `asknews` SDK for news data | Direct API calls to HN, Reddit, GitHub, Discourse | Phase 5 decision | Eliminates $0→paid API dependency, enables multi-source |
| `httpx==0.25.2` (asknews-constrained) | `httpx==0.28.1` | Removing asknews removes constraint | Latest async HTTP client with improved streaming |
| `postgres:16-alpine` (no extensions) | `timescale/timescaledb-ha:pg16-latest` | Phase 5 migration | Enables hypertables + vector search in one image |
| `articles` + `sentiment_timeseries` tables | `posts` hypertable + `aspect_sentiments` | Phase 5 schema reset | Supports multi-source, aspect-level sentiment, semantic search |
| `structlog` for structured logging | Remove `structlog`, use standard `logging` | Phase 5 cleanup | One less dependency; structlog was only used in AskNews client code |

**Deprecated/outdated:**
- `tenacity` retry library: Was used only in `news_job.py` for AskNews retries. Not needed once the job is deleted. If retry logic is needed for future HTTP sources, `httpx` has built-in retry support via transport adapters.
- `structlog`: Used in `asknews_client.py` and pipeline jobs. Once those files are deleted, check if any remaining code uses `structlog`. If not, remove from `requirements.txt`.

---

## Open Questions

1. **What to do with `scheduler_execution_log` table?**
   - What we know: The table exists and is populated by APScheduler. It's not AskNews-specific.
   - What's unclear: Should it be kept as-is or also dropped/redesigned?
   - Recommendation: Keep it. It's infrastructure-agnostic audit logging that will still be useful for future pipeline jobs.

2. **What to do with `entities` table during full wipe?**
   - What we know: The full wipe decision says "drop ALL existing data (articles, sentiment_timeseries, entities)." But entities "will be re-seeded in a later phase."
   - What's unclear: Should the migration drop and recreate the entities table (empty but with same schema), or is the entities schema changing?
   - Recommendation: Drop and recreate the entities table with the same schema. This gives a clean start while preserving the table structure for the re-seeding phase.

3. **Does `structlog` exist anywhere outside of pipeline/clients/?**
   - What we know: `structlog` is imported in `asknews_client.py`, `news_job.py`, `stories_job.py`, `sentiment_service.py`
   - What's unclear: Are there other files using `structlog` not in the 14-file AskNews grep results?
   - Recommendation: After AskNews cleanup, grep for remaining `structlog` imports before removing from `requirements.txt`.

4. **Alembic migration chain: fresh head or continuation?**
   - What we know: There are currently 5 migrations (001 through 67a003713f58). The new migration needs to drop old tables.
   - What's unclear: Should the new migration be `006_reset_schema.py` with `down_revision = '67a003713f58'` (continuation of chain), or a standalone with `down_revision = None` (breaking the chain)?
   - Recommendation: Continue the chain (`down_revision = '67a003713f58'`) so that existing databases that have already run migrations 001-005 will upgrade correctly. New databases can still run `alembic upgrade head` and will run all migrations in order. The reset migration simply drops the old tables first.

---

## Sources

### Primary (HIGH confidence)
- [pgvector/pgvector-python GitHub](https://github.com/pgvector/pgvector-python) — Vector type support for SQLAlchemy, asyncpg, Alembic patterns
- [Alembic discussions #1324](https://github.com/sqlalchemy/alembic/discussions/1324) — pgvector type registration in `ischema_names`
- [Alembic discussions #1465](https://github.com/sqlalchemy/alembic/discussions/1465) — TimescaleDB hypertable index filtering in `env.py`
- [timescale/timescaledb Docker Hub](https://hub.docker.com/r/timescale/timescaledb) — Image tags, pg16/pg17 support
- [Fly.io Managed Postgres Docs](https://fly.io/docs/mpg/) — Pricing tiers: Basic $38/mo
- [Fly.io Resource Pricing](https://fly.io/docs/about/pricing/) — Machine costs: ~$2-5/mo shared CPU
- Project file audit (14 files with AskNews references) — grep results verified

### Secondary (MEDIUM confidence)
- [timescale/timescaledb-docker-ha releases](https://github.com/timescale/timescaledb-docker-ha/releases) — pgvector included in pg16/pg17 HA images, pg18 had missing pgvector issue Nov 2025
- [Oracle Cloud Free Tier](https://www.oracle.com/cloud/free/) — 4 ARM cores + 24GB RAM always free, 240GB block storage
- [sentiment_analysis_improvement.md](../../../sentiment_analysis_improvement.md) — Schema recommendations (posts hypertable, VECTOR(384), JSONB metadata, content_hash)

### Tertiary (LOW confidence)
- Various WebSearch results on Fly.io, Railway, Hetzner pricing comparisons — cross-referenced with official docs where possible

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified against official docs, existing project requirements
- Architecture patterns: HIGH — verified against Alembic and pgvector GitHub discussions
- Pitfalls: HIGH — sourced from actual GitHub issues and discussions
- Hosting research: MEDIUM — pricing verified against official Fly.io docs; Oracle Cloud claims from multiple sources

**Research date:** 2026-02-19
**Valid until:** 2026-03-21 (30 days, stable ecosystem)
