# Phase 2 — API Service — Design

**Date:** 2026-06-06
**Branch:** `phase-2-api-service`
**Status:** Design settled in brainstorming; awaiting spec review before planning.

## Goal

Stand up the FastAPI service that serves **dashboard data** from the `lib_db`
data layer, built **test-first** (integration tests before implementation),
demoable end-to-end against *seeded* data before ingestion or the worker exist.
By the checkpoint: the API serves correct data from Postgres, is covered by
integration tests, and exposes a verified OpenAPI spec ready for the Phase 3
frontend.

## Context — what 2.1 already delivered

Phase 2.1 (committed `8d1a718`) scaffolded the service: `services/api/` is a uv
workspace member depending on `lib-db` + `fastapi` + `uvicorn` + `psycopg`, with
`api/main.py` (FastAPI app, a lifespan that owns the `lib_db` async pool, and a
DB-free `/health` liveness probe), a `Dockerfile`, and an `api` service wired
into `docker-compose.yml` (built, run, and verified healthy end-to-end). This
means **2.5's "add API to Docker Compose" is already done**; 2.5 reduces to
seeding data and curling the real endpoints.

### Reconciliation with the original plan (written pre-Phase-1)

- **"Apply migrations" is stale.** Phase 1 dropped migrations for a declarative
  `sql/schema.sql` applied via `psql -f`, plus `sql/seeds/tools.sql`. `conftest`
  therefore assumes the schema is present (CI loads it before pytest; the local
  dev DB already has it) and manages only test *facts*.
