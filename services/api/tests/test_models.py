import datetime as dt

from api.models import SentimentPoint, SentimentSeries, Tool


def test_tool_fields() -> None:
    t = Tool(slug="cursor", display_name="Cursor", aliases=["cursor", "cursor ai"])
    assert t.model_dump() == {
        "slug": "cursor",
        "display_name": "Cursor",
        "aliases": ["cursor", "cursor ai"],
    }


def test_sentiment_series_field_names() -> None:
    point = SentimentPoint(
        bucket_start=dt.datetime(2026, 5, 18, tzinfo=dt.UTC), n=3, avg_score=0.63
    )
    series = SentimentSeries(
        tool="cursor",
        period="30d",
        bucket="week",
        start=dt.datetime(2026, 5, 16, tzinfo=dt.UTC),
        end=dt.datetime(2026, 6, 15, tzinfo=dt.UTC),
        series=[point],
    )
    dumped = series.model_dump()
    assert set(dumped) == {"tool", "period", "bucket", "start", "end", "series"}
    assert set(dumped["series"][0]) == {"bucket_start", "n", "avg_score"}
