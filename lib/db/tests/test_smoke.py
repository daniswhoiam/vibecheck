import datetime as dt
import uuid

import pytest
from lib_db import queries


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


async def test_idempotent_creates(conn):
    """Re-running ingest/mention/analysis on the same natural key returns the
    existing row (never None, never a UniqueViolation) and does NOT overwrite
    the stored data — the create queries use a no-op DO UPDATE for that."""
    suffix = uuid.uuid4().hex[:8]
    slug = f"test-tool-{suffix}"
    source_id = f"sid-{suffix}"

    cur = await conn.execute(
        "INSERT INTO tools (slug, display_name) VALUES (%s, %s) RETURNING id",
        (slug, "Test Tool"),
    )
    tool_row = await cur.fetchone()
    assert tool_row is not None
    tool_id = tool_row[0]

    try:
        published = dt.datetime(2026, 5, 1, 12, 0, tzinfo=dt.UTC)
        first = await queries.create_post(
            conn,
            source="test",
            source_id=source_id,
            content="original content",
            author="alice",
            url="https://example.com/p",
            published_at=published,
            metadata={"k": "v"},
        )
        assert first is not None

        # Duplicate ingest with DIFFERENT content: returns the same row id and
        # leaves the originally-stored content untouched (no-op DO UPDATE).
        dup = await queries.create_post(
            conn,
            source="test",
            source_id=source_id,
            content="changed content",
            author="bob",
            url="https://example.com/other",
            published_at=published,
            metadata={"changed": True},
        )
        assert dup is not None
        assert dup.id == first.id
        assert dup.content == "original content"
        assert dup.metadata == {"k": "v"}

        # Duplicate mention on (post_id, tool_id): same row, no error.
        m1 = await queries.create_mention(conn, post_id=first.id, tool_id=tool_id)
        m2 = await queries.create_mention(conn, post_id=first.id, tool_id=tool_id)
        assert m1 is not None and m2 is not None
        assert m1.id == m2.id

        # Identical analysis rerun: same row, score/label/analyzed_at preserved
        # even though the rerun passes a different score.
        a1 = await queries.create_analysis_result(
            conn,
            mention_id=m1.id,
            model_name="twitter-roberta-base",
            model_version=None,
            score=0.82,
            label="positive",
            raw_output={"logits": [0.1, 0.9]},
        )
        assert a1 is not None
        a2 = await queries.create_analysis_result(
            conn,
            mention_id=m1.id,
            model_name="twitter-roberta-base",
            model_version=None,
            score=0.10,
            label="negative",
            raw_output={"logits": [0.9, 0.1]},
        )
        assert a2 is not None
        assert a2.id == a1.id
        assert a2.score == pytest.approx(0.82)
        assert a2.label == "positive"
        assert a2.analyzed_at == a1.analyzed_at
    finally:
        await conn.execute("DELETE FROM posts WHERE source_id = %s", (source_id,))
        await conn.execute("DELETE FROM tools WHERE id = %s", (tool_id,))
