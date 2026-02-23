"""Hacker News data client using the Algolia Search API.

API: https://hn.algolia.com/api/v1/search_by_date
No authentication required. Free, no rate limit documented.
Hard limit: 1000 hits per query (Algolia constraint).
"""
import logging
from datetime import datetime, timezone
import httpx

logger = logging.getLogger(__name__)

HN_API_BASE = "https://hn.algolia.com/api/v1"
HN_ITEMS_API = "https://hacker-news.firebaseio.com/v0/item"
HITS_PER_PAGE = 100
ALGOLIA_MAX_HITS = 1000  # Hard cap: page * hitsPerPage <= 1000


async def fetch_hn_stories(
    since_unix: int,
    client: httpx.AsyncClient,
) -> list[dict]:
    """Fetch HN stories created after since_unix (Unix epoch).

    Handles pagination up to Algolia's 1000-hit cap.
    For backfill (large time windows), callers should split into weekly chunks.

    Returns list of raw Algolia hit dicts.
    """
    results = []
    page = 0
    while True:
        response = await client.get(
            f"{HN_API_BASE}/search_by_date",
            params={
                "tags": "story",
                "numericFilters": f"created_at_i>{since_unix}",
                "hitsPerPage": HITS_PER_PAGE,
                "page": page,
            },
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        hits = data.get("hits", [])
        results.extend(hits)
        nb_pages = data.get("nbPages", 1)
        if not hits or page >= nb_pages - 1:
            break
        page += 1
        if (page + 1) * HITS_PER_PAGE > ALGOLIA_MAX_HITS:
            logger.warning(
                "HN Algolia 1000-hit cap reached for since_unix=%d. "
                "Use weekly time windows for backfill.",
                since_unix,
            )
            break
    return results


async def fetch_hn_comments_for_story(
    story_id: str,
    client: httpx.AsyncClient,
) -> list[dict]:
    """Fetch top-level comments for a single HN story via Algolia.

    Returns list of raw comment hit dicts (top-level only, not nested replies).
    """
    results = []
    page = 0
    while True:
        response = await client.get(
            f"{HN_API_BASE}/search_by_date",
            params={
                "tags": f"comment,story_{story_id}",
                "hitsPerPage": HITS_PER_PAGE,
                "page": page,
            },
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        hits = data.get("hits", [])
        # Filter to top-level only: parent_id == story_id
        top_level = [h for h in hits if str(h.get("parent_id")) == str(story_id)]
        results.extend(top_level)
        nb_pages = data.get("nbPages", 1)
        if not hits or page >= nb_pages - 1:
            break
        page += 1
        if (page + 1) * HITS_PER_PAGE > ALGOLIA_MAX_HITS:
            break
    return results


def normalize_hn_story(hit: dict) -> dict:
    """Normalize an Algolia story hit to a common dict for PostCreate.

    Returns dict with keys: source, external_id, url, title, body, published_at, metadata.
    """
    return {
        "source": "hackernews",
        "external_id": hit["objectID"],
        "url": hit.get("url"),
        "title": hit.get("title"),
        "body": hit.get("story_text"),  # None for link posts
        "published_at": datetime.fromtimestamp(hit["created_at_i"], tz=timezone.utc),
        "metadata": {
            "score": hit.get("points"),
            "comment_count": hit.get("num_comments"),
        },
    }


def normalize_hn_comment(hit: dict, story_title: str | None = None) -> dict:
    """Normalize an Algolia comment hit to a common dict for PostCreate."""
    return {
        "source": "hackernews",
        "external_id": f"comment_{hit['objectID']}",
        "url": f"https://news.ycombinator.com/item?id={hit['objectID']}",
        "title": story_title,  # Inherit story title for context
        "body": hit.get("comment_text"),
        "published_at": datetime.fromtimestamp(hit["created_at_i"], tz=timezone.utc),
        "metadata": {
            "story_id": hit.get("parent_id"),
            "comment_count": None,
        },
    }
