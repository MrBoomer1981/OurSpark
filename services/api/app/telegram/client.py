"""Клиент Bot API бота игры: отправка сообщений и ссылки на бота.

Без BOT_TOKEN (это можно только с DEBUG) клиент выключен: входа через Telegram нет,
ссылок нет, уведомления не уходят. Так интерфейс делают локально, без Telegram.
"""

from urllib.parse import quote

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from pydantic import SecretStr


class Telegram:
    def __init__(self, token: SecretStr | None) -> None:
        self.bot = (
            Bot(
                token.get_secret_value(),
                default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True),
            )
            if token
            else None
        )
        self.username: str | None = None

    async def start(self) -> None:
        if self.bot is not None:
            me = await self.bot.get_me()
            self.username = me.username

    async def close(self) -> None:
        if self.bot is not None:
            await self.bot.session.close()

    def app_link(self, param: str | None = None) -> str | None:
        """Ссылка, которая открывает Mini App бота (нужен Main Mini App в BotFather)."""
        if self.username is None:
            return None
        suffix = f"={quote(param)}" if param else ""
        return f"https://t.me/{self.username}?startapp{suffix}"

    def start_link(self, param: str) -> str:
        """Ссылка на чат с ботом с параметром /start. Только при включённом клиенте."""
        if self.username is None:
            raise RuntimeError("Telegram выключен: нет BOT_TOKEN")
        return f"https://t.me/{self.username}?start={quote(param)}"
