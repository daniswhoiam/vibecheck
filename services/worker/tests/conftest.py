"""Worker test harness: real Postgres, a uniquely-named seeded tool with
surgical cleanup, and a deterministic stub analyzer (the real model has its
own unit tests in test_sentiment.py)."""

import dataclasses
import os
import uuid

import pytest
from lib_db import create_pool
from worker.sentiment import SentimentResult

DSN = os.environ.get(
    "DATABASE_URL",
    "postgres://vibecheck:vibecheck@127.0.0.1:5432/vibecheck?sslmode=disable",
)


class StubAnalyzer:
    """Deterministic stand-in satisfying the SentimentAnalyzer interface."""

    model_name = "stub-model"
    model_version = "stub-v1"

    def analyze(self, text: str) -> SentimentResult:
        return SentimentResult(
            score=0.9,
            label="positive",
            raw={"negative": 0.05, "neutral": 0.05, "positive": 0.9},
        )


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
async def seed(db_pool):
    """A tool with a unique slug plus a unique post source for cleanup."""
    suffix = uuid.uuid4().hex[:8]
    slug = f"workertool-{suffix}"
    source = f"workertest-{suffix}"
    async with db_pool.connection() as conn:
        cur = await conn.execute(
            "INSERT INTO tools (slug, display_name) VALUES (%s, %s) RETURNING id",
            (slug, "Worker Test Tool"),
        )
        row = await cur.fetchone()
        assert row is not None
        tool_id = row[0]

    yield Seed(slug=slug, source=source, tool_id=tool_id)

    async with db_pool.connection() as conn:
        await conn.execute("DELETE FROM posts WHERE source = %s", (source,))
        await conn.execute("DELETE FROM tools WHERE id = %s", (tool_id,))
