"""Доступ: бот только для двух участников.

Чужим доступен лишь /start — в нём проверяется код приглашения (features/onboarding.py).
Найденный участник кладётся в data["user"], и хендлеры получают его параметром user.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.enums import ChatType
from aiogram.types import CallbackQuery, Chat, Message, TelegramObject
from aiogram.types import User as TelegramUser

from bot import texts


class AccessMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        sender: TelegramUser | None = data.get("event_from_user")
        chat: Chat | None = data.get("event_chat")
        if sender is None or (chat is not None and chat.type != ChatType.PRIVATE):
            return None  # группы и каналы бот игнорирует
        member = await data["app"].repo.get_member(sender.id)
        data["user"] = member
        if member is not None or is_start_command(event):
            return await handler(event, data)
        if isinstance(event, Message):
            await event.answer(texts.PRIVATE)
        elif isinstance(event, CallbackQuery):
            await event.answer()
        return None


def is_start_command(event: TelegramObject) -> bool:
    if not isinstance(event, Message) or not event.text or not event.text.strip():
        return False
    command = event.text.split(maxsplit=1)[0]
    return command.split("@")[0] == "/start"
