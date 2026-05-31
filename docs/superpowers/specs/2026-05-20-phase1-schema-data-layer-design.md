# Phase 1 — Schema & Data Layer — Design

**Date:** 2026-05-20
**Branch:** `phase-1-schema-data-layer`
**Status:** Design settled — data layer uses pgschema (declarative) + Scythe 0.8.0 (updated 2026-05-31; codegen is now DB-free).

## Goal

Stand up vibecheck's database schema, Scythe query files, and generated
data-access code in `lib/db`, with a verified end-to-end path from declarative schema → generated
Python → live Postgres.

## Context

vibecheck is a sentiment dashboard tracking AI dev tools (cursor, claude-code, …) across sources
(reddit, hn, …). The repo is a clean restart: a uv-workspace monorepo with `lib/db` and three
services (`api`, `ingestion`, `worker`) over Postgres + RabbitMQ + Redis. The data layer is
**SQL-first**: schema and queries are authored as SQL; **Scythe** (sqlc-style) generates typed
Python; **pgschema** applies the declarative schema to the database. There is no ORM.

## Data model

Five-table core. Rollups are **deferred** to a later phase (dashboard queries live for now).

### Decisions

- **Many tools per post.** `posts` are source-pure; a `mentions` join table links posts↔tools
  many-to-many. A single thread mentioning two tools is one post with two mentions.
- **`tools` is a curated dimension table** with `aliases text[]` driving ingestion/relevance matching.
- **Sentiment is per-mention (aspect-based):** `analysis_results.mention_id → mentions(id)`,
  one score per (post, tool, model). Handles mixed-sentiment posts ("Cursor is great but Claude is buggy").
- **Re-scoring keeps history via version-in-key:** `model_version` is a nullable string and part of
  `UNIQUE NULLS NOT DISTINCT (mention_id, model_name, model_version)`. Intentional model/version
  comparisons coexist; accidental identical re-runs dedupe (incl. when version is NULL — PG15+ semantics).
- **Time axis is `posts.published_at`** (when content was written), never `analyzed_at` (when we scored
  it) — backfill would otherwise collapse all history onto one day.

### DDL (validated against Postgres 18)

```sql
CREATE TABLE tools (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug         varchar(50)  NOT NULL UNIQUE,
    display_name varchar(255) NOT NULL,
    aliases      text[]       NOT NULL DEFAULT '{}',
    created_at   timestamptz  NOT NULL DEFAULT now()
);

CREATE TABLE posts (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    source       varchar(20)  NOT NULL,        -- 'reddit', 'hn', ...
    source_id    varchar(255) NOT NULL,        -- original id from source
    content      text         NOT NULL,
    author       varchar(255),
    url          varchar(2048),
    published_at timestamptz  NOT NULL,
    metadata     jsonb        NOT NULL DEFAULT '{}',
    created_at   timestamptz  NOT NULL DEFAULT now(),
    UNIQUE (source, source_id)                 -- idempotent ingest
);
CREATE INDEX idx_posts_published_at ON posts (published_at);

CREATE TABLE mentions (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    post_id    uuid NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    tool_id    uuid NOT NULL REFERENCES tools(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (post_id, tool_id)
);
CREATE INDEX idx_mentions_tool_id ON mentions (tool_id);

CREATE TABLE analysis_results (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    mention_id    uuid             NOT NULL REFERENCES mentions(id) ON DELETE CASCADE,
    model_name    varchar(100)     NOT NULL,        -- e.g. 'twitter-roberta-base'
    model_version varchar(50),                       -- nullable; part of the uniqueness key
    score         double precision NOT NULL,
    label         varchar(20)      NOT NULL,         -- 'positive' | 'negative' | 'neutral'
    raw_output    jsonb,
    analyzed_at   timestamptz      NOT NULL DEFAULT now(),
    UNIQUE NULLS NOT DISTINCT (mention_id, model_name, model_version)
);
CREATE INDEX idx_analysis_mention ON analysis_results (mention_id, model_name, analyzed_at DESC);
```

### Index rationale

