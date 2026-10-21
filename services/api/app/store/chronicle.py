"""SQL летописи. У записи — ключ события, уникальный в паре: повтор не допишет вторую."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import asyncpg


@dataclass(frozen=True)
class Entry:
    id: int
    kind: str
    data: dict[str, Any]
    created_at: datetime


async def add(conn: asyncpg.Connection, pair_id: int, event_key: str, kind: str, data: dict[str, Any]) -> bool:
    inserted = await conn.fetchval(
        "INSERT INTO chronicle (pair_id, event_key, kind, data) VALUES ($1, $2, $3, $4)"
        " ON CONFLICT (pair_id, event_key) DO NOTHING RETURNING 1",
        pair_id,
        event_key,
        kind,
        data,
    )
    return inserted is not None


async def entries(conn: asyncpg.Connection, pair_id: int) -> list[Entry]:
    """Записи пары от новых к старым."""
    rows = await conn.fetch(
        "SELECT id, kind, data, created_at FROM chronicle WHERE pair_id = $1 ORDER BY id DESC", pair_id
    )
    return [Entry(row["id"], row["kind"], row["data"], row["created_at"]) for row in rows]


async def reset(conn: asyncpg.Connection, pair_id: int, keep: str) -> None:
    """Только для отладки: стирает записи пары, кроме записи с ключом keep."""
    await conn.execute("DELETE FROM chronicle WHERE pair_id = $1 AND event_key <> $2", pair_id, keep)
