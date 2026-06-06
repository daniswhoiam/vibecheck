import datetime as dt

import pytest
from api.main import app
from httpx import ASGITransport, AsyncClient


class _PoisonPool:
    """A pool whose connection() must never be reached."""

    def connection(self):
        raise AssertionError("DB connection acquired before request validation passed")


async def test_sentiment_week_buckets_are_weighted(client, seeded) -> None:
    response = await client.get(
        f"/api/v1/sentiment/{seeded.slug}", params={"period": "30d", "bucket": "week"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tool"] == seeded.slug
    assert body["period"] == "30d"
    assert body["bucket"] == "week"
    # window = [FIXED_NOW - 30d, FIXED_NOW); parse to be robust to Z vs +00:00
    assert dt.datetime.fromisoformat(body["start"]) == dt.datetime(2026, 5, 16, 12, tzinfo=dt.UTC)
    assert dt.datetime.fromisoformat(body["end"]) == dt.datetime(2026, 6, 15, 12, tzinfo=dt.UTC)
    by_start = {dt.datetime.fromisoformat(p["bucket_start"]).date(): p for p in body["series"]}
    assert set(by_start) == {dt.date(2026, 5, 18), dt.date(2026, 5, 25)}
    wk1 = by_start[dt.date(2026, 5, 18)]
    assert wk1["n"] == 3
    assert wk1["avg_score"] == pytest.approx(1.9 / 3)  # weighted, not 0.55
    wk2 = by_start[dt.date(2026, 5, 25)]
    assert wk2["n"] == 1
    assert wk2["avg_score"] == pytest.approx(0.1)


async def test_sentiment_day_buckets(client, seeded) -> None:
    response = await client.get(f"/api/v1/sentiment/{seeded.slug}", params={"bucket": "day"})
    assert response.status_code == 200
    by_start = {
        dt.datetime.fromisoformat(p["bucket_start"]).date(): p for p in response.json()["series"]
    }
    assert by_start[dt.date(2026, 5, 18)]["n"] == 2
    assert by_start[dt.date(2026, 5, 18)]["avg_score"] == pytest.approx(0.8)
    assert by_start[dt.date(2026, 5, 20)]["n"] == 1


async def test_sentiment_unknown_tool_404(client) -> None:
    response = await client.get("/api/v1/sentiment/no-such-tool")
    assert response.status_code == 404


async def test_sentiment_invalid_period_422(client) -> None:
    response = await client.get("/api/v1/sentiment/any-tool", params={"period": "invalid"})
    assert response.status_code == 422
    # The committed OpenAPI advertises HTTPValidationError ({"detail": [...]}) for
    # 422; the runtime body must match so generated clients parse it correctly.
    assert isinstance(response.json()["detail"], list)


async def test_sentiment_invalid_bucket_422(client) -> None:
    response = await client.get("/api/v1/sentiment/any-tool", params={"bucket": "fortnight"})
    assert response.status_code == 422


async def test_invalid_params_do_not_touch_the_pool() -> None:
    # Malformed query params must 422 without acquiring a DB connection, so a bad
    # request can neither consume the pool nor surface a 500 when it is exhausted.
    app.state.pool = _PoisonPool()
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            response = await c.get("/api/v1/sentiment/any-tool", params={"period": "invalid"})
        assert response.status_code == 422
    finally:
        del app.state.pool


async def test_sentiment_oversized_period_422(client) -> None:
    # A digit string large enough to OverflowError timedelta must be rejected at
    # validation (422), not escape as a 500.
    response = await client.get("/api/v1/sentiment/any-tool", params={"period": "99999999999d"})
    assert response.status_code == 422


async def test_sentiment_empty_window_is_200_empty(client, seeded) -> None:
    # 7d window ends at FIXED_NOW (06-15); all seeded posts are >= 19 days old.
    response = await client.get(f"/api/v1/sentiment/{seeded.slug}", params={"period": "7d"})
    assert response.status_code == 200
    assert response.json()["series"] == []
