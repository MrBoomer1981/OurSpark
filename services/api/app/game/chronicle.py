"""Летопись пары: записи только о заранее заданных событиях. Не тратятся и не теряются.

Запись хранит вид события и ключи контента, а текст собирается из контента при показе:
поправленная опечатка в тексте исправит и старые записи. Ключи контента постоянные.
"""

from typing import Any

import asyncpg

from app.content import Content
from app.store import chronicle
from app.store.chronicle import Entry

HATCH = "hatch"  # питомец вылупился: пара собрана
CHOICE = "choice"  # оба выбрали один вариант, и для него задана запись
STAGE = "stage"
HABIT = "habit"
RELIC = "relic"


async def write(conn: asyncpg.Connection, pair_id: int, event_key: str, kind: str, **data: Any) -> bool:
    """Пишет запись ровно один раз: повтор с тем же ключом события ничего не добавит."""
    return await chronicle.add(conn, pair_id, event_key, kind, data)


async def entries(conn: asyncpg.Connection, pair_id: int) -> list[Entry]:
    return await chronicle.entries(conn, pair_id)


def text(entry: Entry, content: Content) -> str | None:
    """Текст записи. None — ключей записи в контенте нет: такую запись не показываем."""
    data = entry.data
    if entry.kind == HATCH:
        return content.line("chronicle", "hatch", entry.id)
    if entry.kind == CHOICE:
        card = content.cards.get(data.get("prompt", ""))
        option = card.option(data.get("option", "")) if card else None
        if option is None:
            return None
        return option.chronicle or content.line("reveal", "same", entry.id, option=option.text)
    if entry.kind == STAGE:
        stage = content.stage(data.get("stage", ""))
        return content.line("chronicle", "stage", entry.id, name=stage.name) if stage else None
    if entry.kind == HABIT:
        trait = content.traits.get(data.get("trait", ""))
        level = trait.level(data.get("level", "")) if trait else None
        return content.line("chronicle", "habit", entry.id, habit=level.habit) if level else None
    if entry.kind == RELIC:
        theme = content.themes.get(data.get("theme", ""))
        if theme is None:
            return None
        return content.line("chronicle", "relic", entry.id, name=theme.relic, text=theme.relic_text)
    return None


async def reset(conn: asyncpg.Connection, pair_id: int) -> None:
    """Только для отладки: стирает всё, кроме первой страницы — «питомец вылупился»."""
    await chronicle.reset(conn, pair_id, keep=HATCH)
