"""Ingestion test harness: real Postgres with a uniquely-named seeded tool
(matcher input + dedup target) and surgical cleanup."""

import dataclasses
import os
import uuid

import pytest
from lib_db import create_pool

DSN = os.environ.get(
    "DATABASE_URL",
    "postgres://vibecheck:vibecheck@127.0.0.1:5432/vibecheck?sslmode=disable",
)


@dataclasses.dataclass(frozen=True)
class Seed:
    slug: str
    display_name: str
    source: str
    tool_id: uuid.UUID


@pytest.fixture
async def db_pool():
    pool = create_pool(DSN)
    await pool.open()
    yield pool
    await pool.close()


@pytest.fixture
async def seed(db_pool):
    """A tool whose display name is a unique nonsense word, so detection in
    test posts can never collide with real registry entries."""
    suffix = uuid.uuid4().hex[:8]
    slug = f"ingesttool-{suffix}"
    display_name = f"ingesttool{suffix}"
    source = f"ingesttest-{suffix}"
    async with db_pool.connection() as conn:
        cur = await conn.execute(
            "INSERT INTO tools (slug, display_name, aliases) VALUES (%s, %s, %s) RETURNING id",
            (slug, display_name, [display_name]),
        )
        row = await cur.fetchone()
        assert row is not None
        tool_id = row[0]

    yield Seed(slug=slug, display_name=display_name, source=source, tool_id=tool_id)

    async with db_pool.connection() as conn:
        await conn.execute("DELETE FROM posts WHERE source = %s", (source,))
        await conn.execute("DELETE FROM tools WHERE id = %s", (tool_id,))
