# Phase 2 — API Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the FastAPI service that serves dashboard data (`/api/v1/tools`, `/api/v1/sentiment/{tool}`) from the `lib_db` data layer, test-first, demoable against seeded data.

**Architecture:** Two read endpoints behind an `/api/v1` router. Bucket-granularity aggregation is computed in SQL (correct-by-construction weighted mean) via a parameterized Scythe query; an authored Pydantic layer decouples the public contract from the generated DB row types. Pure period/bucket parsing is isolated for unit testing; FastAPI dependency injection provides the DB connection and an injectable clock. Integration tests run the real app via `httpx.AsyncClient` against a test Postgres with a self-contained, committed-then-surgically-cleaned data fixture.

**Tech Stack:** Python 3.13, FastAPI, psycopg3 (async), uv workspace, Scythe (SQL codegen), pgschema (declarative schema), pytest + pytest-asyncio + httpx, Postgres.

---

## Reference: spec

`docs/superpowers/specs/2026-06-06-phase2-api-service-design.md`. Read it before starting.

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `lib/db/tests/conftest.py` | `conn` fixture for data-layer tests (moved from root) | 1 |
| `lib/db/tests/test_smoke.py` | data-layer roundtrip/idempotency tests (moved from root) | 1, 2 |
| `services/api/tests/test_health.py` | `/health` liveness test (moved from root, async) | 1 |
| `pyproject.toml` | `testpaths`, `--import-mode=importlib` | 1 |
| `sql/queries/analysis.sql` | parameterize bucket granularity | 2 |
| `sql/queries/tools.sql` | add `GetToolBySlug` | 2 |
| `lib/db/lib_db/generated/queries.py` | regenerated (do not hand-edit) | 2 |
| `services/api/api/periods.py` | PURE: parse period, validate bucket | 3 |
| `services/api/tests/test_periods.py` | unit tests for `periods` | 3 |
| `services/api/api/models.py` | Pydantic response models | 4 |
| `services/api/tests/test_models.py` | contract/field-name test | 4 |
| `services/api/api/dependencies.py` | `get_conn`, `get_now`, `resolve_window` | 5, 7 |
| `services/api/tests/conftest.py` | `db_pool`, `client`, `seeded` fixtures, `FIXED_NOW` | 5 |
| `services/api/tests/test_harness.py` | harness self-test | 5 |
| `services/api/api/routes.py` | `/api/v1` router: `/tools`, `/sentiment/{tool}` | 6, 7 |
| `services/api/api/main.py` | include the router | 6 |
| `services/api/tests/test_tools.py` | `/tools` integration test | 6 |
| `services/api/tests/test_sentiment.py` | `/sentiment` integration tests | 7 |
| `scripts/gen-openapi.sh` | regenerate `openapi.json` | 8 |
| `services/api/openapi.json` | committed OpenAPI spec artifact | 8 |
| `services/api/tests/test_openapi.py` | spec verification test | 8 |
| `.github/workflows/ci.yml` | OpenAPI freshness gate | 8 |
| `sql/seeds/demo_facts.sql` | dev-only demo facts for manual verify | 9 |

**Preconditions:** a Postgres with the schema applied and `tools` seeded must be reachable at `DATABASE_URL` (default `postgres://vibecheck:vibecheck@127.0.0.1:5432/vibecheck?sslmode=disable`). Locally: `docker compose up -d postgres` then `psql "$DATABASE_URL" -f sql/schema.sql` and `psql "$DATABASE_URL" -f sql/seeds/tools.sql` if not already loaded. Verify with `uv run pytest lib/db/tests -q`.

---

### Task 1: Reorganize tests into per-package layout

**Files:**
- Create: `lib/db/tests/conftest.py`, `lib/db/tests/test_smoke.py`, `services/api/tests/test_health.py`
- Modify: `pyproject.toml` (root)
- Delete: `tests/test_smoke.py`, `tests/test_api_health.py`, `tests/__init__.py`

- [ ] **Step 1: Create `lib/db/tests/conftest.py`** with the extracted `conn` fixture

```python
import os

import pytest
from lib_db import create_pool

DSN = os.environ.get(
    "DATABASE_URL",
    "postgres://vibecheck:vibecheck@127.0.0.1:5432/vibecheck?sslmode=disable",
)


@pytest.fixture
async def conn():
    pool = create_pool(DSN)
    await pool.open()
    async with pool.connection() as c:
        yield c
    await pool.close()
```

- [ ] **Step 2: Move the smoke test body** to `lib/db/tests/test_smoke.py`

`git mv tests/test_smoke.py lib/db/tests/test_smoke.py`, then delete the now-duplicated `DSN` constant and the `conn` fixture from it (they live in `conftest.py`). Keep the two test functions (`test_data_layer_roundtrip`, `test_idempotent_creates`) and their imports (`datetime as dt`, `os` may now be unused — remove it; keep `uuid`, `pytest`, `from lib_db import queries`). The top of the file becomes:

