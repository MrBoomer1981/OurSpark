"""SQL питомца: шкалы и надетая косметика."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

import asyncpg

# Шкалы — колонки таблицы pets; их ключи совпадают с ключами в content/pet.yaml.
TRAITS = ("curiosity", "mischief", "tenderness", "courage")


@dataclass(frozen=True)
class Pet:
    created_at: datetime
    traits: dict[str, int]
    equipped: dict[str, str]  # слот → ключ предмета


async def create(conn: asyncpg.Connection, pair_id: int) -> None:
    await conn.execute("INSERT INTO pets (pair_id) VALUES ($1) ON CONFLICT DO NOTHING", pair_id)


async def created_at(conn: asyncpg.Connection, pair_id: int) -> datetime | None:
    return await conn.fetchval("SELECT created_at FROM pets WHERE pair_id = $1", pair_id)


async def get(conn: asyncpg.Connection, pair_id: int, *, lock: bool = False) -> Pet | None:
    sql = f"SELECT created_at, equipped, {', '.join(TRAITS)} FROM pets WHERE pair_id = $1"
    row = await conn.fetchrow(sql + " FOR UPDATE" if lock else sql, pair_id)
    if row is None:
        return None
    return Pet(row["created_at"], {trait: row[trait] for trait in TRAITS}, row["equipped"])


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


async def wear(conn: asyncpg.Connection, pair_id: int, slot: str, item: str) -> None:
    """Надевает предмет в слот; что было в слоте — снимается."""
    await conn.execute(
        "UPDATE pets SET equipped = equipped || jsonb_build_object($2::text, $3::text) WHERE pair_id = $1",
        pair_id,
        slot,
        item,
    )


async def take_off(conn: asyncpg.Connection, pair_id: int, slot: str, item: str) -> None:
    """Снимает предмет, если он ещё в слоте: встречное «надеть другое» не потеряется."""
    await conn.execute(
        "UPDATE pets SET equipped = equipped - $2::text WHERE pair_id = $1 AND equipped ->> $2::text = $3",
        pair_id,
        slot,
        item,
    )


async def reset(conn: asyncpg.Connection, pair_id: int) -> None:
    """Только для отладки: шкалы в ноль, косметика снята."""
    zeros = ", ".join(f"{trait} = 0" for trait in TRAITS)
    await conn.execute(f"UPDATE pets SET {zeros}, equipped = '{{}}' WHERE pair_id = $1", pair_id)
