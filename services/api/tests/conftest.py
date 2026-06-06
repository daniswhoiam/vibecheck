"""Integration harness: real app over httpx, a self-contained data fixture,
committed inserts with surgical cleanup, and a pinned clock."""

import dataclasses
import datetime as dt
import os
import uuid

import pytest
from api.dependencies import get_now
from api.main import app
from httpx import ASGITransport, AsyncClient
from lib_db import create_pool, queries

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
    del app.state.pool


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
            mention = await queries.create_mention(conn, post_id=post.id, tool_id=tool_id)
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
