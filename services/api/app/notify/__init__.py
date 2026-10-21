"""Уведомления. Пишутся в outbox в той же транзакции, что и событие; отправляет их relay."""

from typing import Any

import asyncpg

from app.store import outbox

# Виды уведомлений. Текст каждого — в app/texts.py, отрисовка — в relay.render.
PARTNER_JOINED = "partner_joined"


async def enqueue(conn: asyncpg.Connection, user_id: int, kind: str, payload: dict[str, Any], *, key: str) -> None:
    """Ставит уведомление в очередь ровно один раз: второе с тем же ключом не появится."""
    await outbox.add(conn, user_id, kind, payload, key)
