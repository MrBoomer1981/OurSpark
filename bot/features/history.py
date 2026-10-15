"""Архив (/history): дни кнопками, фото за день и карточка с реакциями."""

from __future__ import annotations

from datetime import date
from math import ceil

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.filters.callback_data import CallbackData
from aiogram.types import (
    BotCommand,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from bot import daily, texts, ui
from bot.app import App
from bot.feature import Feature
from bot.repo import User

PAGE_SIZE = 10

router = Router(name="history")


class HistoryCallback(CallbackData, prefix="history"):
    action: str  # "page" — листание, "day" — открыть день
    value: str  # номер страницы или дата в ISO


async def render_page(app: App, page: int) -> tuple[str, InlineKeyboardMarkup | None]:
    total = await app.repo.history_count()
    if total == 0:
        return texts.HISTORY_EMPTY, None
    pages = ceil(total / PAGE_SIZE)
    page = min(max(page, 0), pages - 1)
    today = app.today()

    rows = [
        [
            InlineKeyboardButton(
                text=texts.history_button(day, photos, day.date == today),
                callback_data=HistoryCallback(action="day", value=day.date.isoformat()).pack(),
            )
        ]
        for day, photos in await app.repo.history_page(offset=page * PAGE_SIZE, limit=PAGE_SIZE)
    ]
    navigation = []
    if page + 1 < pages:
        older = HistoryCallback(action="page", value=str(page + 1)).pack()
        navigation.append(InlineKeyboardButton(text=texts.HISTORY_OLDER, callback_data=older))
    if page > 0:
        newer = HistoryCallback(action="page", value=str(page - 1)).pack()
        navigation.append(InlineKeyboardButton(text=texts.HISTORY_NEWER, callback_data=newer))
    if navigation:
        rows.append(navigation)

    stats = await daily.streak_stats(app, today)
    header = texts.history_header(stats.current, stats.best, await app.repo.exchange_count())
    return header, InlineKeyboardMarkup(inline_keyboard=rows)


@router.message(Command("history"))
async def cmd_history(message: Message, app: App) -> None:
    text, keyboard = await render_page(app, 0)
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(HistoryCallback.filter(F.action == "page"))
async def on_page(callback: CallbackQuery, callback_data: HistoryCallback, app: App) -> None:
    text, keyboard = await render_page(app, int(callback_data.value))
    await callback.answer()
    await ui.edit_message(callback, text, keyboard)


@router.callback_query(HistoryCallback.filter(F.action == "day"))
async def on_day(
    callback: CallbackQuery, callback_data: HistoryCallback, app: App, user: User
) -> None:
    await callback.answer()
    day = date.fromisoformat(callback_data.value)
    current = await app.repo.get_day(day)
    photos = await daily.visible_photos(app, day, user.user_id)
    if current is None or not photos:
        hidden = bool(await app.repo.get_submissions(day))
        await daily.notify(app, user.user_id, texts.HISTORY_DAY_HIDDEN if hidden else texts.HISTORY_DAY_EMPTY)
        return
    await daily.send_photos(app, user.user_id, photos)
    if current.exchanged_at is not None:
        # День с обменом — та же карточка, что вечером: реакции видны, можно поставить свою.
        await daily.send_card(app, day, user, archive=True)
    else:
        author = await daily.user_name(app, current.theme_author)
        await daily.notify(app, user.user_id, texts.history_day_footer(current, author))


feature = Feature(
    name="history",
    router=router,
    commands=(BotCommand(command="history", description=texts.COMMAND_HISTORY),),
)
