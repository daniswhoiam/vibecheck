"""Discourse forum client using the public REST API.

Target forums:
  - https://forum.cursor.com (Cursor AI editor community)
  - https://community.openai.com (OpenAI community)

Both are public Discourse instances. No authentication required for read-only access.
Polite delay of 1 second between paginated requests to avoid rate limiting.
"""
import asyncio
import logging
from datetime import datetime
import httpx

logger = logging.getLogger(__name__)

# Polite delay between requests to avoid Cloudflare throttling
INTER_PAGE_DELAY = 1.0  # seconds

# Target Discourse forums
DISCOURSE_FORUMS = [
    "https://forum.cursor.com",
    "https://community.openai.com",
]


async def fetch_discourse_topics(
    base_url: str,
    client: httpx.AsyncClient,
    max_pages: int = 5,
) -> list[dict]:
    """Fetch latest topics from a Discourse forum.

    Fetches up to max_pages pages of /latest.json.
    Returns list of raw topic dicts.

    Raises httpx.HTTPStatusError on 4xx/5xx (including 403 login-required).
    """
    topics = []
    for page in range(max_pages):
        if page > 0:
            await asyncio.sleep(INTER_PAGE_DELAY)
        try:
            response = await client.get(
                f"{base_url}/latest.json",
                params={"page": page},
                headers={"User-Agent": "VibeCheck/2.0 (sentiment research bot)"},
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            page_topics = data.get("topic_list", {}).get("topics", [])
            if not page_topics:
                break
            topics.extend(page_topics)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                retry_after = int(e.response.headers.get("Retry-After", 60))
                logger.warning(
                    "Discourse rate limited at %s page %d. Waiting %ds.",
                    base_url, page, retry_after,
                )
                await asyncio.sleep(retry_after)
                # Retry once after waiting
                response = await client.get(
                    f"{base_url}/latest.json",
                    params={"page": page},
                    headers={"User-Agent": "VibeCheck/2.0 (sentiment research bot)"},
                    timeout=30.0,
                )
                response.raise_for_status()
                data = response.json()
                page_topics = data.get("topic_list", {}).get("topics", [])
                topics.extend(page_topics)
            else:
                raise
    return topics


async def fetch_topic_body(
    base_url: str,
    topic_slug: str,
    topic_id: int,
    client: httpx.AsyncClient,
) -> str | None:
    """Fetch the body text of the first post (OP) for a topic.

    Returns the raw_html or cooked (HTML) text of the first post, or None on failure.
    Used to get the full post body — /latest.json only contains metadata.
    """
    try:
        await asyncio.sleep(INTER_PAGE_DELAY)
        response = await client.get(
            f"{base_url}/t/{topic_slug}/{topic_id}.json",
            headers={"User-Agent": "VibeCheck/2.0 (sentiment research bot)"},
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        posts = data.get("post_stream", {}).get("posts", [])
        if posts:
            # First post is the original post (OP)
            return posts[0].get("cooked") or posts[0].get("raw")
    except Exception as exc:
        logger.debug("Could not fetch topic body for %s/%d: %s", topic_slug, topic_id, exc)
    return None


def normalize_discourse_topic(
    topic: dict,
    base_url: str,
    body: str | None = None,
) -> dict:
    """Normalize a Discourse topic dict to common PostCreate fields."""
    slug = topic.get("slug", str(topic.get("id", "")))
    topic_id = topic.get("id")
    url = f"{base_url}/t/{slug}/{topic_id}" if topic_id else None

    # Parse created_at ISO string
    created_at_raw = topic.get("created_at")
    if created_at_raw:
        published_at = datetime.fromisoformat(created_at_raw.replace("Z", "+00:00"))
    else:
        from datetime import timezone
        published_at = datetime.now(timezone.utc)

    return {
        "source": "discourse",
        "external_id": f"{base_url.split('//')[1]}_{topic_id}",  # e.g. "forum.cursor.com_12345"
        "url": url,
        "title": topic.get("title"),
        "body": body,
        "published_at": published_at,
        "metadata": {
            "views": topic.get("views"),
            "comment_count": topic.get("posts_count"),
            "forum": base_url,
        },
    }
