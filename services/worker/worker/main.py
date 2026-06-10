"""Worker entrypoint: load the model once, then consume until terminated.

Run as ``python -m worker.main``.
"""

import asyncio
import logging
import os

from worker.consumer import run_consumer
from worker.sentiment import SentimentAnalyzer

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgres://vibecheck:vibecheck@127.0.0.1:5432/vibecheck?sslmode=disable",
)
AMQP_URL = os.environ.get("AMQP_URL", "amqp://vibecheck:vibecheck@127.0.0.1:5672/")


def main() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    analyzer = SentimentAnalyzer()
    asyncio.run(run_consumer(AMQP_URL, DATABASE_URL, analyzer))


if __name__ == "__main__":
    main()
