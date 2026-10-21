"""Награды. Искры — общий кошелёк пары; начисляет только сервер и ровно один раз на событие.

Значения стартовые: баланс подбираем на этапе 4.
"""

import asyncpg

from app.store import rewards

ANSWER_SPARKS = 5  # за свой ответ на послание
REVEAL_SPARKS = 10  # паре — за открытый результат


async def for_answer(conn: asyncpg.Connection, pair_id: int, user_id: int, session_id: int) -> None:
    await rewards.grant(conn, pair_id, user_id, f"answer:{session_id}:{user_id}", ANSWER_SPARKS)


async def for_reveal(conn: asyncpg.Connection, pair_id: int, session_id: int) -> None:
    await rewards.grant(conn, pair_id, None, f"reveal:{session_id}", REVEAL_SPARKS)


async def balance(conn: asyncpg.Connection, pair_id: int) -> int:
    return await rewards.balance(conn, pair_id)
