"""Уведомления. Пишутся в outbox в той же транзакции, что и событие; отправляет их relay.

Канал выбирает relay: web push, если у человека есть рабочая подписка, иначе сообщение бота.
"""

from typing import Any

import asyncpg

from app.store import outbox

# Виды уведомлений. Тексты — в app/texts.py, отрисовка — в relay.render.
PARTNER_JOINED = "partner_joined"
PARTNER_ANSWERED = "partner_answered"  # партнёр ответил — твоя очередь
RESULT_READY = "result_ready"  # ответили оба — тому, кто ответил первым


async def enqueue(conn: asyncpg.Connection, user_id: int, kind: str, payload: dict[str, Any], *, key: str) -> None:
    """Ставит уведомление в очередь ровно один раз: второе с тем же ключом не появится."""
    await outbox.add(conn, user_id, kind, payload, key)
