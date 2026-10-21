"""Питомец пары: шкалы характера и привычки, стадии роста, косметика, реликвии.

Шкалы никогда не убывают. Всё открытое — стадии, привычки, предметы, реликвии — записывается
в unlocks по ключу на пару: открывается ровно один раз и не пропадает, даже если пороги
в контенте потом поменяются.
"""

from collections.abc import Mapping
from datetime import datetime
from typing import Literal

import asyncpg

from app.content import RELIC_SERIES, Content, Item, Level, Stage, Trait
from app.game import rewards
from app.store import pets, unlocks
from app.store.pets import Pet

STAGE = "stage:"
HABIT = "habit:"
ITEM = "item:"
RELIC = "relic:"

PetErrorCode = Literal["item_unknown", "item_locked", "not_enough_sparks", "item_not_owned"]


class PetError(Exception):
    def __init__(self, code: PetErrorCode) -> None:
        super().__init__(code)
        self.code: PetErrorCode = code


async def hatch(conn: asyncpg.Connection, pair_id: int) -> None:
    """Питомец появляется, когда пара собрана. Повторный вызов ничего не меняет."""
    await pets.create(conn, pair_id)


async def hatched_at(conn: asyncpg.Connection, pair_id: int) -> datetime | None:
    return await pets.created_at(conn, pair_id)


async def get(conn: asyncpg.Connection, pair_id: int) -> Pet | None:
    return await pets.get(conn, pair_id)


async def unlocked(conn: asyncpg.Connection, pair_id: int) -> set[str]:
    return await unlocks.keys(conn, pair_id)


async def shift(conn: asyncpg.Connection, pair_id: int, deltas: Mapping[str, int]) -> None:
    if any(delta < 0 for delta in deltas.values()):
        raise ValueError("шкалы питомца не убывают")
    await pets.shift(conn, pair_id, deltas)


def habit_key(trait: Trait, level: Level) -> str:
    return f"{HABIT}{trait.key}:{level.key}"


def stage(content: Content, opened: set[str]) -> Stage:
    """Текущая стадия — последняя открытая; первая открыта с самого начала."""
    return next(
        (s for s in reversed(content.stages[1:]) if STAGE + s.key in opened),
        content.stages[0],
    )


def reached(content: Content, opened: set[str], key: str) -> bool:
    return key == content.stages[0].key or STAGE + key in opened


def habits(content: Content, opened: set[str]) -> list[tuple[Trait, Level]]:
    """Открытые привычки в порядке шкал и порогов."""
    return [
        (trait, level)
        for trait in content.traits.values()
        for level in trait.levels
        if habit_key(trait, level) in opened
    ]


def available(item: Item, content: Content, opened: set[str], traits: Mapping[str, int]) -> bool:
    """Предмет в продаже: условие выполнено (стадия открыта или шкала дорасла)."""
    requires = item.requires
    if requires is None:
        return True
    if requires.stage is not None:
        return reached(content, opened, requires.stage)
    return requires.trait is not None and traits.get(requires.trait, 0) >= requires.at


async def grow(conn: asyncpg.Connection, pair_id: int, earned: int, content: Content) -> list[Stage]:
    """Открывает стадии, до которых дотянулись заработанные искры. Возвращает только новые."""
    grown = []
    for next_stage in content.stages[1:]:
        if next_stage.sparks <= earned and await unlocks.add(conn, pair_id, STAGE + next_stage.key):
            grown.append(next_stage)
    return grown


async def learn_habits(conn: asyncpg.Connection, pair_id: int, content: Content) -> list[tuple[Trait, Level]]:
    """Открывает привычки, до порогов которых доросли шкалы. Возвращает только новые."""
    values = await pets.traits(conn, pair_id)
    learned = []
    for trait in content.traits.values():
        for level in trait.levels:
            if values.get(trait.key, 0) >= level.at and await unlocks.add(conn, pair_id, habit_key(trait, level)):
                learned.append((trait, level))
    return learned


async def find_relic(conn: asyncpg.Connection, pair_id: int, theme: str, completed: int) -> bool:
    """Реликвия темы — за RELIC_SERIES завершённых посланий этой темы. True — найдена только что."""
    return completed >= RELIC_SERIES and await unlocks.add(conn, pair_id, RELIC + theme)


async def buy(conn: asyncpg.Connection, pair_id: int, user_id: int, item_key: str, content: Content) -> None:
    """Покупка: условие, трата искр и открытие предмета — одной транзакцией. Купленное сразу надевается.

    Строка питомца под блокировкой: покупки пары идут по очереди, поэтому повторное нажатие
    ничего не спишет, а две покупки на последние искры не пройдут обе.
    """
    item = content.items.get(item_key)
    if item is None:
        raise PetError("item_unknown")
    async with conn.transaction():
        pet = await pets.get(conn, pair_id, lock=True)
        if pet is None:
            raise LookupError(pair_id)  # маршрут пускает сюда только собранную пару
        opened = await unlocks.keys(conn, pair_id)
        if ITEM + item.key in opened:
            return  # уже куплено: повторное нажатие
        if not available(item, content, opened, pet.traits):
            raise PetError("item_locked")
        if not await rewards.spend(conn, pair_id, user_id, f"buy:{pair_id}:{item.key}", item.price):
            raise PetError("not_enough_sparks")
        await unlocks.add(conn, pair_id, ITEM + item.key)
        await pets.wear(conn, pair_id, item.slot, item.key)


async def wear(conn: asyncpg.Connection, pair_id: int, item_key: str, worn: bool, content: Content) -> None:
    """Надеть (в слоте один предмет) или снять купленный предмет."""
    item = content.items.get(item_key)
    if item is None:
        raise PetError("item_unknown")
    if not await unlocks.has(conn, pair_id, ITEM + item.key):
        raise PetError("item_not_owned")
    if worn:
        await pets.wear(conn, pair_id, item.slot, item.key)
    else:
        await pets.take_off(conn, pair_id, item.slot, item.key)


async def reset(conn: asyncpg.Connection, pair_id: int) -> None:
    """Только для отладки: шкалы в ноль, косметика снята, всё открытое закрыто."""
    await pets.reset(conn, pair_id)
    await unlocks.reset(conn, pair_id)
