"""Доступ: кто в паре — работает со своей парой; кто не в паре — может только создать пару
или войти по ссылке партнёра.

Middleware находит пару того, кто пишет, и кладёт в data контекст пары (app) и участника
(user) — хендлеры получают их параметрами. Не в паре — оба равны None, и дальше
пропускаются только /start, /help и кнопки создания пары (features/onboarding.py).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.enums import ChatType
from aiogram.types import CallbackQuery, Chat, Message, TelegramObject
from aiogram.types import User as TelegramUser

from bot import texts
from bot.app import Core

PAIR_CALLBACK_PREFIX = "pair"  # кнопки создания пары и выхода из неё — features/onboarding.py
OPEN_COMMANDS = ("/start", "/help")


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
        core: Core = data["core"]
        pair_id = await core.registry.user_pair(sender.id)
        app = await core.pair_app(pair_id) if pair_id is not None else None
        data["app"] = app
        data["user"] = await app.repo.get_member(sender.id) if app is not None else None
        if app is not None or is_open_to_all(event):
            return await handler(event, data)
        if isinstance(event, Message):
            await event.answer(texts.NOT_IN_PAIR)
        elif isinstance(event, CallbackQuery):
            await event.answer(texts.NOT_IN_PAIR, show_alert=True)
        return None


def is_open_to_all(event: TelegramObject) -> bool:
    """То, что доступно и тем, кто не в паре: /start, /help и кнопки создания пары."""
    if isinstance(event, CallbackQuery):
        return (event.data or "").split(":", 1)[0] == PAIR_CALLBACK_PREFIX
    if not isinstance(event, Message) or not event.text or not event.text.strip():
        return False
    command = event.text.split(maxsplit=1)[0].split("@")[0]
    return command in OPEN_COMMANDS
