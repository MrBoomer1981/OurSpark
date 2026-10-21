"""SQL пар."""

from dataclasses import dataclass
from datetime import datetime

import asyncpg


@dataclass(frozen=True)
class Pair:
    id: int
    invite_code: str
    completed_at: datetime | None
    closed_at: datetime | None


_COLUMNS = "id, invite_code, completed_at, closed_at"


def _pair(row: asyncpg.Record) -> Pair:
    return Pair(row["id"], row["invite_code"], row["completed_at"], row["closed_at"])


async def create(conn: asyncpg.Connection, invite_code: str) -> Pair:
    row = await conn.fetchrow(
        f"INSERT INTO pairs (invite_code) VALUES ($1) RETURNING {_COLUMNS}", invite_code
    )
    return _pair(row)


async def get(conn: asyncpg.Connection, pair_id: int, *, lock: bool = False) -> Pair | None:
    sql = f"SELECT {_COLUMNS} FROM pairs WHERE id = $1"
    row = await conn.fetchrow(sql + " FOR UPDATE" if lock else sql, pair_id)
    return _pair(row) if row else None


async def by_code(conn: asyncpg.Connection, invite_code: str, *, lock: bool = False) -> Pair | None:
    sql = f"SELECT {_COLUMNS} FROM pairs WHERE invite_code = $1"
    row = await conn.fetchrow(sql + " FOR UPDATE" if lock else sql, invite_code)
    return _pair(row) if row else None


async def mark_complete(conn: asyncpg.Connection, pair_id: int) -> None:
    await conn.execute(
        "UPDATE pairs SET completed_at = now() WHERE id = $1 AND completed_at IS NULL", pair_id
    )


async def close(conn: asyncpg.Connection, pair_id: int) -> None:
    await conn.execute("UPDATE pairs SET closed_at = now() WHERE id = $1 AND closed_at IS NULL", pair_id)
