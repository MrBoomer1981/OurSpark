"""SQL людей: кто есть кто и в какой паре."""

from dataclasses import dataclass

import asyncpg


@dataclass(frozen=True)
class User:
    id: int
    name: str
    pair_id: int | None
    tg_reachable: bool | None  # None — боту ещё не писали; False — Telegram отказал


_COLUMNS = "user_id, name, pair_id, tg_reachable"


def _user(row: asyncpg.Record) -> User:
    return User(row["user_id"], row["name"], row["pair_id"], row["tg_reachable"])


async def get(conn: asyncpg.Connection, user_id: int, *, lock: bool = False) -> User | None:
    sql = f"SELECT {_COLUMNS} FROM users WHERE user_id = $1"
    row = await conn.fetchrow(sql + " FOR UPDATE" if lock else sql, user_id)
    return _user(row) if row else None


async def ensure(conn: asyncpg.Connection, user_id: int, name: str) -> User:
    """Человек с таким id: заводит нового и обновляет имя, если оно сменилось в Telegram."""
    user = await get(conn, user_id)
    if user is not None and user.name == name:
        return user
    row = await conn.fetchrow(
        "INSERT INTO users (user_id, name) VALUES ($1, $2)"
        " ON CONFLICT (user_id) DO UPDATE SET name = EXCLUDED.name"
        f" RETURNING {_COLUMNS}",
        user_id,
        name,
    )
    return _user(row)


async def members(conn: asyncpg.Connection, pair_id: int) -> list[User]:
    rows = await conn.fetch(f"SELECT {_COLUMNS} FROM users WHERE pair_id = $1 ORDER BY created_at", pair_id)
    return [_user(row) for row in rows]


async def set_pair(conn: asyncpg.Connection, user_id: int, pair_id: int) -> None:
    await conn.execute("UPDATE users SET pair_id = $2 WHERE user_id = $1", user_id, pair_id)


async def release_pair(conn: asyncpg.Connection, pair_id: int) -> None:
    """Все участники пары снова ни в какой паре."""
    await conn.execute("UPDATE users SET pair_id = NULL WHERE pair_id = $1", pair_id)


async def set_reachable(conn: asyncpg.Connection, user_id: int, reachable: bool) -> None:
    await conn.execute(
        "UPDATE users SET tg_reachable = $2 WHERE user_id = $1 AND tg_reachable IS DISTINCT FROM $2",
        user_id,
        reachable,
    )
