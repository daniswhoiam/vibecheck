"""Cycle tests: stub fetchers and a recording publisher around the real
registry + dedup queries in Postgres."""

import datetime as dt
import uuid

from ingestion.pipeline import run_cycle
from ingestion.posts import FetchedPost
from lib_db import queries

LOOKBACK = dt.timedelta(hours=1)


def make_post(seed, *, source_id: str | None = None, content: str | None = None) -> FetchedPost:
    return FetchedPost(
        source=seed.source,
        source_id=source_id or uuid.uuid4().hex[:10],
        content=content if content is not None else f"{seed.display_name} is great",
        published_at=dt.datetime.now(dt.UTC),
    )


class RecordingPublisher:
    def __init__(self) -> None:
        self.published: list[tuple[FetchedPost, list[str]]] = []

    async def __call__(self, post: FetchedPost, tools) -> None:
        self.published.append((post, list(tools)))


def stub_fetcher(posts):
    calls = []

    async def fetch(tool_queries, since):
        calls.append((list(tool_queries), since))
        return list(posts)

    fetch.calls = calls
    return fetch


async def test_detected_post_is_published_with_slugs(db_pool, seed):
    post = make_post(seed)
    publish = RecordingPublisher()
    fetcher = stub_fetcher([post])

    stats = await run_cycle(db_pool, publish, [fetcher], lookback=LOOKBACK)

    assert publish.published == [(post, [seed.slug])]
    assert stats.published == 1
    # Fetchers are queried with registry display names (seeded one included).
    (queried, since), *_ = fetcher.calls
    assert seed.display_name in queried
    assert since.tzinfo is not None


async def test_post_already_in_db_is_not_republished(db_pool, seed):
    post = make_post(seed)
    async with db_pool.connection() as conn:
        await queries.create_post(
            conn,
            source=post.source,
            source_id=post.source_id,
            content=post.content,
            author=None,
            url=None,
            published_at=post.published_at,
            metadata={},
        )
    publish = RecordingPublisher()

    stats = await run_cycle(db_pool, publish, [stub_fetcher([post])], lookback=LOOKBACK)

    assert publish.published == []
    assert stats.skipped_existing == 1


async def test_post_without_mention_is_dropped(db_pool, seed):
    post = make_post(seed, content="nothing relevant in here")
    publish = RecordingPublisher()

    stats = await run_cycle(db_pool, publish, [stub_fetcher([post])], lookback=LOOKBACK)

    assert publish.published == []
    assert stats.skipped_no_mention == 1


async def test_failing_fetcher_does_not_block_others(db_pool, seed):
    async def broken(tool_queries, since):
        raise RuntimeError("source is down")

    post = make_post(seed)
    publish = RecordingPublisher()

    stats = await run_cycle(db_pool, publish, [broken, stub_fetcher([post])], lookback=LOOKBACK)

    assert [p.source_id for p, _ in publish.published] == [post.source_id]
    assert stats.published == 1


async def test_same_post_from_two_fetchers_published_once(db_pool, seed):
    post = make_post(seed)
    publish = RecordingPublisher()

    stats = await run_cycle(
        db_pool, publish, [stub_fetcher([post]), stub_fetcher([post])], lookback=LOOKBACK
    )

    assert stats.published == 1
    assert stats.fetched == 1
