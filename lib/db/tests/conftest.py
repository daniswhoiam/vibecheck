import os

import pytest
from lib_db import create_pool

DSN = os.environ.get(
    "DATABASE_URL",
    "postgres://vibecheck:vibecheck@127.0.0.1:5432/vibecheck?sslmode=disable",
)


@pytest.fixture
async def conn():
    pool = create_pool(DSN)
    await pool.open()
    async with pool.connection() as c:
        yield c
    await pool.close()
