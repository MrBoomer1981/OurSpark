"""Награды. Искры — общий кошелёк пары; начисляет и списывает только сервер, ровно один раз на событие.

Значения стартовые: баланс подбираем на этапе 4.
"""

import secrets

import asyncpg

from app.store import rewards

ANSWER_SPARKS = 5  # за свой ответ на послание
REVEAL_SPARKS = 10  # паре — за открытый результат
DEBUG_SPARKS = 100  # кнопка отладочной панели


async def for_answer(conn: asyncpg.Connection, pair_id: int, user_id: int, session_id: int) -> None:
    await rewards.grant(conn, pair_id, user_id, f"answer:{session_id}:{user_id}", ANSWER_SPARKS)


async def for_reveal(conn: asyncpg.Connection, pair_id: int, session_id: int) -> None:
    await rewards.grant(conn, pair_id, None, f"reveal:{session_id}", REVEAL_SPARKS)


async def for_debug(conn: asyncpg.Connection, pair_id: int, user_id: int) -> None:
    """Только для отладки: у каждого нажатия свой ключ, поэтому каждое начисляет."""
    await rewards.grant(conn, pair_id, user_id, f"debug:{pair_id}:{secrets.token_hex(8)}", DEBUG_SPARKS)


async def spend(conn: asyncpg.Connection, pair_id: int, user_id: int, event_key: str, price: int) -> bool:
    """Тратит искры. Не хватает или по этому ключу уже потрачено — ничего не списывает и возвращает False.

    Звать под блокировкой строки питомца: тогда две траты одной пары идут по очереди
    и не пройдут обе на одни и те же искры.
    """
    if await rewards.balance(conn, pair_id) < price:
        return False
    return await rewards.grant(conn, pair_id, user_id, event_key, -price)


async def balance(conn: asyncpg.Connection, pair_id: int) -> int:
    return await rewards.balance(conn, pair_id)


async def earned(conn: asyncpg.Connection, pair_id: int) -> int:
    """Заработано за всё время, без трат: по этой сумме растёт питомец."""
    return await rewards.earned(conn, pair_id)
