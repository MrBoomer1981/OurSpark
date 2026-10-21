"""SQL outbox: очередь уведомлений, которые нельзя потерять."""

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import asyncpg

# Бронь, которую не закрыли за это время (копия api упала посреди отправки), снимается.
CLAIM_TIMEOUT = "2 minutes"


@dataclass(frozen=True)
class Message:
    id: int
    user_id: int
    kind: str
    payload: dict[str, Any]
    attempts: int


async def add(
    conn: asyncpg.Connection, user_id: int, kind: str, payload: dict[str, Any], dedup_key: str
) -> None:
    """Ставит уведомление в очередь. Второе с тем же ключом не появится."""
    await conn.execute(
        "INSERT INTO outbox (user_id, kind, payload, dedup_key) VALUES ($1, $2, $3, $4)"
        " ON CONFLICT (dedup_key) DO NOTHING",
        user_id,
        kind,
        payload,
        dedup_key,
    )


async def claim(conn: asyncpg.Connection, limit: int) -> list[Message]:
    """Бронирует созревшие уведомления. Две копии api не получат одно и то же."""
    rows = await conn.fetch(
        "UPDATE outbox SET claimed_at = now(), attempts = attempts + 1"
        " WHERE id IN ("
        "  SELECT id FROM outbox"
        "  WHERE sent_at IS NULL AND failed_at IS NULL AND due_at <= now()"
        f"   AND (claimed_at IS NULL OR claimed_at < now() - interval '{CLAIM_TIMEOUT}')"
        "  ORDER BY id LIMIT $1 FOR UPDATE SKIP LOCKED)"
        " RETURNING id, user_id, kind, payload, attempts",
        limit,
    )
    return [Message(r["id"], r["user_id"], r["kind"], r["payload"], r["attempts"]) for r in rows]


async def mark_sent(conn: asyncpg.Connection, message_id: int) -> None:
    await conn.execute("UPDATE outbox SET sent_at = now(), error = NULL WHERE id = $1", message_id)


async def retry_later(conn: asyncpg.Connection, message_id: int, delay: timedelta, error: str) -> None:
    await conn.execute(
        "UPDATE outbox SET claimed_at = NULL, due_at = now() + $2, error = $3 WHERE id = $1",
        message_id,
        delay,
        error,
    )


async def mark_failed(conn: asyncpg.Connection, message_id: int, error: str) -> None:
    await conn.execute("UPDATE outbox SET failed_at = now(), error = $2 WHERE id = $1", message_id, error)