| Index / constraint | Why |
|---|---|
| `posts UNIQUE(source, source_id)` | Idempotent ingest + existence lookup. Leftmost-prefix also serves "by source". |
| `idx_posts_published_at` | Dashboard time-range filtering on the true time axis. (Upgrade path: BRIN at scale.) |
| `mentions UNIQUE(post_id, tool_id)` | One link per post↔tool; idempotent. Leftmost-prefix covers "tools for a post" — **no separate `post_id` index needed.** |
| `idx_mentions_tool_id` | "All mentions of a tool" (core dashboard hop) + FK cascade safety. |
| `analysis_results UNIQUE NULLS NOT DISTINCT(mention_id, model_name, model_version)` | Version-in-key dedup (see decisions). |
| `idx_analysis_mention` (`mention_id, model_name, analyzed_at DESC`) | FK join (covers `mention_id` alone) + cheap "latest score per model". |

Deferred/conditional (add when a query needs them): GIN on `tools.aliases` (if relevance filter does
`aliases @> ARRAY[...]`), GIN on `posts.metadata` (if querying into JSONB), BRIN on `published_at` at scale.

The dashboard's "sentiment per tool over time" runs as a 3-table join (`analysis_results → mentions →
posts`, grouped by `tools.slug` and `date_trunc('day', posts.published_at)`). We deliberately do **not**
denormalize `published_at` onto `mentions` or pre-aggregate yet; revisit if the live join proves slow.

## Seed data — `tools` registry

`tools` is curated reference data (a slowly-changing dimension), distinct in kind from the runtime
facts in `posts`/`mentions`/`analysis_results`. It is loaded by an **idempotent, pure-SQL seed
script** — `sql/seeds/tools.sql` — applied with `psql -f`. Each row is an
`INSERT … ON CONFLICT (slug) DO UPDATE SET display_name = …, aliases = …`, so the script is
re-runnable: a fresh DB gets populated, an existing DB converges to the file's contents, and editing
the tool list is a one-file edit + re-run.

**Why this over the alternatives:** the tool list changes more often than the schema (alias-tuning is
iterative) and for different reasons (curation, not engineering), so it should be cheap and decoupled
from schema changes. A *schema-embedded seed* was rejected because every list edit would require a
schema re-apply and conflate curation with structural changes; *startup upsert* was rejected because
it couples three services' boot to DB writes and races on concurrent start.

**Anchored on `slug`, never `id`.** `mentions.tool_id` is a UUID FK; upserting on the stable `slug`
keeps each tool's UUID stable across re-runs so existing mentions never break. The seed is upsert-only
— removing a tool from the file does **not** delete its row (deleting a tracked tool with live mentions
is a deliberate act, not a side effect of editing the file).

**Format rationale:** pure SQL (not a data-file + Python loader) matches the SQL-first, no-ORM ethos,
adds zero dependencies, and reads like the rest of the data layer.

Initial registry (slugs/display names/aliases are a starting point; aliases assume ingestion
case-folds before matching, so they are stored lowercase):

| slug | display_name | aliases (starter) |
|---|---|---|
| `cursor` | Cursor | cursor, cursor ai, cursor editor |
| `claude-code` | Claude Code | claude code, claudecode, cc |
| `github-copilot` | GitHub Copilot | copilot, gh copilot, github copilot |
| `windsurf` | Windsurf | windsurf, codeium windsurf |
| `cline` | Cline | cline, claude dev |
| `aider` | Aider | aider, aider chat |
| `chatgpt` | ChatGPT | chatgpt, gpt, openai chatgpt |
| `kilo` | Kilo Code | kilo, kilo code, kilocode |
| `codex` | Codex | codex, openai codex, codex cli |

## Schema management — pgschema (declarative)

- **`sql/schema.sql`** is the single source of truth — a hand-authored, declarative desired-state DDL
  file. Both pgschema (database apply) and Scythe (code generation) consume it directly. There are no
  migration files and no `schema_migrations` table.
- **pgschema** (v1.10.0) reconciles a live database to `sql/schema.sql` via a two-phase `plan` →
  `apply`. The helper `scripts/db-apply.sh` runs `pgschema apply`; it sources `scripts/pg-env.sh` to
  derive discrete `PG*` connection vars from `DATABASE_URL` (pgschema takes `PG*` vars, not a URL).
- **squawk** lints the SQL emitted by `pgschema plan --output-sql` for unsafe-migration detection
  (free; replaces the linting that Atlas moved behind Pro as of v0.38). **Known CI caveat:** the
  schema is applied to a blank service DB first, so the subsequent plan is empty and squawk has
  nothing to lint there. The gate has real content only when planning against a DB that holds the
  prior schema (locally before applying, or a staging baseline). The CI step handles this gracefully:
  if the plan file is empty it prints a notice and exits clean.
- **Rollback:** revert `sql/schema.sql` and re-apply; pgschema computes the reverse diff. The `plan`
  review step gates destructive diffs. Acceptable for greenfield.
- **Atlas was rejected** despite its declarative `sql/schema`-as-source-of-truth alignment with
  Scythe, because its lint is now Pro-only ($9/dev/mo + $59/CI-project/mo) and absent from the OSS
  Community Edition. pgschema delivers the same declarative model for free (open-source), which also
  eliminates the original selling point of dbmate's hand-written `up`/`down` approach: Scythe only
  ever needed a flat DDL file, and `sql/schema.sql` is exactly that authored artifact.

## Codegen pipeline — Scythe (pinned 0.8.0)

Scythe generates the `python-psycopg3` backend: **async** functions taking an `AsyncConnection`, returning
frozen `@dataclass(slots=True)` row types, using `%(name)s` params. The default backend is `rust-sqlx`, so
Python must be selected explicitly.

**The pipeline is 1 step, DB-free** (see [Validation](#validation)):

```
edit sql/schema.sql  →  scythe generate
```

Scythe reads `sql/schema.sql` statically — no Postgres instance is required. The former
`dbmate up → dbmate dump → strip backslash lines → scythe generate → patch imports` five-step pipeline
is gone entirely.

**Scythe 0.8.0** eliminated the two workarounds that were mandatory in 0.7.0:

1. ~~**Strip psql meta-commands.**~~ No longer needed — Scythe reads the hand-authored `sql/schema.sql`
   directly; there is no `pg_dump` output and no `\restrict` / `\unrestrict` to strip.
2. ~~**Patch missing imports.**~~ Scythe 0.8.0 emits `import uuid` and `from typing import Any`
   natively. The post-generate import-patch step has been deleted.

**One workaround remains:** psycopg3 won't adapt a plain `dict` to `jsonb` implicitly. The
`JsonbDumper` registration in `lib/db`'s connection factory (`lib_db/pool.py`) is still necessary
and is unrelated to Scythe.

### `scythe.toml` (exact shape for 0.8.0)

```toml
[scythe]
version = "1"

