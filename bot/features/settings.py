"""/settings: время темы и время обмена меняются прямо в боте."""

from __future__ import annotations

import re
from datetime import time

from aiogram import F, Router
from aiogram.filters import Command, StateFilter
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

from bot import daily, texts
from bot.app import App
from bot.feature import Feature
from bot.repo import User

TIME_PATTERN = re.compile(r"\s*(\d{1,2})(?:[:.\s](\d{2}))?\s*")

router = Router(name="settings")


class SettingsForm(StatesGroup):
    theme_time = State()
    reveal_time = State()


class SettingsCallback(CallbackData, prefix="settings"):
    field: str  # "theme" | "reveal"


KEYBOARD = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text=texts.SETTINGS_THEME_BUTTON,
                callback_data=SettingsCallback(field="theme").pack(),
            ),
            InlineKeyboardButton(
                text=texts.SETTINGS_REVEAL_BUTTON,
                callback_data=SettingsCallback(field="reveal").pack(),
            ),
        ]
    ]
)


def parse_time(text: str) -> time | None:
    """«8», «8:30», «08.30», «21 00» → time; всё остальное — None."""
    match = TIME_PATTERN.fullmatch(text)
    if match is None:
        return None
    hour, minute = int(match[1]), int(match[2] or 0)
    if hour > 23 or minute > 59:
        return None
    return time(hour, minute)


async def render(app: App) -> str:
    schedule = await daily.get_schedule(app)
    remind = daily.reminder_at(app, app.today(), schedule)
    return texts.settings_text(
        schedule, remind.time() if remind else None, daily.REMINDER_HOURS, app.config.timezone
    )


async def soon_warning(app: App, schedule: daily.Schedule, editing_theme: bool) -> str | None:
    """Новое время сегодня уже прошло — событие случится на ближайшем тике, предупреждаем."""
    now, today = app.now(), app.today()
    current = await app.repo.get_day(today)
    if editing_theme:
        pending = current is None or (current.theme_sent_at is None and not current.skipped)
        due = app.at(today, schedule.theme) <= now < app.at(today, schedule.reveal)
        paired = await app.repo.member_count() >= daily.PAIR_SIZE
        return texts.THEME_SOON if pending and due and paired else None
    pending = current is not None and current.theme_sent_at is not None and current.revealed_at is None
    return texts.REVEAL_SOON if pending and now >= app.at(today, schedule.reveal) else None


@router.message(Command("settings"))
async def cmd_settings(message: Message, app: App, state: FSMContext) -> None:
    await state.clear()
    await message.answer(await render(app), reply_markup=KEYBOARD)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(texts.SETTINGS_CANCELLED)


@router.callback_query(SettingsCallback.filter())
async def on_field(callback: CallbackQuery, callback_data: SettingsCallback, state: FSMContext) -> None:
    await callback.answer()
    if callback_data.field == "theme":
        await state.set_state(SettingsForm.theme_time)
        question = texts.ASK_THEME_TIME
    else:
        await state.set_state(SettingsForm.reveal_time)
        question = texts.ASK_REVEAL_TIME
    if isinstance(callback.message, Message):
        await callback.message.answer(question)


# Команды во время ввода не перехватываем: они уходят своим хендлерам.
@router.message(StateFilter(SettingsForm), F.text, ~F.text.startswith("/"))
async def on_time(message: Message, app: App, user: User, state: FSMContext) -> None:
    moment = parse_time(message.text or "")
    if moment is None:
        await message.answer(texts.BAD_TIME)
        return
    current = await daily.get_schedule(app)
    editing_theme = await state.get_state() == SettingsForm.theme_time.state
    if editing_theme:
        new = daily.Schedule(theme=moment, reveal=current.reveal)
    else:
        new = daily.Schedule(theme=current.theme, reveal=moment)
    if new.theme >= new.reveal:
        await message.answer(texts.theme_must_precede(new))
        return

    await daily.set_schedule(app, new)
    await state.clear()
    text = texts.schedule_changed(user.name, new)
    warning = await soon_warning(app, new, editing_theme)
    if warning:
        text += f"\n{warning}"
    for member in await app.repo.members():
        await daily.notify(app, member.user_id, text)


feature = Feature(
    name="settings",
    router=router,
    commands=(BotCommand(command="settings", description=texts.COMMAND_SETTINGS),),
)
