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
    answer: str | None  # ключ варианта; None — ответ текстом
    text: str | None  # свободный ответ
    prediction: str | None  # «Угадай партнёра»: какой вариант выберет партнёр
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


async def create(conn: asyncpg.Connection, pair_id: int, day: date, prompt_key: str) -> bool:
    """Назначает послание на день. Если кто-то из пары успел первым, остаётся его послание и возвращает False."""
    inserted = await conn.fetchval(
        "INSERT INTO prompt_sessions (pair_id, day, prompt_key) VALUES ($1, $2, $3)"
        " ON CONFLICT (pair_id, day) DO NOTHING RETURNING 1",
        pair_id,
        day,
        prompt_key,
    )
    return inserted is not None


async def replace(conn: asyncpg.Connection, session: Session, prompt_key: str) -> None:
    """Другая карточка вместо послания без ответов: старое удаляется, новое получает новый id и тот же день."""
    await conn.execute("DELETE FROM prompt_sessions WHERE id = $1", session.id)
    await conn.execute(
        "INSERT INTO prompt_sessions (pair_id, day, prompt_key) VALUES ($1, $2, $3)",
        session.pair_id,
        session.day,
        prompt_key,
    )


async def log(conn: asyncpg.Connection, pair_id: int, day: date, prompt_key: str, *, changed: bool) -> None:
    """Журнал показов: каждая карточка, которую пара увидела, в том числе сменённая."""
    await conn.execute(
        "INSERT INTO prompt_log (pair_id, day, prompt_key, changed) VALUES ($1, $2, $3, $4)",
        pair_id,
        day,
        prompt_key,
        changed,
    )


async def shown_today(conn: asyncpg.Connection, pair_id: int, day: date) -> tuple[set[str], int]:
    """Карточки, показанные паре в этот день, и сколько раз за день послание сменили."""
    rows = await conn.fetch("SELECT prompt_key, changed FROM prompt_log WHERE pair_id = $1 AND day = $2", pair_id, day)
    return {row["prompt_key"] for row in rows}, sum(1 for row in rows if row["changed"])


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
        "SELECT user_id, answer, text, prediction, created_at, result_seen_at FROM answers WHERE session_id = $1",
        session_id,
    )
    return {
        row["user_id"]: Answer(
            row["user_id"], row["answer"], row["text"], row["prediction"], row["created_at"], row["result_seen_at"]
        )
        for row in rows
    }


async def add_answer(
    conn: asyncpg.Connection,
    session_id: int,
    user_id: int,
    answer: str | None,
    text: str | None,
    prediction: str | None,
) -> bool:
    """Записывает ответ вместе с прогнозом. Повторная отправка ничего не меняет и возвращает False."""
    inserted = await conn.fetchval(
        "INSERT INTO answers (session_id, user_id, answer, text, prediction) VALUES ($1, $2, $3, $4, $5)"
        " ON CONFLICT (session_id, user_id) DO NOTHING RETURNING 1",
        session_id,
        user_id,
        answer,
        text,
        prediction,
    )
    return inserted is not None


async def completed_keys(conn: asyncpg.Connection, pair_id: int) -> set[str]:
    """Карточки, которые пара завершила хотя бы раз."""
    rows = await conn.fetch(
        "SELECT DISTINCT prompt_key FROM prompt_sessions WHERE pair_id = $1 AND completed_at IS NOT NULL", pair_id
    )
    return {row["prompt_key"] for row in rows}


async def claim(conn: asyncpg.Connection, session_id: int, day: date) -> bool:
    """Бронь раскрытия: только первый вызов получает True."""
    claimed = await conn.fetchval(
        "UPDATE prompt_sessions SET completed_at = now(), completed_on = $2"
        " WHERE id = $1 AND completed_at IS NULL RETURNING 1",
        session_id,
        day,
    )
    return claimed is not None


async def save_result(conn: asyncpg.Connection, session_id: int, result: dict[str, Any]) -> None:
    await conn.execute("UPDATE prompt_sessions SET result = $2 WHERE id = $1", session_id, result)


async def mark_seen(conn: asyncpg.Connection, session_id: int, user_id: int) -> None:
    await conn.execute(
        "UPDATE answers SET result_seen_at = now()"
        " WHERE session_id = $1 AND user_id = $2 AND result_seen_at IS NULL",
        session_id,
        user_id,
    )


async def delete(conn: asyncpg.Connection, session_id: int) -> None:
    """Только для отладки: послание и ответы на него."""
    await conn.execute("DELETE FROM answers WHERE session_id = $1", session_id)
    await conn.execute("DELETE FROM prompt_sessions WHERE id = $1", session_id)


async def delete_pair(conn: asyncpg.Connection, pair_id: int) -> None:
    """Только для отладки: все послания пары, ответы на них и журнал показов."""
    await conn.execute(
        "DELETE FROM answers WHERE session_id IN (SELECT id FROM prompt_sessions WHERE pair_id = $1)", pair_id
    )
    await conn.execute("DELETE FROM prompt_sessions WHERE pair_id = $1", pair_id)
    await conn.execute("DELETE FROM prompt_log WHERE pair_id = $1", pair_id)
