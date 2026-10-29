"""SQL событий для метрик: ключ события уникален, повтор не допишет вторую запись."""

from datetime import date
from typing import Any

import asyncpg


async def add(
    conn: asyncpg.Connection, pair_id: int, user_id: int, kind: str, day: date, key: str, data: dict[str, Any]
) -> None:
    await conn.execute(
        "INSERT INTO events (pair_id, user_id, kind, day, key, data) VALUES ($1, $2, $3, $4, $5, $6)"
        " ON CONFLICT (key) DO NOTHING",
        pair_id,
        user_id,
        kind,
        day,
        key,
        data,
    )