```python
import datetime as dt
import uuid

import pytest
from lib_db import queries


async def test_data_layer_roundtrip(conn):
    ...  # unchanged body
```

- [ ] **Step 3: Move + convert the health test** to `services/api/tests/test_health.py` (async `httpx`, so we standardize on one HTTP client)

`git mv tests/test_api_health.py services/api/tests/test_health.py`, then replace its contents with:

```python
"""Health-check test for the API service.

No lifespan/pool is started, so liveness never depends on a database.
"""

from httpx import ASGITransport, AsyncClient

from api.main import app


async def test_health_returns_ok() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 4: Remove the empty root `tests/`**

```bash
git rm tests/__init__.py
rmdir tests 2>/dev/null || true
```

- [ ] **Step 5: Update root `pyproject.toml` (pytest + mypy config)**

(a) Replace the `[tool.pytest.ini_options]` block with (the Starlette `filterwarnings` entry is removed — we no longer use `starlette.testclient`):

```toml
[tool.pytest.ini_options]
testpaths = ["lib/db/tests", "services/api/tests"]
addopts = "--import-mode=importlib"
asyncio_mode = "auto"
```

(b) Fix mypy for the new layout. The old `[[tool.mypy.overrides]] module = "tests.*"` block assumed a single root `tests` package; with two package-less test dirs, `mypy .` would error on a duplicate `conftest` module and the override would not match. **Delete** that overrides block:

```toml
[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false
```

and instead exclude the test directories from the strict type-check by extending the existing `[tool.mypy] exclude` list to:

```toml
exclude = ["\\.venv", "frontend", "build", "dist", "lib/db/lib_db/generated", "lib/db/tests", "services/api/tests"]
```

(Tests stay covered by pytest + ruff; mypy stays strict on source. This sidesteps the package-less-`conftest` collision cleanly.)

- [ ] **Step 6: Run the full suite to verify the move is green**

Run: `uv run pytest -q`
Expected: PASS — `test_data_layer_roundtrip`, `test_idempotent_creates` (from `lib/db/tests`) and `test_health_returns_ok` (from `services/api/tests`) all pass. No collection errors.

- [ ] **Step 7: Lint + commit**

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy .
git add -A
git commit -m "refactor(tests): co-locate tests per package, standardize on httpx"
```

---

### Task 2: Parameterize sentiment bucket + add GetToolBySlug

**Files:**
- Modify: `sql/queries/analysis.sql`, `sql/queries/tools.sql`, `lib/db/tests/test_smoke.py`
- Regenerate: `lib/db/lib_db/generated/queries.py`
- Test: `lib/db/tests/test_smoke.py`

- [ ] **Step 1: Write failing data-layer tests** — append to `lib/db/tests/test_smoke.py`

```python
async def test_sentiment_week_bucket_is_weighted(conn):
    """Two posts (0.9, 0.7) on one day + one post (0.3) on another day in the
    SAME ISO week must average to the weighted mean over all 3 rows
    (1.9/3 ≈ 0.6333), NOT the mean-of-day-means (0.55)."""
    suffix = uuid.uuid4().hex[:8]
    slug = f"weektool-{suffix}"
    cur = await conn.execute(
        "INSERT INTO tools (slug, display_name) VALUES (%s, %s) RETURNING id",
        (slug, "Week Tool"),
    )
    row = await cur.fetchone()
    assert row is not None
    tool_id = row[0]
    try:
        # 2026-05-18 is a Monday; 05-18 and 05-20 are the same ISO week.
        for i, (day, score) in enumerate(
            [(18, 0.9), (18, 0.7), (20, 0.3)]
        ):
            post = await queries.create_post(
                conn,
                source=f"wk-{suffix}",
                source_id=f"wk-{suffix}-{i}",
                content="x",
                author=None,
                url=None,
                published_at=dt.datetime(2026, 5, day, 12, tzinfo=dt.UTC),
                metadata={},
            )
            assert post is not None
            mention = await queries.create_mention(
                conn, post_id=post.id, tool_id=tool_id
            )
            assert mention is not None
            res = await queries.create_analysis_result(
                conn,
                mention_id=mention.id,
                model_name="test-model",
                model_version=None,
                score=score,
                label="positive",
                raw_output=None,
            )
            assert res is not None

        start = dt.datetime(2026, 5, 1, tzinfo=dt.UTC)
        end = dt.datetime(2026, 6, 1, tzinfo=dt.UTC)
        buckets = await queries.get_sentiment_by_tool_bucket(
            conn, slug=slug, bucket="week", published_at_1=start, published_at_2=end
        )
        assert len(buckets) == 1
        assert buckets[0].n == 3
        avg = buckets[0].avg_score
        assert avg is not None
        assert float(avg) == pytest.approx(1.9 / 3)
    finally:
        await conn.execute("DELETE FROM posts WHERE source = %s", (f"wk-{suffix}",))
        await conn.execute("DELETE FROM tools WHERE id = %s", (tool_id,))


async def test_get_tool_by_slug(conn):
    suffix = uuid.uuid4().hex[:8]
    slug = f"slugtool-{suffix}"
    cur = await conn.execute(
        "INSERT INTO tools (slug, display_name) VALUES (%s, %s) RETURNING id",
        (slug, "Slug Tool"),
    )
    row = await cur.fetchone()
    assert row is not None
    tool_id = row[0]
    try:
        found = await queries.get_tool_by_slug(conn, slug=slug)
        assert found is not None
        assert found.slug == slug
        missing = await queries.get_tool_by_slug(conn, slug="does-not-exist-xyz")
        assert missing is None
    finally:
        await conn.execute("DELETE FROM tools WHERE id = %s", (tool_id,))
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest lib/db/tests/test_smoke.py -q`
Expected: FAIL — `get_sentiment_by_tool_bucket()` raises `TypeError` (unexpected keyword `bucket`) and `queries.get_tool_by_slug` raises `AttributeError`.

- [ ] **Step 3: Parameterize the bucket** in `sql/queries/analysis.sql`

Find the `GetSentimentByToolBucket` query and replace the hard-coded `'day'` in the `date_trunc` call with the `%(bucket)s` parameter. The select expression becomes:

```sql
    date_trunc(
        %(bucket)s, p.published_at AT TIME ZONE 'UTC'
    ) AT TIME ZONE 'UTC' AS bucket,
```

Leave the rest of the query (joins, `WHERE t.slug = %(slug)s AND p.published_at >= %(published_at_1)s AND p.published_at < %(published_at_2)s`, `GROUP BY`) unchanged.

- [ ] **Step 4: Add `GetToolBySlug`** to `sql/queries/tools.sql`

```sql
-- @name GetToolBySlug
-- @returns one
SELECT id, slug, display_name, aliases, created_at
FROM tools
WHERE slug = %(slug)s;
```

- [ ] **Step 5: Regenerate the typed query layer**

Run: `./scripts/codegen.sh`
Expected: "Codegen complete -> lib/db/lib_db/generated/queries.py". The file now has a `bucket` param on `get_sentiment_by_tool_bucket` and a new `get_tool_by_slug`.

- [ ] **Step 6: Fix the existing smoke test call** in `lib/db/tests/test_smoke.py`

In `test_data_layer_roundtrip`, the existing `get_sentiment_by_tool_bucket(...)` call now needs the `bucket` argument. Update it:

```python
        buckets = await queries.get_sentiment_by_tool_bucket(
            conn, slug=slug, bucket="day", published_at_1=start, published_at_2=end
        )
```

- [ ] **Step 7: Run to verify pass**

Run: `uv run pytest lib/db/tests -q`
Expected: PASS — all data-layer tests including the two new ones.

- [ ] **Step 8: Lint + commit**

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy .
git add -A
git commit -m "feat(db): parameterize sentiment bucket granularity + add GetToolBySlug"
```

---

### Task 3: Pure period/bucket parsing (`periods.py`)

**Files:**
- Create: `services/api/api/periods.py`
- Test: `services/api/tests/test_periods.py`

- [ ] **Step 1: Write failing unit tests** — `services/api/tests/test_periods.py`

```python
import datetime as dt

import pytest

from api.periods import BUCKETS, parse_period, validate_bucket


def test_parse_period_days() -> None:
    assert parse_period("30d") == dt.timedelta(days=30)


def test_parse_period_weeks() -> None:
    assert parse_period("2w") == dt.timedelta(weeks=2)


@pytest.mark.parametrize("bad", ["invalid", "30", "d", "-5d", "30m", "1.5d", ""])
def test_parse_period_rejects(bad: str) -> None:
    with pytest.raises(ValueError):
        parse_period(bad)


def test_validate_bucket_ok() -> None:
    assert validate_bucket("week") == "week"
    assert BUCKETS == {"day", "week", "month"}


@pytest.mark.parametrize("bad", ["fortnight", "year", "Day", ""])
def test_validate_bucket_rejects(bad: str) -> None:
    with pytest.raises(ValueError):
        validate_bucket(bad)
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest services/api/tests/test_periods.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'api.periods'`.

- [ ] **Step 3: Implement `services/api/api/periods.py`**

```python
"""Pure parsing/validation for the sentiment endpoint's query params.

No HTTP, no DB — so it is unit-testable in isolation. Callers translate the
ValueErrors raised here into HTTP 422 at the FastAPI boundary.
"""

import datetime as dt
import re

BUCKETS = {"day", "week", "month"}

_PERIOD_RE = re.compile(r"^(\d+)([dw])$")
_UNIT = {"d": "days", "w": "weeks"}


def parse_period(period: str) -> dt.timedelta:
    """Parse a window length like ``"30d"`` or ``"2w"`` into a timedelta.

    Grammar: ``<positive int><d|w>``. Raises ValueError on anything else.
    """
    match = _PERIOD_RE.match(period)
    if match is None:
        raise ValueError(f"invalid period: {period!r} (expected e.g. '30d' or '2w')")
    value = int(match.group(1))
    if value <= 0:
        raise ValueError(f"invalid period: {period!r} (must be positive)")
    return dt.timedelta(**{_UNIT[match.group(2)]: value})


def validate_bucket(bucket: str) -> str:
    """Return ``bucket`` if it is a supported granularity, else raise ValueError."""
    if bucket not in BUCKETS:
        raise ValueError(
            f"invalid bucket: {bucket!r} (expected one of {sorted(BUCKETS)})"
        )
    return bucket
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest services/api/tests/test_periods.py -q`
Expected: PASS (all parametrized cases).

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy .
git add services/api/api/periods.py services/api/tests/test_periods.py
git commit -m "feat(api): pure period/bucket parsing"
```

---

### Task 4: Pydantic response models (`models.py`)

**Files:**
- Create: `services/api/api/models.py`
- Test: `services/api/tests/test_models.py`

- [ ] **Step 1: Write failing contract test** — `services/api/tests/test_models.py`

```python
import datetime as dt

from api.models import SentimentPoint, SentimentSeries, Tool


def test_tool_fields() -> None:
    t = Tool(slug="cursor", display_name="Cursor", aliases=["cursor", "cursor ai"])
    assert t.model_dump() == {
        "slug": "cursor",
        "display_name": "Cursor",
        "aliases": ["cursor", "cursor ai"],
    }


def test_sentiment_series_field_names() -> None:
    point = SentimentPoint(
        bucket_start=dt.datetime(2026, 5, 18, tzinfo=dt.UTC), n=3, avg_score=0.63
    )
    series = SentimentSeries(
        tool="cursor",
        period="30d",
        bucket="week",
        start=dt.datetime(2026, 5, 16, tzinfo=dt.UTC),
        end=dt.datetime(2026, 6, 15, tzinfo=dt.UTC),
        series=[point],
    )
    dumped = series.model_dump()
    assert set(dumped) == {"tool", "period", "bucket", "start", "end", "series"}
    assert set(dumped["series"][0]) == {"bucket_start", "n", "avg_score"}
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest services/api/tests/test_models.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'api.models'`.

- [ ] **Step 3: Implement `services/api/api/models.py`**

```python
"""Authored public response contract — deliberately decoupled from the
generated DB row dataclasses (internal ids/timestamps are not exposed)."""

import datetime as dt

from pydantic import BaseModel


class Tool(BaseModel):
    slug: str
    display_name: str
    aliases: list[str]


class SentimentPoint(BaseModel):
    bucket_start: dt.datetime
    n: int
    avg_score: float


class SentimentSeries(BaseModel):
    tool: str
    period: str
    bucket: str
    start: dt.datetime
    end: dt.datetime
    series: list[SentimentPoint]
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest services/api/tests/test_models.py -q`
Expected: PASS.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy .
git add services/api/api/models.py services/api/tests/test_models.py
git commit -m "feat(api): authored Pydantic response models"
```

---

### Task 5: Integration test harness + DB/clock dependencies

**Files:**
- Create: `services/api/api/dependencies.py`, `services/api/tests/conftest.py`, `services/api/tests/test_harness.py`

- [ ] **Step 1: Implement `services/api/api/dependencies.py`** (the connection + clock providers; `resolve_window` is added in Task 7)

```python
"""FastAPI dependencies: a pooled DB connection and an injectable clock.

`get_now` is injectable so tests can pin "now" via app.dependency_overrides,
keeping time-based assertions deterministic without widening the public API.
"""

import datetime as dt
from collections.abc import AsyncIterator
from typing import Any

from fastapi import Request
from psycopg import AsyncConnection


async def get_conn(request: Request) -> AsyncIterator[AsyncConnection[Any]]:
    """Yield one connection from the app's pool for the duration of a request."""
    async with request.app.state.pool.connection() as conn:
        yield conn


def get_now() -> dt.datetime:
    """Current UTC time. Overridden in tests for deterministic windows."""
    return dt.datetime.now(dt.UTC)
```

- [ ] **Step 2: Implement `services/api/tests/conftest.py`** (harness fixtures)

```python
"""Integration harness: real app over httpx, a self-contained data fixture,
committed inserts with surgical cleanup, and a pinned clock."""

import dataclasses
import datetime as dt
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from lib_db import create_pool, queries

from api.dependencies import get_now
from api.main import app

DSN = os.environ.get(
    "DATABASE_URL",
    "postgres://vibecheck:vibecheck@127.0.0.1:5432/vibecheck?sslmode=disable",
)

# 2026-06-15 is a Monday; the 30d default window is [2026-05-16, 2026-06-15).
FIXED_NOW = dt.datetime(2026, 6, 15, 12, 0, tzinfo=dt.UTC)


@dataclasses.dataclass(frozen=True)
class Seed:
    slug: str
    source: str
    tool_id: uuid.UUID


@pytest.fixture
async def db_pool():
    pool = create_pool(DSN)
    await pool.open()
    yield pool
    await pool.close()


@pytest.fixture
async def client(db_pool):
    app.state.pool = db_pool
    app.dependency_overrides[get_now] = lambda: FIXED_NOW
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
async def seeded(db_pool):
    """Insert a tool + posts/mentions/analysis with known values.

    Posts (all 12:00Z): 05-18 (0.9), 05-18 (0.7), 05-20 (0.3) — same ISO week,
    unequal daily counts; 05-27 (0.1) — next ISO week. All inside the default
    30d window ending at FIXED_NOW.
    """
    suffix = uuid.uuid4().hex[:8]
    slug = f"senttool-{suffix}"
    source = f"test-{suffix}"
    async with db_pool.connection() as conn:
        cur = await conn.execute(
            "INSERT INTO tools (slug, display_name) VALUES (%s, %s) RETURNING id",
            (slug, "Sentiment Test Tool"),
        )
        row = await cur.fetchone()
        assert row is not None
        tool_id = row[0]
        rows = [
            (dt.datetime(2026, 5, 18, 12, tzinfo=dt.UTC), 0.9),
            (dt.datetime(2026, 5, 18, 12, tzinfo=dt.UTC), 0.7),
            (dt.datetime(2026, 5, 20, 12, tzinfo=dt.UTC), 0.3),
            (dt.datetime(2026, 5, 27, 12, tzinfo=dt.UTC), 0.1),
        ]
        for i, (published_at, score) in enumerate(rows):
            post = await queries.create_post(
                conn,
                source=source,
                source_id=f"{source}-{i}",
                content="x",
                author=None,
                url=None,
                published_at=published_at,
                metadata={},
            )
            assert post is not None
            mention = await queries.create_mention(
                conn, post_id=post.id, tool_id=tool_id
            )
            assert mention is not None
            res = await queries.create_analysis_result(
                conn,
                mention_id=mention.id,
                model_name="test-model",
                model_version=None,
                score=score,
                label="positive",
                raw_output=None,
            )
            assert res is not None

    yield Seed(slug=slug, source=source, tool_id=tool_id)

    async with db_pool.connection() as conn:
        await conn.execute("DELETE FROM posts WHERE source = %s", (source,))
        await conn.execute("DELETE FROM tools WHERE id = %s", (tool_id,))
```

- [ ] **Step 3: Write the harness self-test** — `services/api/tests/test_harness.py`

```python
from lib_db import queries


async def test_seed_inserts_and_is_queryable(db_pool, seeded) -> None:
    async with db_pool.connection() as conn:
        tool = await queries.get_tool_by_slug(conn, slug=seeded.slug)
        assert tool is not None
        cur = await conn.execute(
            "SELECT count(*) FROM posts WHERE source = %s", (seeded.source,)
        )
        row = await cur.fetchone()
        assert row is not None
        assert row[0] == 4
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest services/api/tests/test_harness.py -q`
Expected: PASS — the seed inserts a tool + 4 posts, both queryable through the pool.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy .
git add services/api/api/dependencies.py services/api/tests/conftest.py services/api/tests/test_harness.py
git commit -m "test(api): integration harness with seeded data + injectable clock"
```

---

### Task 6: `GET /api/v1/tools`

**Files:**
- Create: `services/api/api/routes.py`
- Modify: `services/api/api/main.py`
- Test: `services/api/tests/test_tools.py`

- [ ] **Step 1: Write failing integration test** — `services/api/tests/test_tools.py`

```python
async def test_list_tools_returns_seeded_tool(client, seeded) -> None:
    response = await client.get("/api/v1/tools")
    assert response.status_code == 200
    tools = response.json()
    match = [t for t in tools if t["slug"] == seeded.slug]
    assert len(match) == 1
    tool = match[0]
    assert set(tool) == {"slug", "display_name", "aliases"}  # no id/created_at
    assert tool["display_name"] == "Sentiment Test Tool"
    assert tool["aliases"] == []
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest services/api/tests/test_tools.py -q`
Expected: FAIL — 404 (route not registered).

- [ ] **Step 3: Create `services/api/api/routes.py`**

```python
"""Versioned dashboard read endpoints."""

from typing import Any

from fastapi import APIRouter, Depends
from lib_db import queries
from psycopg import AsyncConnection

from api.dependencies import get_conn
from api.models import Tool

router = APIRouter(prefix="/api/v1")


@router.get("/tools", response_model=list[Tool])
async def list_tools(
    conn: AsyncConnection[Any] = Depends(get_conn),
) -> list[Tool]:
    rows = await queries.list_tools(conn)
    return [
        Tool(slug=r.slug, display_name=r.display_name, aliases=r.aliases)
        for r in rows
    ]
```

- [ ] **Step 4: Wire the router in `services/api/api/main.py`**

Add the import near the other imports and `app.include_router(router)` after `app = FastAPI(...)`:

```python
from api.routes import router

# ... after: app = FastAPI(title="Vibecheck API", lifespan=lifespan)
app.include_router(router)
```

- [ ] **Step 5: Run to verify pass**

Run: `uv run pytest services/api/tests/test_tools.py -q`
Expected: PASS.

- [ ] **Step 6: Lint + commit**

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy .
git add services/api/api/routes.py services/api/api/main.py services/api/tests/test_tools.py
git commit -m "feat(api): GET /api/v1/tools"
```

---

### Task 7: `GET /api/v1/sentiment/{tool}`

**Files:**
- Modify: `services/api/api/dependencies.py` (add `resolve_window`), `services/api/api/routes.py`
- Test: `services/api/tests/test_sentiment.py`

- [ ] **Step 1: Write failing integration tests** — `services/api/tests/test_sentiment.py`

```python
import datetime as dt


async def test_sentiment_week_buckets_are_weighted(client, seeded) -> None:
    response = await client.get(
        f"/api/v1/sentiment/{seeded.slug}", params={"period": "30d", "bucket": "week"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tool"] == seeded.slug
    assert body["period"] == "30d"
    assert body["bucket"] == "week"
    by_start = {
        dt.datetime.fromisoformat(p["bucket_start"]).date(): p for p in body["series"]
    }
    assert set(by_start) == {dt.date(2026, 5, 18), dt.date(2026, 5, 25)}
    wk1 = by_start[dt.date(2026, 5, 18)]
    assert wk1["n"] == 3
    assert wk1["avg_score"] == pytest.approx(1.9 / 3)  # weighted, not 0.55
    wk2 = by_start[dt.date(2026, 5, 25)]
    assert wk2["n"] == 1
    assert wk2["avg_score"] == pytest.approx(0.1)


async def test_sentiment_day_buckets(client, seeded) -> None:
    response = await client.get(
        f"/api/v1/sentiment/{seeded.slug}", params={"bucket": "day"}
    )
    assert response.status_code == 200
    by_start = {
        dt.datetime.fromisoformat(p["bucket_start"]).date(): p
        for p in response.json()["series"]
    }
    assert by_start[dt.date(2026, 5, 18)]["n"] == 2
    assert by_start[dt.date(2026, 5, 18)]["avg_score"] == pytest.approx(0.8)
    assert by_start[dt.date(2026, 5, 20)]["n"] == 1


async def test_sentiment_unknown_tool_404(client) -> None:
    response = await client.get("/api/v1/sentiment/no-such-tool")
    assert response.status_code == 404


async def test_sentiment_invalid_period_422(client, seeded) -> None:
    response = await client.get(
        f"/api/v1/sentiment/{seeded.slug}", params={"period": "invalid"}
    )
    assert response.status_code == 422


async def test_sentiment_invalid_bucket_422(client, seeded) -> None:
    response = await client.get(
        f"/api/v1/sentiment/{seeded.slug}", params={"bucket": "fortnight"}
    )
    assert response.status_code == 422


async def test_sentiment_empty_window_is_200_empty(client, seeded) -> None:
    # 7d window ends at FIXED_NOW (06-15); all seeded posts are >= 19 days old.
    response = await client.get(
        f"/api/v1/sentiment/{seeded.slug}", params={"period": "7d"}
    )
    assert response.status_code == 200
    assert response.json()["series"] == []
```

Add `import pytest` at the top of the file (used by `pytest.approx`).

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest services/api/tests/test_sentiment.py -q`
Expected: FAIL — 404 for all (route not registered).

- [ ] **Step 3: Add `resolve_window` to `services/api/api/dependencies.py`**

Append (and extend the imports: add `from dataclasses import dataclass`, `from fastapi import Depends, HTTPException, Request`, and `from api.periods import parse_period, validate_bucket`):

```python
@dataclass(frozen=True)
class ResolvedWindow:
    period: str
    bucket: str
    start: dt.datetime
    end: dt.datetime


def resolve_window(
    period: str = "30d",
    bucket: str = "day",
    now: dt.datetime = Depends(get_now),
) -> ResolvedWindow:
    """Validate query params and compute the [start, end) UTC window.

    Invalid period/bucket -> 422. The window ends at the injected `now`.
    """
    try:
        delta = parse_period(period)
        validate_bucket(bucket)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ResolvedWindow(period=period, bucket=bucket, start=now - delta, end=now)
```

- [ ] **Step 4: Add the endpoint to `services/api/api/routes.py`**

Extend imports — `from fastapi import APIRouter, Depends, HTTPException`, add `from api.dependencies import get_conn, resolve_window, ResolvedWindow`, and `from api.models import SentimentPoint, SentimentSeries, Tool`. Append:

```python
@router.get("/sentiment/{tool}", response_model=SentimentSeries)
async def tool_sentiment(
    tool: str,
    window: ResolvedWindow = Depends(resolve_window),
    conn: AsyncConnection[Any] = Depends(get_conn),
) -> SentimentSeries:
    if await queries.get_tool_by_slug(conn, slug=tool) is None:
        raise HTTPException(status_code=404, detail="tool not found")
    rows = await queries.get_sentiment_by_tool_bucket(
        conn,
        slug=tool,
        bucket=window.bucket,
        published_at_1=window.start,
        published_at_2=window.end,
    )
    points: list[SentimentPoint] = []
    for r in rows:
        assert r.avg_score is not None  # non-empty bucket -> avg is non-null
        points.append(SentimentPoint(bucket_start=r.bucket, n=r.n, avg_score=r.avg_score))
    return SentimentSeries(
        tool=tool,
        period=window.period,
        bucket=window.bucket,
        start=window.start,
        end=window.end,
        series=points,
    )
```

- [ ] **Step 5: Run to verify pass**

Run: `uv run pytest services/api/tests/test_sentiment.py -q`
Expected: PASS — all six tests.

- [ ] **Step 6: Run the full suite + lint + commit**

```bash
uv run pytest -q && uv run ruff check . && uv run ruff format --check . && uv run mypy .
git add services/api/api/dependencies.py services/api/api/routes.py services/api/tests/test_sentiment.py
git commit -m "feat(api): GET /api/v1/sentiment/{tool}"
```

---

### Task 8: OpenAPI spec artifact + freshness gate

**Files:**
- Create: `scripts/gen-openapi.sh`, `services/api/openapi.json`
- Test: `services/api/tests/test_openapi.py`
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Write failing verification test** — `services/api/tests/test_openapi.py`

```python
from api.main import app


def test_openapi_exposes_expected_contract() -> None:
    spec = app.openapi()
    assert "/api/v1/tools" in spec["paths"]
    assert "/api/v1/sentiment/{tool}" in spec["paths"]
    schemas = spec["components"]["schemas"]
    assert {"Tool", "SentimentSeries", "SentimentPoint"} <= set(schemas)
```

- [ ] **Step 2: Run to verify pass** (this asserts current behavior — it should already pass; it is a regression guard, not test-first scaffolding)

Run: `uv run pytest services/api/tests/test_openapi.py -q`
Expected: PASS. (If it fails, the routes/models from Tasks 6–7 are wrong — fix those.)

- [ ] **Step 3: Create `scripts/gen-openapi.sh`** (deterministic output for the freshness diff)

```bash
#!/usr/bin/env bash
# Regenerate the committed OpenAPI spec from the live FastAPI app.
set -euo pipefail
cd "$(dirname "$0")/.."
uv run python -c "
import json
from api.main import app
with open('services/api/openapi.json', 'w') as f:
    json.dump(app.openapi(), f, indent=2, sort_keys=True)
    f.write('\n')
"
echo "Wrote services/api/openapi.json"
```

- [ ] **Step 4: Generate and commit the spec**

```bash
chmod +x scripts/gen-openapi.sh
./scripts/gen-openapi.sh
```
Expected: `services/api/openapi.json` created. Sanity-check it contains `"/api/v1/tools"`.

- [ ] **Step 5: Add the freshness gate to `.github/workflows/ci.yml`**

After the existing "Codegen freshness" step, add a sibling step (same indentation):

```yaml
      - name: OpenAPI freshness
        run: |
          ./scripts/gen-openapi.sh
          git diff --exit-code -- services/api/openapi.json
          test -z "$(git status --porcelain -- services/api/openapi.json)"
```

- [ ] **Step 6: Run the suite + lint + commit**

```bash
uv run pytest -q && uv run ruff check . && uv run mypy .
git add scripts/gen-openapi.sh services/api/openapi.json services/api/tests/test_openapi.py .github/workflows/ci.yml
git commit -m "feat(api): committed OpenAPI spec + CI freshness gate"
```

---

### Task 9: Compose demo seed + manual verification (checkpoint)

**Files:**
- Create: `sql/seeds/demo_facts.sql`

This task is a manual demo checkpoint (no automated tests). It proves the containerized API serves real data.

- [ ] **Step 1: Create `sql/seeds/demo_facts.sql`** (dev-only; never applied in CI)

```sql
-- DEV-ONLY demo facts for manual API verification. NOT applied in CI.
-- Idempotent on posts(source, source_id). Targets the seeded 'cursor' tool.
WITH t AS (SELECT id FROM tools WHERE slug = 'cursor'),
ins_post AS (
    INSERT INTO posts (source, source_id, content, author, url, published_at, metadata)
    VALUES
        ('demo', 'demo-1', 'Cursor is great', 'alice', NULL, now() - interval '2 days', '{}'),
        ('demo', 'demo-2', 'Cursor crashed today', 'bob', NULL, now() - interval '1 day', '{}')
    ON CONFLICT (source, source_id) DO UPDATE SET source = excluded.source
    RETURNING id
),
ins_mention AS (
    INSERT INTO mentions (post_id, tool_id)
    SELECT p.id, t.id FROM ins_post p, t
    ON CONFLICT (post_id, tool_id) DO UPDATE SET post_id = excluded.post_id
    RETURNING id, post_id
)
INSERT INTO analysis_results (mention_id, model_name, score, label)
SELECT m.id, 'demo-model',
       CASE WHEN p.source_id = 'demo-1' THEN 0.9 ELSE 0.2 END,
       CASE WHEN p.source_id = 'demo-1' THEN 'positive' ELSE 'negative' END
FROM ins_mention m JOIN posts p ON p.id = m.post_id
ON CONFLICT (mention_id, model_name, model_version) DO UPDATE SET model_name = excluded.model_name;
```

- [ ] **Step 2: Bring up the stack and seed**

```bash
docker compose up -d --build postgres api
# ensure schema + tools are present, then load demo facts:
psql "$DATABASE_URL" -f sql/schema.sql
psql "$DATABASE_URL" -f sql/seeds/tools.sql
psql "$DATABASE_URL" -f sql/seeds/demo_facts.sql
```

Note: the compose `postgres` has no host port mapping by default; either run `psql` from inside the container (`docker compose exec -T postgres psql -U vibecheck -d vibecheck -f -` < file) or use the host DB that the API points at. Use whichever your `DATABASE_URL` targets.

- [ ] **Step 3: Hit the endpoints and verify**

```bash
curl -s localhost:8000/api/v1/tools | head
curl -s "localhost:8000/api/v1/sentiment/cursor?period=30d&bucket=day"
curl -s "localhost:8000/api/v1/sentiment/cursor?period=invalid" -o /dev/null -w "%{http_code}\n"   # 422
curl -s "localhost:8000/api/v1/sentiment/no-such" -o /dev/null -w "%{http_code}\n"                  # 404
```
Expected: `/tools` lists the registry; `/sentiment/cursor` returns a non-empty `series` with the demo averages; invalid period → 422; unknown tool → 404.

- [ ] **Step 4: Tear down + commit the demo seed**

```bash
docker compose down
git add sql/seeds/demo_facts.sql
git commit -m "chore(api): dev-only demo facts seed for manual verification"
```

- [ ] **Step 5: Checkpoint reached** — API serves correct data from Postgres, integration-tested, OpenAPI spec committed and gated. Ready for the Phase 3 frontend.

---

## Self-review notes

- **Spec coverage:** tools endpoint (T6), sentiment endpoint incl. week/day/unknown/invalid-period/invalid-bucket/empty (T7), SQL bucket param + GetToolBySlug (T2), authored Pydantic models (T4), period/bucket parsing (T3), injectable-now determinism (T5), per-package test move + import-mode (T1), OpenAPI artifact + verification + freshness gate, TS-gen deferred (T8), compose already wired in 2.1 + demo verify (T9). Posts endpoint intentionally absent (deferred).
- **Determinism:** `FIXED_NOW = 2026-06-15` (Monday); seeded posts fall in ISO weeks starting 2026-05-18 and 2026-05-25; the unequal-count week (3 rows: 0.9/0.7/0.3) pins the weighted mean 1.9/3 ≈ 0.633 ≠ naive 0.55.
- **Type consistency:** `ResolvedWindow(period, bucket, start, end)`; `get_sentiment_by_tool_bucket(slug, bucket, published_at_1, published_at_2)`; `SentimentPoint(bucket_start, n, avg_score)`; `SentimentSeries(tool, period, bucket, start, end, series)` — used identically across tasks.
