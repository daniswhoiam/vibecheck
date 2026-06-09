from lib_db import queries


async def test_seed_inserts_and_is_queryable(db_pool, seeded) -> None:
    async with db_pool.connection() as conn:
        tool = await queries.get_tool_by_slug(conn, slug=seeded.slug)
        assert tool is not None
        cur = await conn.execute("SELECT count(*) FROM posts WHERE source = %s", (seeded.source,))
        row = await cur.fetchone()
        assert row is not None
        assert row[0] == 4
