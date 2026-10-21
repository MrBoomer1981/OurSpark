"""SQL питомца."""

from datetime import datetime

import asyncpg


async def create(conn: asyncpg.Connection, pair_id: int) -> None:
    await conn.execute("INSERT INTO pets (pair_id) VALUES ($1) ON CONFLICT DO NOTHING", pair_id)


async def created_at(conn: asyncpg.Connection, pair_id: int) -> datetime | None:
    return await conn.fetchval("SELECT created_at FROM pets WHERE pair_id = $1", pair_id)
