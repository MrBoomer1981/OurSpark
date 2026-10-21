"""SQL настроек пары: строки «ключ — значение», новой настройке миграция не нужна."""

import asyncpg


async def get(conn: asyncpg.Connection, pair_id: int, key: str) -> str | None:
    return await conn.fetchval("SELECT value FROM pair_settings WHERE pair_id = $1 AND key = $2", pair_id, key)


async def put(conn: asyncpg.Connection, pair_id: int, key: str, value: str) -> None:
    await conn.execute(
        "INSERT INTO pair_settings (pair_id, key, value) VALUES ($1, $2, $3)"
        " ON CONFLICT (pair_id, key) DO UPDATE SET value = EXCLUDED.value",
        pair_id,
        key,
        value,
    )
