"""Контексты бота.

Core — общий: бот, база, конфиг, темы, фичи. App — контекст одной пары с тем же
интерфейсом, что нужен логике дня и фичам (app.repo, app.today(), app.invite_link…):
запросы ограничены парой, время — в её часовом поясе. Хендлеры получают App своей пары
параметром app (его подставляет access.py), задачи планировщика — тоже.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import aiosqlite
from aiogram import Bot

from bot.config import Config
from bot.feature import Feature
from bot.repo import Registry, Repo
from bot.themes import ThemeSource


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass
class Core:
    bot: Bot
    conn: aiosqlite.Connection
    registry: Registry
    config: Config
    themes: ThemeSource
    bot_username: str
    features: list[Feature] = field(default_factory=list)
    clock: Callable[[], datetime] = utc_now  # подменяется только в проверках

    def invite_link(self, code: str) -> str:
        return f"https://t.me/{self.bot_username}?start={code}"

    async def pair_app(self, pair_id: int) -> App | None:
        """Контекст пары или None, если пары нет (или её распустили)."""
        pair = await self.registry.get_pair(pair_id)
        if pair is None:
            return None
        repo = Repo(self.conn, pair.id)
        return App(core=self, pair_id=pair.id, repo=repo, tz=await _pair_timezone(self, repo), invite_code=pair.invite_code)


async def _pair_timezone(core: Core, repo: Repo) -> ZoneInfo:
    name = await repo.get_setting("timezone") or core.config.timezone
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(core.config.timezone)


@dataclass
class App:
    core: Core
    pair_id: int
    repo: Repo
    tz: ZoneInfo
    invite_code: str

    @property
    def bot(self) -> Bot:
        return self.core.bot

    @property
    def config(self) -> Config:
        return self.core.config

    @property
    def themes(self) -> ThemeSource:
        return self.core.themes

    @property
    def features(self) -> list[Feature]:
        return self.core.features

    @property
    def invite_link(self) -> str:
        return self.core.invite_link(self.invite_code)

    def now(self) -> datetime:
        return self.core.clock().astimezone(self.tz)

    def today(self) -> date:
        return self.now().date()

    def local_date(self, moment: datetime) -> date:
        """Дата момента в часовом поясе пары — так определяется день фото."""
        return moment.astimezone(self.tz).date()

    def at(self, day: date, moment: time) -> datetime:
        return datetime.combine(day, moment, tzinfo=self.tz)