- **`bucket=week` needs a data-layer change.** The Phase 1
  `GetSentimentByToolBucket` hard-codes day buckets and takes explicit
  timestamps. We parameterize it (see [Data layer changes](#data-layer-changes-libdb)).
- **TS client generation moves to Phase 3.** 2.4 here delivers only the spec
  artifact; the `openapi-typescript`/`openapi-fetch` setup is a frontend concern.

## Scope

**In:** `GET /api/v1/tools`, `GET /api/v1/sentiment/{tool}`, their Pydantic
response models, period/bucket parsing, the integration-test harness, and the
committed OpenAPI spec + regen script + verification test + CI freshness gate.

**Out (deferred, not cancelled):** a posts/drill-down endpoint (the
`GetPostsByToolAndRange` query exists but has no consumer yet — YAGNI until the
frontend needs drill-down); TypeScript client generation (Phase 3); explicit
`from`/`to` custom-range params (see [Time window](#time-window--determinism)).

## Endpoints & contract

`/health` stays **unversioned at root** — it is an ops/liveness concern, not part
of the versioned data contract. Business endpoints live under `/api/v1`.

### `GET /api/v1/tools`

Returns the curated tool registry. Backed by `queries.list_tools`.

```
200 → [ Tool, … ]
Tool = { slug: str, display_name: str, aliases: list[str] }
```

The DB-internal `id` (uuid) and `created_at` are deliberately **omitted** — the
public contract exposes only what the dashboard needs, decoupled from the row
shape.

### `GET /api/v1/sentiment/{tool}`

Time-bucketed average sentiment for one tool. Query params:

| Param | Default | Validation |
|---|---|---|
| `period` | `30d` | `^\d+[dw]$` (days or weeks). Invalid → 422. |
| `bucket` | `day` | one of `day` \| `week` \| `month`. Invalid → 422. |

```
200 → SentimentSeries
SentimentSeries = {
  tool: str,            # slug
  period: str,          # echo of the resolved/defaulted period, e.g. "30d"
  bucket: str,          # granularity, e.g. "week"
  start: datetime,      # window start (UTC, inclusive)
  end: datetime,        # window end (UTC, exclusive)
  series: [ SentimentPoint, … ]   # SPARSE — only buckets that have data
}
SentimentPoint = { bucket_start: datetime, n: int, avg_score: float }
```

**Sparse series:** weeks/days/months with no posts are simply absent (SQL
`GROUP BY date_trunc` only emits non-empty buckets). The API returns facts; the
client owns gap-filling. A tool that exists but has no data in the window returns
`200` with `series: []`.

### Error semantics

| Case | Status | Why |
|---|---|---|
| `/sentiment/{tool}` with a slug not in the registry | **404** | A path param addresses a resource; absent resource → 404. Detected via `GetToolBySlug` (a zero-row sentiment result cannot distinguish "unknown tool" from "no data"). |
| `period` or `bucket` malformed | **422** | Well-formed request, semantically invalid value — FastAPI's native validation status, raised by the param dependency. |
| Tool exists, no data in window | **200** | Absence of data is a valid state, not an error. |

Error **body** is FastAPI's default `{"detail": …}` — standard, and what the
generated OpenAPI/TS client expects. No bespoke error envelope.

## Aggregation decision (the keystone)

**Chosen: bucket granularity computed in SQL** (`date_trunc(%(bucket)s, …)`),
not re-aggregated in Python.

Rationale (first principles): a mean is **not composable** —
`mean(mean(A), mean(B)) ≠ mean(A∪B)` unless the groups are equal-sized. Computing
the bucket average in SQL over the raw rows is **correct by construction**: the
DB never forms intermediate sub-means, so there is nothing to (mis)recompose. The
`date_trunc` unit is an ordinary runtime **text bind parameter** (not string
interpolation), so this is injection-safe and fits Scythe's static-SQL model as a
one-token generalization of the existing query. The alternative (fetch day
buckets, fold to weeks in Python) would keep `lib/db` frozen but move a
weighted-average correctness obligation into the API; we preferred correctness in
the DB and accept reopening `lib/db` once (a natural evolution of the query the
API owns).

## Data layer changes (`lib/db`)

Two SQL edits, then `./scripts/codegen.sh` regenerates
`lib/db/lib_db/generated/queries.py` (the existing CI codegen-freshness gate
already guards drift).

1. **Parameterize `GetSentimentByToolBucket`** — replace the literal `'day'` with
   `%(bucket)s`:
   ```sql
   date_trunc(%(bucket)s, p.published_at AT TIME ZONE 'UTC') AT TIME ZONE 'UTC' AS bucket
   ```
   New signature: `get_sentiment_by_tool_bucket(conn, *, slug, bucket,
   published_at_1, published_at_2)`. The API validates `bucket` against the
   whitelist *before* the call, so the DB only ever receives a valid unit.
2. **Add `GetToolBySlug`** to `sql/queries/tools.sql` — `SELECT … FROM tools
   WHERE slug = %(slug)s`, `-- @returns one`. Used purely as an existence check
   (None → 404).

## Module structure

```
services/api/api/
  main.py          # app assembly: lifespan (pool), include_router, /health. Stays thin.
  dependencies.py  # get_conn (pool → connection); the sentiment query-param
                   #   dependency resolving (period, bucket) → (start, end, bucket)
                   #   or raising 422; an injectable `now` provider.
  periods.py       # PURE domain logic: parse_period("30d") → timedelta,
                   #   BUCKETS whitelist + validation. No HTTP, no DB.
  models.py        # Pydantic response models: Tool, SentimentPoint, SentimentSeries
  routes.py        # one APIRouter(prefix="/api/v1"): /tools, /sentiment/{tool}
```

`periods.py` is isolated precisely because it is pure — `"invalid" → error` and
`"30d" → timedelta(days=30)` are unit-testable without a client or DB. FastAPI
surfaces its failures as 422 by invoking it through the param dependency.

## Time window & determinism

The window is `[now − period, now)` in UTC. `now` is provided by an **injectable
dependency** (default `datetime.now(UTC)`) so tests override it to a fixed instant
via `app.dependency_overrides` — keeping the public contract `period`-only while
making time-based assertions deterministic. (Explicit `from`/`to` custom-range
params are a clean future enhancement but out of scope here.)

## Serialization

Authored Pydantic response models (above), not the generated dataclasses. Reasons:
the public contract stays decoupled from the DB/codegen row shape; internal fields
are dropped; OpenAPI emits clean named schemas (`Tool`, `SentimentSeries`) that
feed Phase 3's TS generation; and `/sentiment` needs an envelope model regardless,
so using models for `/tools` too keeps the layer uniform.

## Test strategy (2.2 — tests first)

**Layout** (per-package, tests co-located with what they test):

```
lib/db/tests/        # test_smoke.py MOVED here from root tests/ (+ conftest with the conn fixture)
services/api/tests/  # conftest.py (harness) + test_tools.py + test_sentiment.py
# root tests/ removed — reserved for future cross-service E2E (none yet)
```

Root `[tool.pytest.ini_options]`: `testpaths = ["lib/db/tests",
"services/api/tests"]`, `addopts = "--import-mode=importlib"` (avoids
same-named-file collisions across packages and drops `__init__.py` boilerplate),
`asyncio_mode = "auto"`. One `uv run pytest` still runs everything in CI.

**Harness** (`services/api/tests/conftest.py`):

- Connects to the test Postgres via `DATABASE_URL` (CI service DB / local dev DB).
  Schema is assumed already applied; `conftest` manages only facts.
- A **self-contained** fixture creates its *own* tool (raw insert) + known
  posts/mentions/analysis with fixed `score`/`published_at` (relative to the
  fixed test `now`), and returns the slug + expected aggregates. It does **not**
  depend on the global `tools` seed. One bucket is given **unequal daily counts**
  so the test pins the *weighted* mean (proving the SQL average, not mean-of-means).
- The app runs for real: `with TestClient(app) as client:` so the lifespan opens
  the real pool and `Depends(get_conn)` is exercised — a true integration test.
  `now` is overridden to a fixed instant.
- **Cleanup: committed insert + surgical delete by key** in teardown
  (FK-cascade from `posts` clears mentions/analysis; the test tool is removed).
  Non-destructive; consistent with the Phase 1 smoke test.

**Test cases (written before implementation):**

1. `GET /api/v1/tools` → 200, lists the tracked tools (shape = `Tool`).
2. `GET /api/v1/sentiment/{tool}?period=30d&bucket=week` → 200, time-bucketed
   weighted averages match the known fixture values (incl. the unequal-count week).
3. `GET /api/v1/sentiment/{unknown}` → 404.
4. `GET /api/v1/sentiment/{tool}?period=invalid` → 422.
5. `GET /api/v1/sentiment/{tool}?bucket=fortnight` → 422.
6. `GET /api/v1/sentiment/{tool}` over a window with no data → 200, `series: []`.

## OpenAPI (2.4)

- A regen script (`scripts/openapi.sh` or a small `python -m` entry) does
  `from api.main import app; json.dump(app.openapi(), …)` → committed
  **`services/api/openapi.json`** (JSON, not YAML — `app.openapi()` is a dict,
  no extra dep, and TS tooling consumes JSON).
- A **Python verification test** asserts the spec contains the expected paths
  (`/api/v1/tools`, `/api/v1/sentiment/{tool}`) and component schemas (`Tool`,
  `SentimentSeries`, `SentimentPoint`).
- A **CI freshness gate** regenerates and `git diff --exit-code`s `openapi.json`,
  mirroring the existing codegen-freshness gate so the committed spec can't drift.
- TS client generation is **deferred to Phase 3**.

## Docker / Compose (2.5)

Already wired in 2.1. Remaining: a small seed path (reuse `sql/seeds/tools.sql`
plus a minimal fact-seed for demo) and manual `curl` verification of the two
endpoints against the running container.

## Out of scope

Posts/drill-down endpoint; TypeScript client generation; explicit `from`/`to`
range params; auth/rate-limiting; pagination; caching/rollups; any
ingestion/worker logic.

## Decisions made while writing — please confirm in review

1. **`period` grammar:** `^\d+[dw]$` (days/weeks), default `30d`. Months are a
   *bucket* granularity (calendar-aligned via `date_trunc`) but not a *window*
   unit, to avoid the variable-length-month ambiguity in window math. Add `mo`
   for period later if needed.
2. **Default `bucket` = `day`** (finest); `bucket` whitelist = `day|week|month`.
3. **Time window** ends at an injectable `now` (UTC), window = `[now−period,
   now)`; tests override `now`. Public contract is `period`-only.
4. **Response field names:** top-level `bucket` = granularity string; each point's
   timestamp = `bucket_start` (avoids overloading "bucket").
