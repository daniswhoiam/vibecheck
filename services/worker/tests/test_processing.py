"""Integration tests for the post -> mention -> analysis processing chain.

Runs against real Postgres through the Scythe-generated functions; the model
is the deterministic stub from conftest. The consumer wraps each message in
one transaction, so tests do the same.
"""

import datetime as dt

import pytest
from worker.messages import PermanentError, PostMessage
from worker.processing import process_message

from .conftest import StubAnalyzer

PUBLISHED_AT = dt.datetime(2026, 6, 1, 12, 0, tzinfo=dt.UTC)


def make_message(seed, **overrides) -> PostMessage:
    defaults = {
        "source": seed.source,
        "source_id": f"{seed.source}-1",
        "content": "This tool is great",
        "published_at": PUBLISHED_AT,
        "tools": [seed.slug],
        "author": "alice",
        "url": "https://example.com/post/1",
        "metadata": {"channel": "test"},
    }
    return PostMessage(**{**defaults, **overrides})


async def fetch_rows(db_pool, source: str) -> list[tuple]:
    async with db_pool.connection() as conn:
        cur = await conn.execute(
            """
            SELECT p.source_id, p.content, t.slug,
                   a.model_name, a.model_version, a.score, a.label, a.raw_output
            FROM posts p
            JOIN mentions m ON m.post_id = p.id
            JOIN tools t ON t.id = m.tool_id
            JOIN analysis_results a ON a.mention_id = m.id
            WHERE p.source = %s
            ORDER BY p.source_id, t.slug
            """,
            (source,),
        )
        return await cur.fetchall()


async def test_message_lands_as_post_mention_and_analysis(db_pool, seed) -> None:
    msg = make_message(seed)
    async with db_pool.connection() as conn, conn.transaction():
        await process_message(conn, msg, StubAnalyzer())

    rows = await fetch_rows(db_pool, seed.source)
    assert rows == [
        (
            f"{seed.source}-1",
            "This tool is great",
            seed.slug,
            "stub-model",
            "stub-v1",
            0.9,
            "positive",
            {"negative": 0.05, "neutral": 0.05, "positive": 0.9},
        )
    ]


async def test_reprocessing_same_message_is_idempotent(db_pool, seed) -> None:
    msg = make_message(seed)
    for _ in range(2):
        async with db_pool.connection() as conn, conn.transaction():
            await process_message(conn, msg, StubAnalyzer())

    rows = await fetch_rows(db_pool, seed.source)
    assert len(rows) == 1


async def test_unknown_tool_slug_is_permanent_and_rolls_back(db_pool, seed) -> None:
    msg = make_message(seed, tools=["no-such-tool"])
    with pytest.raises(PermanentError):
        async with db_pool.connection() as conn, conn.transaction():
            await process_message(conn, msg, StubAnalyzer())

    # The transaction must roll back the post insert too: no partial writes.
    async with db_pool.connection() as conn:
        cur = await conn.execute("SELECT count(*) FROM posts WHERE source = %s", (seed.source,))
        row = await cur.fetchone()
        assert row is not None and row[0] == 0


async def test_one_mention_and_analysis_per_listed_tool(db_pool, seed) -> None:
    suffix = seed.slug.removeprefix("workertool-")
    other_slug = f"workertool2-{suffix}"
    async with db_pool.connection() as conn:
        await conn.execute(
            "INSERT INTO tools (slug, display_name) VALUES (%s, %s)",
            (other_slug, "Second Worker Test Tool"),
        )
    try:
        msg = make_message(seed, tools=[seed.slug, other_slug])
        async with db_pool.connection() as conn, conn.transaction():
            await process_message(conn, msg, StubAnalyzer())

        rows = await fetch_rows(db_pool, seed.source)
        # Set comparison: SQL slug ordering is collation-dependent (ICU treats
        # '-' as ignorable), so a list comparison would flake on the suffix.
        assert {r[2] for r in rows} == {seed.slug, other_slug}
        assert len(rows) == 2
    finally:
        async with db_pool.connection() as conn:
            await conn.execute("DELETE FROM posts WHERE source = %s", (seed.source,))
            await conn.execute("DELETE FROM tools WHERE slug = %s", (other_slug,))
