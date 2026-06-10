"""Ingestion entrypoint: fetch -> detect -> publish on a fixed interval.

Run as ``python -m ingestion.main``.

A plain sleep loop, not a scheduler framework: one job, one interval
(APScheduler earns its keep with multiple schedules or cron semantics). A
failed cycle is logged and retried next interval — the service outlives its
dependencies' outages rather than crash-looping on them.
"""

import asyncio
import datetime as dt
import logging
import os
from collections.abc import Sequence

import aio_pika
import httpx
from lib_db import create_pool

from ingestion.hn import fetch_hn_posts
from ingestion.pipeline import Fetcher, run_cycle
from ingestion.posts import FetchedPost
from ingestion.publisher import declare_topology, publish_post
from ingestion.reddit import fetch_reddit_posts, make_reddit

logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgres://vibecheck:vibecheck@127.0.0.1:5432/vibecheck?sslmode=disable",
)
AMQP_URL = os.environ.get("AMQP_URL", "amqp://vibecheck:vibecheck@127.0.0.1:5672/")
INTERVAL = dt.timedelta(seconds=float(os.environ.get("INGEST_INTERVAL_SECONDS", "300")))
LOOKBACK = dt.timedelta(seconds=float(os.environ.get("INGEST_LOOKBACK_SECONDS", "3600")))
SUBREDDITS = [
    s.strip()
    for s in os.environ.get(
        "REDDIT_SUBREDDITS",
        "programming,ChatGPTCoding,cursor,GithubCopilot,ClaudeAI,vibecoding",
    ).split(",")
    if s.strip()
]


def build_fetchers(client: httpx.AsyncClient) -> list[Fetcher]:
    async def hn(tool_queries: Sequence[str], since: dt.datetime) -> list[FetchedPost]:
        return await fetch_hn_posts(client, tool_queries, since=since)

    fetchers: list[Fetcher] = [hn]

    client_id = os.environ.get("REDDIT_CLIENT_ID")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET")
    user_agent = os.environ.get("REDDIT_USER_AGENT")
    if client_id and client_secret and user_agent:
        reddit = make_reddit(client_id, client_secret, user_agent)

        async def reddit_fetch(
            tool_queries: Sequence[str], since: dt.datetime
        ) -> list[FetchedPost]:
            return await fetch_reddit_posts(reddit, SUBREDDITS, tool_queries, since=since)

        fetchers.append(reddit_fetch)
    else:
        logger.info("REDDIT_* credentials not set; Reddit fetcher disabled")
    return fetchers


async def run() -> None:
    pool = create_pool(DATABASE_URL)
    await pool.open()
    connection = await aio_pika.connect_robust(AMQP_URL)
    try:
        async with connection, httpx.AsyncClient(timeout=30) as client:
            channel = await connection.channel()
            await declare_topology(channel)
            fetchers = build_fetchers(client)

            async def publish(post: FetchedPost, tools: Sequence[str]) -> None:
                await publish_post(channel, post, tools)

            logger.info(
                "ingesting every %ss with a %ss lookback (%d fetchers)",
                INTERVAL.total_seconds(),
                LOOKBACK.total_seconds(),
                len(fetchers),
            )
            while True:
                try:
                    stats = await run_cycle(pool, publish, fetchers, lookback=LOOKBACK)
                    logger.info("cycle done: %s", stats)
                except Exception:
                    logger.exception("cycle failed; retrying next interval")
                await asyncio.sleep(INTERVAL.total_seconds())
    finally:
        await pool.close()


def main() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    asyncio.run(run())


if __name__ == "__main__":
    main()
