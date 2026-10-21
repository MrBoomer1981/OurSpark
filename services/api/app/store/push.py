"""SQL подписок на web push."""

from dataclasses import dataclass

import asyncpg


@dataclass(frozen=True)
class Subscription:
    endpoint: str
    keys: dict[str, str]  # p256dh и auth из PushSubscription браузера


async def save(conn: asyncpg.Connection, user_id: int, endpoint: str, keys: dict[str, str]) -> None:
    """Подписка этого браузера. Тот же endpoint заново — снова рабочая и принадлежит этому человеку."""
    await conn.execute(
        "INSERT INTO push_subs (endpoint, user_id, keys) VALUES ($1, $2, $3)"
        " ON CONFLICT (endpoint) DO UPDATE SET user_id = EXCLUDED.user_id, keys = EXCLUDED.keys, failed_at = NULL",
        endpoint,
        user_id,
        keys,
    )


async def active(conn: asyncpg.Connection, user_id: int) -> list[Subscription]:
    rows = await conn.fetch(
        "SELECT endpoint, keys FROM push_subs WHERE user_id = $1 AND failed_at IS NULL", user_id
    )
    return [Subscription(row["endpoint"], row["keys"]) for row in rows]


async def mark_failed(conn: asyncpg.Connection, endpoint: str) -> None:
    await conn.execute("UPDATE push_subs SET failed_at = now() WHERE endpoint = $1", endpoint)
