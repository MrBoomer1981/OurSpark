"""SQL посланий дня и ответов на них."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import asyncpg


@dataclass(frozen=True)
class Session:
    id: int
    pair_id: int
    day: date
    prompt_key: str
    completed_at: datetime | None
    completed_on: date | None
    result: dict[str, Any] | None


@dataclass(frozen=True)
class Answer:
    user_id: int
    answer: str
    created_at: datetime
    result_seen_at: datetime | None


_COLUMNS = "id, pair_id, day, prompt_key, completed_at, completed_on, result"


def _session(row: asyncpg.Record) -> Session:
    return Session(
        row["id"], row["pair_id"], row["day"], row["prompt_key"], row["completed_at"], row["completed_on"], row["result"]
    )


async def latest(conn: asyncpg.Connection, pair_id: int) -> Session | None:
    row = await conn.fetchrow(
        f"SELECT {_COLUMNS} FROM prompt_sessions WHERE pair_id = $1 ORDER BY day DESC LIMIT 1", pair_id
    )
    return _session(row) if row else None


async def get(conn: asyncpg.Connection, session_id: int, *, lock: bool = False) -> Session | None:
    sql = f"SELECT {_COLUMNS} FROM prompt_sessions WHERE id = $1"
    row = await conn.fetchrow(sql + " FOR UPDATE" if lock else sql, session_id)
    return _session(row) if row else None


async def create(conn: asyncpg.Connection, pair_id: int, day: date, prompt_key: str) -> None:
    """Назначает послание на день. Если кто-то из пары успел первым, остаётся его послание."""
    await conn.execute(
        "INSERT INTO prompt_sessions (pair_id, day, prompt_key) VALUES ($1, $2, $3)"
        " ON CONFLICT (pair_id, day) DO NOTHING",
        pair_id,
        day,
        prompt_key,
    )


async def used_keys(conn: asyncpg.Connection, pair_id: int) -> list[tuple[str, bool]]:
    """Карточки, которые уже были у пары, от новых к старым: ключ и завершена ли."""
    rows = await conn.fetch(
        "SELECT prompt_key, completed_at IS NOT NULL AS completed FROM prompt_sessions"
        " WHERE pair_id = $1 ORDER BY day DESC",
        pair_id,
    )
    return [(row["prompt_key"], row["completed"]) for row in rows]


async def answers(conn: asyncpg.Connection, session_id: int) -> dict[int, Answer]:
    rows = await conn.fetch(
        "SELECT user_id, answer, created_at, result_seen_at FROM answers WHERE session_id = $1", session_id
    )
    return {row["user_id"]: Answer(row["user_id"], row["answer"], row["created_at"], row["result_seen_at"]) for row in rows}


async def add_answer(conn: asyncpg.Connection, session_id: int, user_id: int, answer: str) -> bool:
    """Записывает ответ. Повторная отправка ничего не меняет и возвращает False."""
    inserted = await conn.fetchval(
        "INSERT INTO answers (session_id, user_id, answer) VALUES ($1, $2, $3)"
        " ON CONFLICT (session_id, user_id) DO NOTHING RETURNING 1",
        session_id,
        user_id,
        answer,
    )
    return inserted is not None


async def complete(conn: asyncpg.Connection, session_id: int, day: date, result: dict[str, Any]) -> bool:
    """Бронь раскрытия: только первый вызов получает True."""
    claimed = await conn.fetchval(
        "UPDATE prompt_sessions SET completed_at = now(), completed_on = $2, result = $3"
        " WHERE id = $1 AND completed_at IS NULL RETURNING 1",
        session_id,
        day,
        result,
    )
    return claimed is not None


async def mark_seen(conn: asyncpg.Connection, session_id: int, user_id: int) -> None:
    await conn.execute(
        "UPDATE answers SET result_seen_at = now()"
        " WHERE session_id = $1 AND user_id = $2 AND result_seen_at IS NULL",
        session_id,
        user_id,
    )
