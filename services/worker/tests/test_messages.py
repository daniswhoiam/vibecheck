"""Unit tests for the queue message contract.

A message is self-contained (full post + mentioned tool slugs) so the pipeline
can be exercised by hand-publishing JSON via the RabbitMQ management UI.
Anything malformed must raise PermanentError - the consumer's signal to
dead-letter instead of requeue.
"""

import datetime as dt
import json

import pytest
from worker.messages import PermanentError, parse_post_message

VALID = {
    "source": "reddit",
    "source_id": "t3_abc123",
    "content": "Cursor is great",
    "author": "alice",
    "url": "https://reddit.com/r/x/t3_abc123",
    "published_at": "2026-06-01T12:00:00Z",
    "metadata": {"subreddit": "programming"},
    "tools": ["cursor"],
}


def body(overrides: dict | None = None, drop: list[str] | None = None) -> bytes:
    msg = {**VALID, **(overrides or {})}
    for key in drop or []:
        del msg[key]
    return json.dumps(msg).encode()


def test_parses_full_message() -> None:
    msg = parse_post_message(body())
    assert msg.source == "reddit"
    assert msg.source_id == "t3_abc123"
    assert msg.content == "Cursor is great"
    assert msg.author == "alice"
    assert msg.url == "https://reddit.com/r/x/t3_abc123"
    assert msg.published_at == dt.datetime(2026, 6, 1, 12, tzinfo=dt.UTC)
    assert msg.metadata == {"subreddit": "programming"}
    assert msg.tools == ["cursor"]


def test_optional_fields_default() -> None:
    msg = parse_post_message(body(drop=["author", "url", "metadata"]))
    assert msg.author is None
    assert msg.url is None
    assert msg.metadata == {}


def test_invalid_json_is_permanent() -> None:
    with pytest.raises(PermanentError):
        parse_post_message(b"not json{")


def test_missing_required_field_is_permanent() -> None:
    with pytest.raises(PermanentError):
        parse_post_message(body(drop=["content"]))


def test_naive_timestamp_is_permanent() -> None:
    # A timestamp without offset is ambiguous; refuse rather than guess UTC.
    with pytest.raises(PermanentError):
        parse_post_message(body({"published_at": "2026-06-01T12:00:00"}))


def test_unparseable_timestamp_is_permanent() -> None:
    with pytest.raises(PermanentError):
        parse_post_message(body({"published_at": "yesterday"}))


def test_empty_tools_is_permanent() -> None:
    # A post mentioning no tracked tool has no business on this queue.
    with pytest.raises(PermanentError):
        parse_post_message(body({"tools": []}))


def test_wrong_type_is_permanent() -> None:
    with pytest.raises(PermanentError):
        parse_post_message(body({"tools": "cursor"}))
    with pytest.raises(PermanentError):
        parse_post_message(body({"content": 42}))
    with pytest.raises(PermanentError):
        parse_post_message(body({"metadata": [1, 2]}))


def test_non_object_payload_is_permanent() -> None:
    with pytest.raises(PermanentError):
        parse_post_message(b'["a", "list"]')
