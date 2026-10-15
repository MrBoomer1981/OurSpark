"""/dev — служебные кнопки для ручной проверки. Подключается только при DEBUG=true."""

from __future__ import annotations

from contextlib import suppress

from aiogram import Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.filters.callback_data import CallbackData
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot import daily, texts
from bot.app import App
from bot.feature import Feature
from bot.themes import ListThemes

router = Router(name="dev")


class DevCallback(CallbackData, prefix="dev"):
    action: str


def keyboard() -> InlineKeyboardMarkup:
    def button(action: str) -> InlineKeyboardButton:
        return InlineKeyboardButton(
            text=texts.DEV_BUTTONS[action], callback_data=DevCallback(action=action).pack()
        )

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [button("theme"), button("remind")],
            [button("reveal")],
            [button("reset"), button("clear")],
        ]
    )


async def render(app: App) -> str:
    today = app.today()
    themes_left = None
    if isinstance(app.themes, ListThemes):
        themes_left = app.themes.unused(await app.repo.used_themes())
    return texts.dev_state(
        today,
        await app.repo.get_day(today),
        len(await app.repo.get_submissions(today)),
        [member.name for member in await app.repo.members()],
        await daily.get_schedule(app),
        app.invite_link,
        themes_left,
    )


@router.message(Command("dev"))
async def cmd_dev(message: Message, app: App) -> None:
    await message.answer(await render(app), reply_markup=keyboard())


@router.callback_query(DevCallback.filter())
async def on_action(callback: CallbackQuery, callback_data: DevCallback, app: App) -> None:
    today = app.today()
    done = True
    match callback_data.action:
        case "theme":
            done = await daily.send_theme(app, today)
        case "remind":
            done = await daily.send_reminders(app, today)
        case "reveal":
            done = await daily.reveal(app, today)
        case "reset":
            await app.repo.reset_day(today)
        case "clear":
            await app.repo.clear_history()
    await callback.answer(texts.DEV_DONE if done else texts.DEV_NOT_NOW, show_alert=not done)
    if isinstance(callback.message, Message):
        with suppress(TelegramBadRequest):  # «message is not modified», если ничего не поменялось
            await callback.message.edit_text(await render(app), reply_markup=keyboard())


feature = Feature(name="dev", router=router)
