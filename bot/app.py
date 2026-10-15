"""App — общий контекст бота.

Его получают все хендлеры (параметр app), задачи планировщика и хуки фич.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from aiogram import Bot

from bot.config import Config
from bot.feature import Feature
from bot.repo import Repo
from bot.themes import ThemeSource


@dataclass
class App:
    bot: Bot
    repo: Repo
    config: Config
    themes: ThemeSource
    tz: ZoneInfo
    bot_username: str
    invite_code: str
    features: list[Feature] = field(default_factory=list)

    def now(self) -> datetime:
        return datetime.now(self.tz)

    def today(self) -> date:
        return self.now().date()

    def local_date(self, moment: datetime) -> date:
        """Дата момента в часовом поясе пары — так определяется день фото."""
        return moment.astimezone(self.tz).date()

    def at(self, day: date, moment: time) -> datetime:
        return datetime.combine(day, moment, tzinfo=self.tz)

    @property
    def invite_link(self) -> str:
        return f"https://t.me/{self.bot_username}?start={self.invite_code}"
