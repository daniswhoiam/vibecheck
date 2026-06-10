"""End-to-end consumer tests: real RabbitMQ in, real Postgres out.

Each test runs the consumer as a background task with the stub analyzer over a
throwaway, uniquely-named topology - a deployed worker may be consuming the
production queue on the same broker, and it must never steal test messages.
Tests poll for the observable outcome (a DB row or a dead-lettered message).
"""

import asyncio
import contextlib
import dataclasses
import json
import os
import uuid

import aio_pika
import pytest
from worker.consumer import declare_topology, run_consumer

from .conftest import DSN, StubAnalyzer

AMQP_URL = os.environ.get("AMQP_URL", "amqp://vibecheck:vibecheck@127.0.0.1:5672/")


@dataclasses.dataclass(frozen=True)
class Topology:
    queue: str
    dlx: str
    dead_queue: str


def make_payload(seed) -> dict:
    return {
        "source": seed.source,
        "source_id": f"{seed.source}-q1",
        "content": "Queue test post",
        "author": "alice",
        "url": None,
        "published_at": "2026-06-01T12:00:00Z",
        "metadata": {},
        "tools": [seed.slug],
    }


@pytest.fixture
def topology() -> Topology:
    name = f"test.posts.{uuid.uuid4().hex[:8]}"
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


@pytest.fixture
async def consumer(topology):
    task = asyncio.create_task(
        run_consumer(
            AMQP_URL,
            DSN,
            StubAnalyzer(),
            queue_name=topology.queue,
            dlx_name=topology.dlx,
            dead_queue_name=topology.dead_queue,
        )
    )
    yield task
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


async def publish(channel, topology: Topology, body: bytes) -> None:
    await channel.default_exchange.publish(
        aio_pika.Message(body=body, delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
        routing_key=topology.queue,
    )


async def poll(predicate, timeout: float = 15.0):
    async with asyncio.timeout(timeout):
        while True:
            result = await predicate()
            if result is not None:
                return result
            await asyncio.sleep(0.1)


async def test_published_message_lands_in_postgres(db_pool, seed, topology, amqp, consumer) -> None:
    await publish(amqp, topology, json.dumps(make_payload(seed)).encode())

    async def find_row():
        async with db_pool.connection() as conn:
            cur = await conn.execute(
                """
                SELECT a.score, a.label, a.model_name
                FROM posts p
                JOIN mentions m ON m.post_id = p.id
                JOIN analysis_results a ON a.mention_id = m.id
                WHERE p.source = %s
                """,
                (seed.source,),
            )
            return await cur.fetchone()

    row = await poll(find_row)
    assert row == (0.9, "positive", "stub-model")


async def test_malformed_message_goes_to_dead_letter_queue(topology, amqp, consumer) -> None:
    marker = uuid.uuid4().hex
    await publish(amqp, topology, f"not json {marker}".encode())

    async def find_dead():
        msg = await (await amqp.get_queue(topology.dead_queue)).get(fail=False)
        if msg is not None:
            await msg.ack()
        return msg

    dead = await poll(find_dead)
    assert marker in dead.body.decode()


async def test_unknown_tool_goes_to_dead_letter_queue(
    db_pool, seed, topology, amqp, consumer
) -> None:
    payload = {**make_payload(seed), "tools": ["no-such-tool"]}
    await publish(amqp, topology, json.dumps(payload).encode())

    async def find_dead():
        msg = await (await amqp.get_queue(topology.dead_queue)).get(fail=False)
        if msg is not None:
            await msg.ack()
        return msg

    dead = await poll(find_dead)
    assert json.loads(dead.body)["source"] == seed.source

    # And nothing was committed for it.
    async with db_pool.connection() as conn:
        cur = await conn.execute("SELECT count(*) FROM posts WHERE source = %s", (seed.source,))
        row = await cur.fetchone()
        assert row is not None and row[0] == 0
