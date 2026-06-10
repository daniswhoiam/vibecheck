"""Queue message contract for posts awaiting analysis.

A message carries the full post plus the slugs of the tools it mentions, so it
is self-contained: nothing needs to exist in the database beforehand, and a
test message can be hand-published via the RabbitMQ management UI.

Parsing failures raise :class:`PermanentError` - redelivery cannot fix a
malformed payload, so the consumer dead-letters it for inspection.
"""

import datetime as dt
import json
from dataclasses import dataclass, field
from typing import Any


class PermanentError(Exception):
    """The message can never be processed; dead-letter, do not requeue."""


@dataclass(frozen=True, slots=True)
class PostMessage:
    source: str
    source_id: str
    content: str
    published_at: dt.datetime
    tools: list[str]
    author: str | None = None
    url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def _require_str(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise PermanentError(f"field {key!r} must be a non-empty string")
    return value


def _optional_str(payload: dict[str, Any], key: str) -> str | None:
    value = payload.get(key)
    if value is not None and not isinstance(value, str):
        raise PermanentError(f"field {key!r} must be a string or null")
    return value


def parse_post_message(body: bytes) -> PostMessage:
    """Parse and validate a raw message body."""
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PermanentError(f"body is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise PermanentError("payload must be a JSON object")

    raw_published = _require_str(payload, "published_at")
    try:
        published_at = dt.datetime.fromisoformat(raw_published)
    except ValueError as exc:
        raise PermanentError(f"published_at is not ISO 8601: {raw_published!r}") from exc
    if published_at.tzinfo is None:
        # A naive timestamp is ambiguous; refuse rather than guess UTC.
        raise PermanentError(f"published_at must carry a UTC offset: {raw_published!r}")

    tools = payload.get("tools")
    if not isinstance(tools, list) or not tools or not all(isinstance(t, str) and t for t in tools):
        raise PermanentError("field 'tools' must be a non-empty list of slugs")

    metadata = payload.get("metadata", {})
    if not isinstance(metadata, dict):
        raise PermanentError("field 'metadata' must be a JSON object")

    return PostMessage(
        source=_require_str(payload, "source"),
        source_id=_require_str(payload, "source_id"),
        content=_require_str(payload, "content"),
        published_at=published_at,
        tools=tools,
        author=_optional_str(payload, "author"),
        url=_optional_str(payload, "url"),
        metadata=metadata,
    )
