"""Reddit data client using asyncpraw.

Uses OAuth read-only access (no account/password needed).
asyncpraw handles Reddit's rate limiting automatically via response headers.
Always use 'async with asyncpraw.Reddit(...) as reddit:' to ensure session cleanup.

Credentials required (env vars):
  REDDIT_CLIENT_ID      — from Reddit Apps page (read-only script app)
  REDDIT_CLIENT_SECRET  — from Reddit Apps page
"""
import logging
from datetime import datetime, timezone
import asyncpraw

logger = logging.getLogger(__name__)

# Tool-specific subreddits — high-signal, apply loose relevance check
TOOL_SUBREDDITS: list[str] = [
    "ChatGPT",
    "ClaudeAI",
    "cursor",
    "GithubCopilot",
    "LocalLLaMA",   # Primary hub for Llama, Mistral, local model discussion
]

# Broad AI/dev subreddits — apply strict ambiguity-aware filter
BROAD_SUBREDDITS: list[str] = [
    "artificial",
    "MachineLearning",
    "programming",
    "learnmachinelearning",
    "ChatGPTCoding",
]

REDDIT_USER_AGENT = "VibeCheck/2.0 (sentiment research; read-only)"


async def fetch_subreddit_posts(
    subreddit_name: str,
    client_id: str,
    client_secret: str,
    limit: int = 100,
) -> list[dict]:
    """Fetch the most recent posts from a subreddit.

    Returns list of normalized post dicts (not raw asyncpraw objects, which
    are stateful and can't be used after the Reddit context manager closes).

    Args:
        subreddit_name: e.g., "ChatGPT"
        client_id: REDDIT_CLIENT_ID env var
        client_secret: REDDIT_CLIENT_SECRET env var
        limit: max posts to fetch (asyncpraw caps at 1000 per call)
    """
    posts = []
    async with asyncpraw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent=REDDIT_USER_AGENT,
    ) as reddit:
        subreddit = await reddit.subreddit(subreddit_name)
        async for submission in subreddit.new(limit=limit):
            # Extract all data while Reddit session is still open
            posts.append({
                "id": submission.id,
                "title": submission.title,
                "selftext": submission.selftext,
                "url": submission.url,
                "score": submission.score,
                "num_comments": submission.num_comments,
                "created_utc": submission.created_utc,
                "permalink": f"https://reddit.com{submission.permalink}",
                "is_self": submission.is_self,
                "subreddit": subreddit_name,
            })
    return posts


def normalize_reddit_post(post_dict: dict) -> dict:
    """Normalize a Reddit post dict to common PostCreate fields.

    For self-posts: body = selftext (may be empty string for link posts).
    For link posts: url is the external link; body is None.
    """
    body = post_dict.get("selftext") if post_dict.get("is_self") else None
    # Reddit uses empty string "" for link posts with no selftext — normalize to None
    if body == "" or body == "[deleted]" or body == "[removed]":
        body = None

    return {
        "source": "reddit",
        "external_id": post_dict["id"],
        "url": post_dict.get("permalink"),  # Use Reddit permalink (canonical)
        "title": post_dict.get("title"),
        "body": body,
        "published_at": datetime.fromtimestamp(post_dict["created_utc"], tz=timezone.utc),
        "metadata": {
            "score": post_dict.get("score"),
            "comment_count": post_dict.get("num_comments"),
            "subreddit": post_dict.get("subreddit"),
            "external_url": post_dict.get("url") if not post_dict.get("is_self") else None,
        },
    }
