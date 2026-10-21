"""Питомец пары: вылупляется, когда пара собрана; шкалы характера двигают выборы в посланиях.

Шкалы никогда не убывают. Стадии и косметика — этап 3.
"""

from collections.abc import Mapping
from datetime import datetime

import asyncpg

from app.store import pets


async def hatch(conn: asyncpg.Connection, pair_id: int) -> None:
    """Питомец появляется, когда пара собрана. Повторный вызов ничего не меняет."""
    await pets.create(conn, pair_id)


async def hatched_at(conn: asyncpg.Connection, pair_id: int) -> datetime | None:
    return await pets.created_at(conn, pair_id)


async def traits(conn: asyncpg.Connection, pair_id: int) -> dict[str, int]:
    return await pets.traits(conn, pair_id)


async def shift(conn: asyncpg.Connection, pair_id: int, deltas: Mapping[str, int]) -> None:
    if any(delta < 0 for delta in deltas.values()):
        raise ValueError("шкалы питомца не убывают")
    await pets.shift(conn, pair_id, deltas)
