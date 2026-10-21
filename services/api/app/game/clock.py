"""Часы пары: какой сегодня день в её часовом поясе.

С DEBUG день можно сдвинуть вперёд (кнопка «следующий день» в отладочной панели). Сдвиг хранится
в настройках пары, поэтому его видят оба и он переживает перезапуск. Перед приходом настоящих пар
базу тестового стенда чистим, так что сдвиг в проде не останется.
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import asyncpg

from app.store import settings

TIMEZONE = "timezone"
DAY_OFFSET = "debug_day_offset"


async def today(conn: asyncpg.Connection, pair_id: int, default_timezone: str) -> date:
    zone = await settings.get(conn, pair_id, TIMEZONE) or default_timezone
    offset = int(await settings.get(conn, pair_id, DAY_OFFSET) or 0)
    return (datetime.now(ZoneInfo(zone)) + timedelta(days=offset)).date()


async def next_day(conn: asyncpg.Connection, pair_id: int) -> None:
    offset = int(await settings.get(conn, pair_id, DAY_OFFSET) or 0)
    await settings.put(conn, pair_id, DAY_OFFSET, str(offset + 1))
