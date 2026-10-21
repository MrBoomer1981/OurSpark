"""SQL питомца."""

from collections.abc import Mapping
from datetime import datetime

import asyncpg

# Шкалы — колонки таблицы pets; их ключи совпадают с ключами в content/pet.yaml.
TRAITS = ("curiosity", "mischief", "tenderness", "courage")


async def create(conn: asyncpg.Connection, pair_id: int) -> None:
    await conn.execute("INSERT INTO pets (pair_id) VALUES ($1) ON CONFLICT DO NOTHING", pair_id)


async def created_at(conn: asyncpg.Connection, pair_id: int) -> datetime | None:
    return await conn.fetchval("SELECT created_at FROM pets WHERE pair_id = $1", pair_id)


async def traits(conn: asyncpg.Connection, pair_id: int) -> dict[str, int]:
    row = await conn.fetchrow(f"SELECT {', '.join(TRAITS)} FROM pets WHERE pair_id = $1", pair_id)
    return {trait: row[trait] for trait in TRAITS} if row else dict.fromkeys(TRAITS, 0)


async def shift(conn: asyncpg.Connection, pair_id: int, deltas: Mapping[str, int]) -> None:
    """Сдвигает шкалы. Имена колонок — только из TRAITS, значения — параметрами."""
    unknown = set(deltas) - set(TRAITS)
    if unknown:
        raise ValueError(f"неизвестные шкалы: {sorted(unknown)}")
    if not deltas:
        return
    names = list(deltas)
    assignments = ", ".join(f"{name} = {name} + ${index}" for index, name in enumerate(names, start=2))
    await conn.execute(f"UPDATE pets SET {assignments} WHERE pair_id = $1", pair_id, *(deltas[n] for n in names))
