"""Hacker News fetcher: Algolia full-text search, one query per tool name.

`search_by_date` (not relevance-ranked `search`) so a lookback-window filter
returns *everything* recent, not Algolia's idea of the best matches. Stories
only for now — comments are deferred (volume, threading).
"""

import datetime as dt
import html
import re
from collections.abc import Iterable
from typing import Any

import httpx

from ingestion.posts import FetchedPost

ALGOLIA_URL = "https://hn.algolia.com/api/v1/search_by_date"
_PAGE_SIZE = 100  # Algolia's maximum; one page per query keeps us stateless

_TAG_RE = re.compile(r"<[^>]+>")


def _clean(text: str) -> str:
    """Algolia story_text is HTML; the model wants prose."""
    prose = html.unescape(_TAG_RE.sub(" ", text))
    return re.sub(r"\s+", " ", prose).strip()


def _to_post(hit: dict[str, Any]) -> FetchedPost:
    object_id = str(hit["objectID"])
    content = hit["title"]
    if hit.get("story_text"):
        content = f"{content}\n\n{_clean(hit['story_text'])}"
    return FetchedPost(
        source="hn",
        source_id=object_id,
        content=content,
        published_at=dt.datetime.fromtimestamp(hit["created_at_i"], tz=dt.UTC),
        author=hit.get("author"),
        # Ask/Show HN stories have no external URL; link the item page itself.
        url=hit.get("url") or f"https://news.ycombinator.com/item?id={object_id}",
        metadata={"points": hit.get("points"), "num_comments": hit.get("num_comments")},
    )


async def fetch_hn_posts(
    client: httpx.AsyncClient,
    queries: Iterable[str],
    *,
    since: dt.datetime,
) -> list[FetchedPost]:
    """Search each query within the lookback window; dedupe across queries
    (one story can match several tools' searches)."""
    by_id: dict[str, FetchedPost] = {}
    for query in queries:
        response = await client.get(
            ALGOLIA_URL,
            params={
                "query": query,
                "tags": "story",
                "numericFilters": f"created_at_i>{int(since.timestamp())}",
                "hitsPerPage": _PAGE_SIZE,
            },
        )
        response.raise_for_status()
        for hit in response.json()["hits"]:
            post = _to_post(hit)
            by_id[post.source_id] = post
    return list(by_id.values())
