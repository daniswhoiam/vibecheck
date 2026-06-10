"""Publisher tests against the real broker, with throwaway queue names so a
deployed stack on the same broker never sees test messages.

The contract is pinned from both ends: a published message must parse with the
worker's own parse_post_message, and the declared topology must be accepted by
the worker's declare_topology (RabbitMQ rejects re-declaration with different
arguments, so this catches drift before deploy ever could)."""

import dataclasses
import datetime as dt
import os
import uuid

import aio_pika
import pytest
from ingestion.posts import FetchedPost
from ingestion.publisher import declare_topology, publish_post, serialize_post
from worker.consumer import declare_topology as worker_declare_topology
from worker.messages import parse_post_message

AMQP_URL = os.environ.get("AMQP_URL", "amqp://vibecheck:vibecheck@127.0.0.1:5672/")

POST = FetchedPost(
    source="hn",
    source_id="41000001",
    content="Cursor is great",
    published_at=dt.datetime(2026, 6, 10, 12, 0, tzinfo=dt.UTC),
    author="alice",
    url="https://example.com/post",
    metadata={"points": 42},
)


@dataclasses.dataclass(frozen=True)
class Topology:
    queue: str
    dlx: str
    dead_queue: str


@pytest.fixture
def topology() -> Topology:
    name = f"test.ingestion.{uuid.uuid4().hex[:8]}"
    return Topology(queue=name, dlx=f"{name}.dlx", dead_queue=f"{name}.dead")


@pytest.fixture
async def amqp(topology):
    connection = await aio_pika.connect(AMQP_URL)
    channel = await connection.channel()
    await declare_topology(
        channel,
        queue_name=topology.queue,
        dlx_name=topology.dlx,
        dead_queue_name=topology.dead_queue,
    )
    yield channel
    await channel.queue_delete(topology.queue)
    await channel.queue_delete(topology.dead_queue)
    await channel.exchange_delete(topology.dlx)
    await connection.close()


async def test_published_message_parses_with_worker_contract(topology, amqp):
    await publish_post(amqp, POST, ["cursor", "github-copilot"], queue_name=topology.queue)

    message = await (await amqp.get_queue(topology.queue)).get(timeout=10)
    await message.ack()
    assert message.delivery_mode == aio_pika.DeliveryMode.PERSISTENT

    parsed = parse_post_message(message.body)
    assert parsed.source == "hn"
    assert parsed.source_id == "41000001"
    assert parsed.content == "Cursor is great"
    assert parsed.published_at == POST.published_at
    assert parsed.tools == ["cursor", "github-copilot"]
    assert parsed.author == "alice"
    assert parsed.url == "https://example.com/post"
    assert parsed.metadata == {"points": 42}


async def test_topology_matches_workers(topology, amqp):
    # Must not raise PRECONDITION_FAILED: identical names + arguments.
    await worker_declare_topology(
        amqp,
        queue_name=topology.queue,
        dlx_name=topology.dlx,
        dead_queue_name=topology.dead_queue,
    )


def test_serialize_rejects_naive_timestamp():
    naive = dataclasses.replace(POST, published_at=dt.datetime(2026, 6, 10, 12, 0))
    with pytest.raises(ValueError, match="timezone-aware"):
        serialize_post(naive, ["cursor"])


def test_serialize_rejects_empty_tools():
    with pytest.raises(ValueError, match="tools"):
        serialize_post(POST, [])
