"""HN fetcher tests: the mapping from Algolia hits to canonical posts, with
the network replaced by httpx.MockTransport."""

import datetime as dt

import httpx
import pytest
from ingestion.hn import ALGOLIA_URL, fetch_hn_posts

SINCE = dt.datetime(2026, 6, 10, 12, 0, tzinfo=dt.UTC)


def make_client(hits_by_query: dict[str, list[dict]]) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).startswith(ALGOLIA_URL)
        params = request.url.params
        assert params["tags"] == "story"
        assert params["numericFilters"] == f"created_at_i>{int(SINCE.timestamp())}"
        hits = hits_by_query.get(params["query"], [])
        return httpx.Response(200, json={"hits": hits})

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def hit(**overrides) -> dict:
    base = {
        "objectID": "41000001",
        "title": "Cursor is great",
        "url": "https://example.com/post",
        "author": "alice",
        "story_text": None,
        "created_at_i": int(SINCE.timestamp()) + 60,
        "points": 42,
        "num_comments": 7,
    }
    return base | overrides


async def test_maps_hit_to_canonical_post():
    client = make_client({"Cursor": [hit()]})
    posts = await fetch_hn_posts(client, ["Cursor"], since=SINCE)
    assert len(posts) == 1
    post = posts[0]
    assert post.source == "hn"
    assert post.source_id == "41000001"
    assert post.content == "Cursor is great"
    assert post.author == "alice"
    assert post.url == "https://example.com/post"
    assert post.published_at == dt.datetime.fromtimestamp(int(SINCE.timestamp()) + 60, tz=dt.UTC)
    assert post.metadata == {"points": 42, "num_comments": 7}


async def test_story_text_appended_with_html_stripped():
    raw = "<p>It&#x27;s the best <i>editor</i></p>"
    client = make_client({"Cursor": [hit(story_text=raw)]})
    (post,) = await fetch_hn_posts(client, ["Cursor"], since=SINCE)
    assert post.content == "Cursor is great\n\nIt's the best editor"


async def test_ask_hn_without_url_falls_back_to_item_page():
    client = make_client({"Cursor": [hit(url=None)]})
    (post,) = await fetch_hn_posts(client, ["Cursor"], since=SINCE)
    assert post.url == "https://news.ycombinator.com/item?id=41000001"


async def test_dedupes_across_queries():
    same = hit()
    client = make_client({"Cursor": [same], "Copilot": [same, hit(objectID="41000002")]})
    posts = await fetch_hn_posts(client, ["Cursor", "Copilot"], since=SINCE)
    assert sorted(p.source_id for p in posts) == ["41000001", "41000002"]


async def test_http_error_propagates():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with pytest.raises(httpx.HTTPStatusError):
        await fetch_hn_posts(client, ["Cursor"], since=SINCE)


async def test_hit_missing_author_is_tolerated():
    client = make_client({"Cursor": [hit(author=None)]})
    (post,) = await fetch_hn_posts(client, ["Cursor"], since=SINCE)
    assert post.author is None
