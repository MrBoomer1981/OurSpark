"""Темы друг для друга: /addtheme кладёт тему в копилку.

Когда тема из копилки выпадает, решает ядро — daily.send_theme: не чаще чем через день,
по очереди от каждого автора. Партнёр заранее тему не видит.
"""

from __future__ import annotations

from contextlib import suppress

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject, StateFilter
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BotCommand,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from bot import texts
from bot.app import App
from bot.feature import Feature
from bot.repo import User
from bot.themes import Theme

TITLE_LENGTH = (2, 50)
HINT_LIMIT = 100
SEPARATORS = (" — ", " – ", " - ", "\n")

router = Router(name="partner_themes")


class AddThemeForm(StatesGroup):
    waiting = State()


class DeleteThemeCallback(CallbackData, prefix="ctheme"):
    id: int


def parse_theme(raw: str) -> Theme | None:
    """«Окно — вид из любого окна» → Theme. Подсказка необязательна."""
    text = raw.strip()
    title, hint = text, ""
    for separator in SEPARATORS:
        if separator in text:
            title, _, hint = text.partition(separator)
            break
    title = title.strip().strip("«»\"' ")
    hint = " ".join(hint.split())
    if "\n" in title or not TITLE_LENGTH[0] <= len(title) <= TITLE_LENGTH[1] or len(hint) > HINT_LIMIT:
        return None
    return Theme(title, hint)


async def save_theme(message: Message, app: App, user: User, raw: str) -> bool:
    theme = parse_theme(raw)
    if theme is None:
        await message.answer(texts.ADDTHEME_BAD)
        return False
    theme_id = await app.repo.add_custom_theme(user.user_id, theme, app.now())
    delete = InlineKeyboardButton(
        text=texts.ADDTHEME_DELETE_BUTTON, callback_data=DeleteThemeCallback(id=theme_id).pack()
    )
    await message.answer(
        texts.addtheme_saved(theme.title, await app.repo.custom_pending_count(user.user_id)),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[delete]]),
    )
    return True


@router.message(Command("addtheme"))
async def cmd_addtheme(
    message: Message, command: CommandObject, app: App, user: User, state: FSMContext
) -> None:
    if command.args:  # /addtheme Окно — вид из любого окна
        await state.clear()
        await save_theme(message, app, user, command.args)
        return
    await state.set_state(AddThemeForm.waiting)
    await message.answer(texts.addtheme_prompt(await app.repo.custom_pending_count(user.user_id)))


# Команды во время ввода не перехватываем: они уходят своим хендлерам (/cancel — в settings).
@router.message(StateFilter(AddThemeForm.waiting), F.text, ~F.text.startswith("/"))
async def on_theme_text(message: Message, app: App, user: User, state: FSMContext) -> None:
    if await save_theme(message, app, user, message.text or ""):
        await state.clear()


@router.callback_query(DeleteThemeCallback.filter())
async def on_delete(
    callback: CallbackQuery, callback_data: DeleteThemeCallback, app: App, user: User
) -> None:
    if not await app.repo.delete_custom_theme(callback_data.id, user.user_id):
        await callback.answer(texts.ADDTHEME_TOO_LATE, show_alert=True)
        return
    await callback.answer()
    if isinstance(callback.message, Message):
        with suppress(TelegramBadRequest):
            await callback.message.edit_text(texts.ADDTHEME_DELETED)


feature = Feature(
    name="partner_themes",
    router=router,
    commands=(BotCommand(command="addtheme", description=texts.COMMAND_ADDTHEME),),
)
