"""Подключение к Postgres и применение миграций."""

import json

import asyncpg
from loguru import logger

from app.store.migrations import MIGRATIONS

# Ключ advisory-лока на время миграций. Во время деплоя стартуют две копии api,
# и применить миграции должна ровно одна: вторая дождётся лока и увидит, что всё сделано.
MIGRATION_LOCK = 20261020


async def _init_connection(conn: asyncpg.Connection) -> None:
    # jsonb туда и обратно — обычные dict, а не строки.
    await conn.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")


async def connect(database_url: str) -> asyncpg.Pool:
    pool = await asyncpg.create_pool(database_url, min_size=1, max_size=10, init=_init_connection)
    version = await migrate(pool)
    logger.info("База: схема v{}", version)
    return pool


async def migrate(pool: asyncpg.Pool) -> int:
    """Применяет недостающие миграции одной транзакцией и возвращает номер схемы."""
    async with pool.acquire() as conn, conn.transaction():
        await conn.execute("SELECT pg_advisory_xact_lock($1)", MIGRATION_LOCK)
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            " version integer PRIMARY KEY,"
            " applied_at timestamptz NOT NULL DEFAULT now())"
        )
        current = await conn.fetchval("SELECT coalesce(max(version), 0) FROM schema_migrations")
        for version, script in enumerate(MIGRATIONS[current:], start=current + 1):
            await conn.execute(script)
            await conn.execute("INSERT INTO schema_migrations (version) VALUES ($1)", version)
            logger.info("База: применена миграция {}", version)
    return max(current, len(MIGRATIONS))
