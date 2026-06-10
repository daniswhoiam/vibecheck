"""Reddit fetcher tests: mapping PRAW submissions to canonical posts, with a
stub standing in for the PRAW client (no network, no credentials)."""

import datetime as dt
from dataclasses import dataclass, field
from typing import Any

from ingestion.reddit import fetch_reddit_posts

SINCE = dt.datetime(2026, 6, 10, 12, 0, tzinfo=dt.UTC)


@dataclass
class FakeSubmission:
    id: str = "abc123"
    title: str = "Cursor is great"
    selftext: str = ""
    author: Any = "alice"
    permalink: str = "/r/programming/comments/abc123/cursor_is_great/"
    created_utc: float = float(int(SINCE.timestamp()) + 60)
    score: int = 42
    num_comments: int = 7
    subreddit: Any = "programming"

    @property
    def fullname(self) -> str:
        return f"t3_{self.id}"


@dataclass
class FakeSubreddit:
    results: dict[str, list[FakeSubmission]]
    calls: list[dict[str, Any]] = field(default_factory=list)
    name: str = ""

    def search(self, query: str, **kwargs: Any):
        self.calls.append({"query": query, **kwargs})
        yield from self.results.get(query, [])


class FakeReddit:
    def __init__(self, results: dict[str, list[FakeSubmission]]) -> None:
        self._sub = FakeSubreddit(results)

    def subreddit(self, name: str) -> FakeSubreddit:
        self._sub.name = name
        return self._sub


async def test_maps_submission_to_canonical_post():
    reddit = FakeReddit({"Cursor": [FakeSubmission()]})
    posts = await fetch_reddit_posts(reddit, ["programming", "cursor"], ["Cursor"], since=SINCE)
    assert len(posts) == 1
    post = posts[0]
    assert post.source == "reddit"
    assert post.source_id == "t3_abc123"
    assert post.content == "Cursor is great"
    assert post.author == "alice"
    assert post.url == "https://www.reddit.com/r/programming/comments/abc123/cursor_is_great/"
    assert post.published_at == dt.datetime.fromtimestamp(int(SINCE.timestamp()) + 60, tz=dt.UTC)
    assert post.metadata == {"score": 42, "num_comments": 7, "subreddit": "programming"}


async def test_searches_combined_subreddits_sorted_by_new():
    reddit = FakeReddit({})
    await fetch_reddit_posts(reddit, ["programming", "cursor"], ["Cursor"], since=SINCE)
    assert reddit._sub.name == "programming+cursor"
    (call,) = reddit._sub.calls
    assert call["sort"] == "new"


async def test_selftext_appended_to_title():
    sub = FakeSubmission(selftext="Honestly the agent mode rules.")
    reddit = FakeReddit({"Cursor": [sub]})
    (post,) = await fetch_reddit_posts(reddit, ["programming"], ["Cursor"], since=SINCE)
    assert post.content == "Cursor is great\n\nHonestly the agent mode rules."


async def test_deleted_author_becomes_none():
    reddit = FakeReddit({"Cursor": [FakeSubmission(author=None)]})
    (post,) = await fetch_reddit_posts(reddit, ["programming"], ["Cursor"], since=SINCE)
    assert post.author is None


async def test_filters_out_posts_older_than_window():
    old = FakeSubmission(id="old1", created_utc=float(int(SINCE.timestamp()) - 1))
    fresh = FakeSubmission(id="new1")
    reddit = FakeReddit({"Cursor": [old, fresh]})
    posts = await fetch_reddit_posts(reddit, ["programming"], ["Cursor"], since=SINCE)
    assert [p.source_id for p in posts] == ["t3_new1"]


async def test_dedupes_across_queries():
    same = FakeSubmission()
    reddit = FakeReddit({"Cursor": [same], "Copilot": [same, FakeSubmission(id="xyz789")]})
    posts = await fetch_reddit_posts(reddit, ["programming"], ["Cursor", "Copilot"], since=SINCE)
    assert sorted(p.source_id for p in posts) == ["t3_abc123", "t3_xyz789"]
