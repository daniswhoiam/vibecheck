"""End-to-end consumer tests: real RabbitMQ in, real Postgres out.

Each test runs the consumer as a background task with the stub analyzer,
publishes to the real queue, and polls for the observable outcome (a DB row or
a dead-lettered message). Queues are purged between tests for isolation.
"""

import asyncio
import contextlib
import json
import os
import uuid

import aio_pika
import pytest
from worker.consumer import DEAD_QUEUE_NAME, QUEUE_NAME, declare_topology, run_consumer

from .conftest import DSN, StubAnalyzer

AMQP_URL = os.environ.get("AMQP_URL", "amqp://vibecheck:vibecheck@127.0.0.1:5672/")


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
async def amqp():
    connection = await aio_pika.connect(AMQP_URL)
    channel = await connection.channel()
    queue, dead_queue = await declare_topology(channel)
    await queue.purge()
    await dead_queue.purge()
    yield channel
    await connection.close()


@pytest.fixture
async def consumer():
    task = asyncio.create_task(run_consumer(AMQP_URL, DSN, StubAnalyzer()))
    yield task
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


async def publish(channel, body: bytes) -> None:
    await channel.default_exchange.publish(
        aio_pika.Message(body=body, delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
        routing_key=QUEUE_NAME,
    )


async def poll(predicate, timeout: float = 15.0):
    async with asyncio.timeout(timeout):
        while True:
            result = await predicate()
            if result is not None:
                return result
            await asyncio.sleep(0.1)


async def test_published_message_lands_in_postgres(db_pool, seed, amqp, consumer) -> None:
    await publish(amqp, json.dumps(make_payload(seed)).encode())

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


async def test_malformed_message_goes_to_dead_letter_queue(amqp, consumer) -> None:
    marker = uuid.uuid4().hex
    await publish(amqp, f"not json {marker}".encode())

    async def find_dead():
        msg = await (await amqp.get_queue(DEAD_QUEUE_NAME)).get(fail=False)
        if msg is not None:
            await msg.ack()
        return msg

    dead = await poll(find_dead)
    assert marker in dead.body.decode()


async def test_unknown_tool_goes_to_dead_letter_queue(db_pool, seed, amqp, consumer) -> None:
    payload = {**make_payload(seed), "tools": ["no-such-tool"]}
    await publish(amqp, json.dumps(payload).encode())

    async def find_dead():
        msg = await (await amqp.get_queue(DEAD_QUEUE_NAME)).get(fail=False)
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
