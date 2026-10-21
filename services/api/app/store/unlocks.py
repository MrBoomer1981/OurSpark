"""SQL того, что открыла пара: стадии, привычки, предметы, реликвии — по ключу на пару."""

import asyncpg


async def add(conn: asyncpg.Connection, pair_id: int, key: str) -> bool:
    """Открывает. Уже открытое — ничего, и возвращает False."""
    inserted = await conn.fetchval(
        "INSERT INTO unlocks (pair_id, key) VALUES ($1, $2) ON CONFLICT DO NOTHING RETURNING 1", pair_id, key
    )
    return inserted is not None


async def has(conn: asyncpg.Connection, pair_id: int, key: str) -> bool:
    return bool(await conn.fetchval("SELECT 1 FROM unlocks WHERE pair_id = $1 AND key = $2", pair_id, key))


async def keys(conn: asyncpg.Connection, pair_id: int) -> set[str]:
    return {row["key"] for row in await conn.fetch("SELECT key FROM unlocks WHERE pair_id = $1", pair_id)}


async def reset(conn: asyncpg.Connection, pair_id: int) -> None:
    """Только для отладки."""
    await conn.execute("DELETE FROM unlocks WHERE pair_id = $1", pair_id)