[[sql]]
name = "main"
engine = "postgresql"
schema = ["sql/schema.sql"]          # the hand-authored declarative DDL
queries = ["sql/queries/*.sql"]

[[sql.gen]]                          # array-of-tables; a single [sql.gen] silently emits Rust
backend = "python-psycopg3"
output = "lib/db/lib_db/generated"
```

Notes:
- `sql/schema.sql` is the authored artifact — Scythe reads it statically, with no database involved.
- Query annotations are `-- @name X` / `-- @returns one|many` (NOT sqlc's `-- name:`). Lint prefers
  verb-prefixed names (`Create…` over `Insert…`, SC-N03) and flags `ORDER BY` without `LIMIT` (SC-P01).

### Where the pipeline lives — `scripts/codegen.sh`

The pipeline is encoded in a single committed shell script, `scripts/codegen.sh`
(`set -euo pipefail`), invoked identically locally and in CI so the two never drift. The script is the
single source of truth for the sequence. A task runner (make/just) was rejected for now: the repo has
none today (it's `uv` + `pre-commit` + GitHub Actions + shell), the steps are inherently shell, and a
lone script fits that grain. Promote to a task runner later only if the command set grows.

**No Postgres lifecycle.** The script requires no running database — `scythe generate` reads
`sql/schema.sql` statically. To change the schema: edit `sql/schema.sql`, then run
`scripts/codegen.sh`.

**Generated code is committed.** The generated Python in `lib/db` is checked in. Local workflow: edit
`sql/schema.sql` / queries → run `scripts/codegen.sh` → commit the regenerated output alongside the
SQL change.

**Wiring:**

| Stage | What runs | Why there |
|---|---|---|
| pre-commit | unchanged: `ruff`, `scythe fmt`, `scythe lint --fix`, `mypy` | Codegen is a deliberate manual/CI act; SQL authoring stays linted at commit time. |
| CI — schema apply | `scripts/db-apply.sh --auto-approve` | Reconciles the service DB to `sql/schema.sql` before seed and pytest (replaces `dbmate up`). |
| CI — codegen freshness gate | `./scripts/codegen.sh`, then `git diff --exit-code lib/db/lib_db/generated/` | Stale committed generated code cannot merge — this is what makes "commit the output" safe. |
| CI — schema safety | `pgschema plan --output-sql` piped to `squawk`; skipped if plan is empty (see caveat above) | Squawk checks schema-change safety (orthogonal to scythe, which lints query SQL). A CI gate, not pre-commit, to keep commits fast. |
| CI / local — seed | `psql -f sql/seeds/tools.sql` after pgschema apply | So smoke tests exercise queries (`ListTools`, the sentiment join) against realistic reference data. Kept out of `codegen.sh` — seeding is a data op, codegen is a build op; each script stays single-purpose. |

## `lib/db` public API — Option A (thin layer + pool factory)

The generated functions **are** the typed API. `lib/db` adds only the two unavoidable jobs and re-exports
them; services own pool lifecycle and pass connections explicitly.

```python
# lib_db/pool.py
from psycopg_pool import AsyncConnectionPool
from psycopg.types.json import JsonbDumper

