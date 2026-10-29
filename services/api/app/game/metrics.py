"""Метрики закрытого теста (ТЗ §13): что открывала пара и когда. На игру не влияют.

Открытие Гнезда — раз в день пары на человека: для возвращаемости важен сам факт. Экран — не чаще
раза в минуту: чтобы «открыли питомца после награды» видело и вечернее открытие после утреннего.
Запросы — в docs/metrics.md.
"""

from datetime import UTC, datetime
from typing import Literal

import asyncpg

from app.game import clock
from app.store import events
from app.store.users import User

OPEN = "open"  # открыл Гнездо (GET /api/me)
SCREEN = "screen"  # открыл экран «Питомец» или «Летопись»
Screen = Literal["pet", "chronicle"]


async def opened(conn: asyncpg.Connection, user: User, default_timezone: str) -> None:
    if user.pair_id is None:
        return
    day = await clock.today(conn, user.pair_id, default_timezone)
    await events.add(conn, user.pair_id, user.id, OPEN, day, f"{OPEN}:{user.id}:{day}", {})


async def screen(conn: asyncpg.Connection, user: User, name: Screen, default_timezone: str) -> None:
    if user.pair_id is None:
        return
    day = await clock.today(conn, user.pair_id, default_timezone)
    minute = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M")
    await events.add(conn, user.pair_id, user.id, SCREEN, day, f"{SCREEN}:{name}:{user.id}:{minute}", {"screen": name})
