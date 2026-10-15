"""«Открыть сейчас»: если фото есть у обоих и оба согласны, обмен случается раньше вечера.

Логика — в ядре (daily.request_early_open), здесь только кнопка.
"""

from __future__ import annotations

from datetime import date

from aiogram import Router
from aiogram.types import CallbackQuery

from bot import daily, texts, ui
from bot.app import App
from bot.feature import Feature
from bot.repo import User

router = Router(name="early_open")


@router.callback_query(daily.EarlyOpenCallback.filter())
async def on_early_open(
    callback: CallbackQuery, callback_data: daily.EarlyOpenCallback, app: App, user: User
) -> None:
    result = await daily.request_early_open(app, date.fromisoformat(callback_data.day), user)
    if result in ("waiting", "already"):
        answer = texts.early_waiting(daily.partner_name(await app.repo.members(), user.user_id))
    else:
        answer = {
            "opened": texts.EARLY_OPENED,
            "not_ready": texts.EARLY_NOT_READY,
            "too_late": texts.EARLY_TOO_LATE,
        }[result]
    await callback.answer(answer)
    if result != "not_ready":
        await ui.edit_message(callback)


feature = Feature(name="early_open", router=router)