async def _configure(conn):
    conn.adapters.register_dumper(dict, JsonbDumper)   # dict -> jsonb (psycopg3 won't do it implicitly)

def create_pool(dsn: str) -> AsyncConnectionPool:
    return AsyncConnectionPool(dsn, configure=_configure, open=False)

# lib_db/__init__.py
from .pool import create_pool
from .generated import queries
```

**Consumption** (one pool per process at startup; one connection per unit of work at the entry seam):

```python
# API (FastAPI): pool in lifespan, connection via a single Depends
@asynccontextmanager
async def lifespan(app):
    app.state.pool = create_pool(DSN); await app.state.pool.open()
    yield
    await app.state.pool.close()

async def get_conn(request):
    async with request.app.state.pool.connection() as conn:
        yield conn

@app.get("/tools")
async def list_tools(conn = Depends(get_conn)):
    return await queries.list_tools(conn)

# Worker: one connection + transaction per message (atomic post+mention+analysis)
async def handle_message(msg):
    async with pool.connection() as conn, conn.transaction():
        post = await queries.insert_post(conn, ...)
        await queries.insert_mention(conn, post_id=post.id, ...)
        await queries.insert_analysis_result(conn, mention_id=..., ...)
```

Rejected alternatives: **B** (repository facade) — decoupling without a real transaction-boundary payoff,
plus per-query boilerplate; **C** (global pool) — breaks multi-row atomic writes; **D** (unit of work) and
**E** (contextvar) — warranted only for deep call stacks, which these thin services don't have. Revisit D/E
if the worker's logic deepens.

## Initial query set (1.3)

In `sql/queries/`, validated and round-tripped against live Postgres:

- `InsertPost` (idempotent `ON CONFLICT (source, source_id) DO NOTHING`, jsonb metadata) — ingestion
- `InsertAnalysisResult` (jsonb `raw_output`, nullable `model_version`) — worker
- `GetSentimentByToolBucket` (3-table join, `date_trunc` day buckets, `avg`/`count`) — api
- `ListTools` — api
- `GetPostsByToolAndRange` (join, time range) — api

(Per the lint convention, `Insert*` will likely be renamed `Create*`.)

## Verification (1.4)

A pytest smoke test imports the generated module and exercises each query function against a test Postgres
(from docker-compose) with seeded data. This is already proven manually in the spike: all five functions
work, including jsonb adaptation, `text[] → list[str]`, nullable inference, and the aggregate join.

## Validation

A throwaway spike executed the full path against an ephemeral `postgres:latest`:
`edit sql/schema.sql → scythe generate (python-psycopg3) → psycopg3 round-trip`; plus
`pgschema apply` + idempotent plan verified (empty plan on second apply confirms no drift).
Confirmed: the schema and all firm constraints/indexes apply cleanly; Scythe parses `sql/schema.sql`
statically (no DB required); type inference is correct; and all five generated functions execute
correctly (e.g. `GetSentimentByToolBucket → ('claude', '2026-05-01', 1, 0.82)`).

## Out of scope (Phase 1)

Sentiment rollups / pre-aggregation tables; GIN/BRIN indexes; the actual ingestion/scoring logic; the
dashboard API endpoints (only the queries backing them are defined here).
