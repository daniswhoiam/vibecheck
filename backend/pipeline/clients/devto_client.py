"""Dev.to (Forem) data client using Forem API v1.

API docs: https://developers.forem.com/api/v1
Requires Accept: application/vnd.forem.api-v1+json header.
API key optional — improves rate limit ceiling but public articles are accessible without auth.

IMPORTANT: The /api/articles list endpoint returns 'description' (excerpt) NOT full body.
Full body requires fetching /api/articles/{id} per article.
"""
import asyncio
import logging
import httpx

logger = logging.getLogger(__name__)

DEVTO_API_BASE = "https://dev.to/api"
DEVTO_ACCEPT = "application/vnd.forem.api-v1+json"

# Tags that cover all 10 CURATED_ENTITIES across HN/Reddit/Dev.to discussion
DEVTO_TAGS: list[str] = [
    "ai",
    "machinelearning",
    "llm",
    "gpt4",
    "claude",
    "gemini",
    "llama",
    "cursor",
    "github-copilot",
    "devtools",
]

# Max concurrent body fetch requests (prevent 429 rate limiting)
BODY_FETCH_CONCURRENCY = 5


async def fetch_devto_articles(
    tag: str,
    client: httpx.AsyncClient,
    api_key: str | None = None,
    page: int = 1,
    per_page: int = 30,
) -> list[dict]:
    """Fetch article list for a tag (metadata + description only, no full body).

    Returns list of article dicts with 'id', 'title', 'description', 'url',
    'published_at', 'positive_reactions_count', 'comments_count'.
    """
    headers = {
        "Accept": DEVTO_ACCEPT,
        "User-Agent": "VibeCheck/2.0",
    }
    if api_key:
        headers["api-key"] = api_key

    response = await client.get(
        f"{DEVTO_API_BASE}/articles",
        params={"tag": tag, "page": page, "per_page": per_page},
        headers=headers,
        timeout=30.0,
    )
    response.raise_for_status()
    return response.json()


async def fetch_article_body(
    article_id: int,
    client: httpx.AsyncClient,
    api_key: str | None = None,
) -> str | None:
    """Fetch the full markdown body of a single article.

    Returns body_markdown string or None on failure.
    """
    headers = {
        "Accept": DEVTO_ACCEPT,
        "User-Agent": "VibeCheck/2.0",
    }
    if api_key:
        headers["api-key"] = api_key

    try:
        response = await client.get(
            f"{DEVTO_API_BASE}/articles/{article_id}",
            headers=headers,
            timeout=30.0,
        )
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            logger.warning("Dev.to rate limited fetching article %d. Waiting %ds.", article_id, retry_after)
            await asyncio.sleep(retry_after)
            response = await client.get(
                f"{DEVTO_API_BASE}/articles/{article_id}",
                headers=headers,
                timeout=30.0,
            )
        response.raise_for_status()
        data = response.json()
        return data.get("body_markdown")
    except Exception as exc:
        logger.debug("Could not fetch body for Dev.to article %d: %s", article_id, exc)
        return None


def normalize_devto_article(article: dict, body: str | None = None) -> dict:
    """Normalize a Dev.to article dict to common PostCreate fields.

    Uses body_markdown from a separate fetch when available;
    falls back to 'description' (excerpt) from the list endpoint.
    """
    from datetime import datetime
    published_raw = article.get("published_at") or article.get("created_at")
    if published_raw:
        published_at = datetime.fromisoformat(published_raw.replace("Z", "+00:00"))
    else:
        from datetime import timezone
        published_at = datetime.now(timezone.utc)

    return {
        "source": "devto",
        "external_id": str(article["id"]),
        "url": article.get("url") or article.get("canonical_url"),
        "title": article.get("title"),
        "body": body or article.get("description"),  # Full markdown preferred, excerpt fallback
        "published_at": published_at,
        "metadata": {
            "score": article.get("positive_reactions_count"),
            "comment_count": article.get("comments_count"),
            "tags": article.get("tag_list"),
        },
    }
