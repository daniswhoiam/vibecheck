import datetime as dt
import os
import uuid

import pytest
from lib_db import create_pool, queries

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


async def test_data_layer_roundtrip(conn):
    suffix = uuid.uuid4().hex[:8]
    slug = f"test-tool-{suffix}"
    source_id = f"sid-{suffix}"

    # Setup: a tool (there is no CreateTool query - use raw SQL).
    cur = await conn.execute(
        "INSERT INTO tools (slug, display_name) VALUES (%s, %s) RETURNING id",
        (slug, "Test Tool"),
    )
    tool_row = await cur.fetchone()
    assert tool_row is not None
    tool_id = tool_row[0]

    try:
        published = dt.datetime(2026, 5, 1, 12, 0, tzinfo=dt.UTC)
        post = await queries.create_post(
            conn,
            source="test",
            source_id=source_id,
            content="Cursor is great",
            author="alice",
            url="https://example.com/p",
            published_at=published,
            metadata={"k": "v"},
        )
        assert post is not None

        mention = await queries.create_mention(conn, post_id=post.id, tool_id=tool_id)
        assert mention is not None

        analysis = await queries.create_analysis_result(
            conn,
            mention_id=mention.id,
            model_name="twitter-roberta-base",
            model_version=None,
            score=0.82,
            label="positive",
            raw_output={"logits": [0.1, 0.9]},
        )
        assert analysis is not None

        start = dt.datetime(2026, 5, 1, tzinfo=dt.UTC)
        end = dt.datetime(2026, 5, 2, tzinfo=dt.UTC)

        buckets = await queries.get_sentiment_by_tool_bucket(
            conn, slug=slug, published_at_1=start, published_at_2=end
        )
        assert len(buckets) == 1
        assert buckets[0].tool_slug == slug
        assert buckets[0].n == 1
        avg_score = buckets[0].avg_score
        assert avg_score is not None  # avg() is NULL-able; narrow before float()
        assert float(avg_score) == pytest.approx(0.82)

        posts = await queries.get_posts_by_tool_and_range(
            conn, slug=slug, published_at_1=start, published_at_2=end, limit_val=10
        )
        assert len(posts) == 1
        assert posts[0].metadata == {"k": "v"}  # jsonb round-trip

        tools = await queries.list_tools(conn)
        assert any(t.slug == slug for t in tools)
    finally:
        # Deleting the post cascades to its mention + analysis; then the tool
        # has no referencing mentions and can be removed.
        await conn.execute("DELETE FROM posts WHERE source_id = %s", (source_id,))
        await conn.execute("DELETE FROM tools WHERE id = %s", (tool_id,))
