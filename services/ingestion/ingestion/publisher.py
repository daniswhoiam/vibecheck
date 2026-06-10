"""Publish detected posts to the analysis queue.

The queue/DLX names and arguments deliberately mirror
``worker/consumer.py:declare_topology`` — RabbitMQ rejects a re-declaration
whose arguments differ (PRECONDITION_FAILED), so whichever service starts
first must declare the exact same topology. test_publisher.py pins the two
declarations against each other, and pins the wire format against the
worker's parser.
"""

import json
from collections.abc import Sequence

import aio_pika
from aio_pika.abc import AbstractChannel

from ingestion.posts import FetchedPost

QUEUE_NAME = "posts.to_analyze"
DLX_NAME = "posts.dlx"
DEAD_QUEUE_NAME = "posts.to_analyze.dead"
_DEAD_ROUTING_KEY = "dead"


async def declare_topology(
    channel: AbstractChannel,
    *,
    queue_name: str = QUEUE_NAME,
    dlx_name: str = DLX_NAME,
    dead_queue_name: str = DEAD_QUEUE_NAME,
) -> None:
    """Declare queue + dead-letter exchange/queue. Idempotent; safe anywhere."""
    dlx = await channel.declare_exchange(dlx_name, aio_pika.ExchangeType.DIRECT, durable=True)
    dead_queue = await channel.declare_queue(dead_queue_name, durable=True)
    await dead_queue.bind(dlx, routing_key=_DEAD_ROUTING_KEY)
    await channel.declare_queue(
        queue_name,
        durable=True,
        arguments={
            "x-dead-letter-exchange": dlx_name,
            "x-dead-letter-routing-key": _DEAD_ROUTING_KEY,
        },
    )


def serialize_post(post: FetchedPost, tools: Sequence[str]) -> bytes:
    """Serialize to the worker's message contract (see worker/messages.py)."""
    if post.published_at.tzinfo is None:
        raise ValueError(f"published_at must be timezone-aware: {post.published_at!r}")
    if not tools:
        raise ValueError("tools must be non-empty")
    return json.dumps(
        {
            "source": post.source,
            "source_id": post.source_id,
            "content": post.content,
            "published_at": post.published_at.isoformat(),
            "tools": list(tools),
            "author": post.author,
            "url": post.url,
            "metadata": post.metadata,
        }
    ).encode()


async def publish_post(
    channel: AbstractChannel,
    post: FetchedPost,
    tools: Sequence[str],
    *,
    queue_name: str = QUEUE_NAME,
) -> None:
    """Publish one post for analysis. PERSISTENT + durable queue: an accepted
    post survives a broker restart."""
    await channel.default_exchange.publish(
        aio_pika.Message(
            body=serialize_post(post, tools),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json",
        ),
        routing_key=queue_name,
    )
