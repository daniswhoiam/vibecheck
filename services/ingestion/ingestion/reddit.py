"""Reddit fetcher: PRAW search across the combined subreddit, one query per
tool name.

PRAW is synchronous, so the whole fetch runs in a worker thread
(``asyncio.to_thread``) — one coarse hop per cycle, the same pattern the
worker uses for model inference. The client is typed as a structural protocol
so tests stub it without touching the network or credentials.
"""

import asyncio
import datetime as dt
from collections.abc import Iterable, Iterator, Sequence
from typing import Any, Protocol

import praw  # type: ignore[import-untyped]

from ingestion.posts import FetchedPost

_SEARCH_LIMIT = 100


class _Subreddit(Protocol):
    def search(self, query: str, *, sort: str, time_filter: str, limit: int) -> Iterator[Any]: ...


class RedditClient(Protocol):
    """The sliver of praw.Reddit the fetcher needs."""

    def subreddit(self, name: str) -> _Subreddit: ...


def make_reddit(client_id: str, client_secret: str, user_agent: str) -> RedditClient:
    """Read-only, app-only OAuth client. check_for_async is silenced because
    PRAW only ever runs inside to_thread here, never on the event loop."""
    reddit = praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent=user_agent,
        check_for_async=False,
    )
    reddit.read_only = True
    return reddit  # type: ignore[no-any-return]


def _time_filter(window: dt.timedelta) -> str:
    """Smallest Reddit time_filter that covers the lookback window; the exact
    cutoff is enforced locally on created_utc."""
    for name, span in (
        ("hour", dt.timedelta(hours=1)),
        ("day", dt.timedelta(days=1)),
        ("week", dt.timedelta(weeks=1)),
        ("month", dt.timedelta(days=31)),
        ("year", dt.timedelta(days=366)),
    ):
        if window <= span:
            return name
    return "all"


def _to_post(submission: Any) -> FetchedPost:
    content = submission.title
    if submission.selftext:
        content = f"{content}\n\n{submission.selftext}"
    return FetchedPost(
        source="reddit",
        source_id=submission.fullname,
        content=content,
        published_at=dt.datetime.fromtimestamp(submission.created_utc, tz=dt.UTC),
        author=str(submission.author) if submission.author is not None else None,
        url=f"https://www.reddit.com{submission.permalink}",
        metadata={
            "score": submission.score,
            "num_comments": submission.num_comments,
            "subreddit": str(submission.subreddit),
        },
    )


def _search_sync(
    reddit: RedditClient,
    subreddits: Sequence[str],
    queries: Iterable[str],
    since: dt.datetime,
) -> list[FetchedPost]:
    combined = reddit.subreddit("+".join(subreddits))
    time_filter = _time_filter(dt.datetime.now(dt.UTC) - since)
    by_id: dict[str, FetchedPost] = {}
    for query in queries:
        for submission in combined.search(
            query, sort="new", time_filter=time_filter, limit=_SEARCH_LIMIT
        ):
            if submission.created_utc < since.timestamp():
                continue
            post = _to_post(submission)
            by_id[post.source_id] = post
    return list(by_id.values())


async def fetch_reddit_posts(
    reddit: RedditClient,
    subreddits: Sequence[str],
    queries: Iterable[str],
    *,
    since: dt.datetime,
) -> list[FetchedPost]:
    """Search each query within the lookback window; dedupe across queries."""
    return await asyncio.to_thread(_search_sync, reddit, subreddits, list(queries), since)
