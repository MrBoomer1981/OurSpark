"""Питомец пары. Пока он только вылупляется — стадии, шкалы и косметика придут на этапе 3."""

from datetime import datetime

import asyncpg

from app.store import pets


async def hatch(conn: asyncpg.Connection, pair_id: int) -> None:
    """Питомец появляется, когда пара собрана. Повторный вызов ничего не меняет."""
    await pets.create(conn, pair_id)


async def hatched_at(conn: asyncpg.Connection, pair_id: int) -> datetime | None:
    return await pets.created_at(conn, pair_id)
