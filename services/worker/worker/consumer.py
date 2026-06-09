"""RabbitMQ consumer: pull message -> analyze -> write to Postgres -> ack.

Error routing is two-way: a :class:`~worker.messages.PermanentError` (bad
payload, unknown tool) is rejected without requeue and lands in the dead-letter
queue for inspection; anything else is treated as transient (DB down, network
blip), nacked back onto the queue, and retried after a damper sleep so an
outage does not become a hot redelivery loop.
"""

import asyncio
import logging

import aio_pika
from aio_pika.abc import AbstractChannel, AbstractIncomingMessage, AbstractQueue
from lib_db import create_pool
from psycopg_pool import AsyncConnectionPool

from worker.messages import PermanentError, parse_post_message
from worker.processing import Analyzer, process_message

logger = logging.getLogger(__name__)

QUEUE_NAME = "posts.to_analyze"
DLX_NAME = "posts.dlx"
DEAD_QUEUE_NAME = "posts.to_analyze.dead"
_DEAD_ROUTING_KEY = "dead"

# Seconds to wait after a transient failure before the nacked message is
# retried; with prefetch=1 the same message redelivers immediately otherwise.
TRANSIENT_RETRY_DELAY = 5.0


async def declare_topology(channel: AbstractChannel) -> tuple[AbstractQueue, AbstractQueue]:
    """Declare queue + dead-letter exchange/queue. Idempotent; safe anywhere."""
    dlx = await channel.declare_exchange(DLX_NAME, aio_pika.ExchangeType.DIRECT, durable=True)
    dead_queue = await channel.declare_queue(DEAD_QUEUE_NAME, durable=True)
    await dead_queue.bind(dlx, routing_key=_DEAD_ROUTING_KEY)
    queue = await channel.declare_queue(
        QUEUE_NAME,
        durable=True,
        arguments={
            "x-dead-letter-exchange": DLX_NAME,
            "x-dead-letter-routing-key": _DEAD_ROUTING_KEY,
        },
    )
    return queue, dead_queue


async def handle_message(
    message: AbstractIncomingMessage,
    pool: AsyncConnectionPool,
    analyzer: Analyzer,
) -> None:
    try:
        msg = parse_post_message(message.body)
        async with pool.connection() as conn, conn.transaction():
            await process_message(conn, msg, analyzer)
    except PermanentError:
        logger.exception("dead-lettering unprocessable message")
        await message.reject(requeue=False)
    except Exception:
        logger.exception("transient failure; requeueing after %.0fs", TRANSIENT_RETRY_DELAY)
        await asyncio.sleep(TRANSIENT_RETRY_DELAY)
        await message.nack(requeue=True)
    else:
        await message.ack()
        logger.info("processed message from %s", message.routing_key)


async def run_consumer(amqp_url: str, dsn: str, analyzer: Analyzer) -> None:
    """Consume until cancelled. Owns the DB pool and AMQP connection."""
    pool = create_pool(dsn)
    await pool.open()
    try:
        connection = await aio_pika.connect_robust(amqp_url)
        async with connection:
            channel = await connection.channel()
            # One unacked message at a time: inference is CPU-bound, so there
            # is nothing to gain from buffering work in the consumer.
            await channel.set_qos(prefetch_count=1)
            queue, _ = await declare_topology(channel)
            logger.info("consuming from %s", QUEUE_NAME)
            async with queue.iterator() as messages:
                async for message in messages:
                    await handle_message(message, pool, analyzer)
    finally:
        await pool.close()
