"""/settings: время темы, время обмена и часовой пояс пары меняются прямо в боте."""

from __future__ import annotations

import re
from datetime import time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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

from bot import daily, texts, ui
from bot.app import App
from bot.feature import Feature
from bot.repo import User

TIME_PATTERN = re.compile(r"\s*(\d{1,2})(?:[:.\s](\d{2}))?\s*")
# Частые часовые пояса — кнопками; любой другой можно написать текстом.
TIMEZONES = (
    ("Калининград", "Europe/Kaliningrad"),
    ("Москва", "Europe/Moscow"),
    ("Самара", "Europe/Samara"),
    ("Екатеринбург", "Asia/Yekaterinburg"),
    ("Омск", "Asia/Omsk"),
    ("Новосибирск", "Asia/Novosibirsk"),
    ("Иркутск", "Asia/Irkutsk"),
    ("Владивосток", "Asia/Vladivostok"),
    ("Минск", "Europe/Minsk"),
    ("Тбилиси", "Asia/Tbilisi"),
    ("Алматы", "Asia/Almaty"),
    ("Берлин", "Europe/Berlin"),
)

router = Router(name="settings")


class SettingsForm(StatesGroup):
    theme_time = State()
    reveal_time = State()
    timezone = State()


class SettingsCallback(CallbackData, prefix="settings"):
    field: str  # "theme" | "reveal" | "timezone"


class TimezoneCallback(CallbackData, prefix="tz"):
    index: int  # номер пояса в TIMEZONES


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
        ],
        [
            InlineKeyboardButton(
                text=texts.SETTINGS_TZ_BUTTON,
                callback_data=SettingsCallback(field="timezone").pack(),
            )
        ],
    ]
)
TIMEZONE_KEYBOARD = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text=label, callback_data=TimezoneCallback(index=index).pack())
            for index, (label, _) in enumerate(TIMEZONES[row : row + 3], start=row)
        ]
        for row in range(0, len(TIMEZONES), 3)
    ]
)


def timezone_label(key: str) -> str:
    return next((f"{label} ({zone})" for label, zone in TIMEZONES if zone == key), key)


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
        schedule, remind.time() if remind else None, daily.REMINDER_HOURS, timezone_label(app.tz.key)
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
        question, markup = texts.ASK_THEME_TIME, None
    elif callback_data.field == "reveal":
        await state.set_state(SettingsForm.reveal_time)
        question, markup = texts.ASK_REVEAL_TIME, None
    else:
        await state.set_state(SettingsForm.timezone)
        question, markup = texts.ASK_TIMEZONE, TIMEZONE_KEYBOARD
    if isinstance(callback.message, Message):
        await callback.message.answer(question, reply_markup=markup)


async def set_timezone(app: App, user: User, key: str, state: FSMContext) -> None:
    """Сменить часовой пояс пары и сообщить обоим. Расписание дальше идёт по новому поясу."""
    await app.repo.set_setting("timezone", key)
    await state.clear()
    for member in await app.repo.members():
        await daily.notify(app, member.user_id, texts.timezone_changed(user.name, timezone_label(key)))


@router.callback_query(TimezoneCallback.filter())
async def on_timezone_pick(
    callback: CallbackQuery, callback_data: TimezoneCallback, app: App, user: User, state: FSMContext
) -> None:
    await callback.answer()
    if not 0 <= callback_data.index < len(TIMEZONES):
        return
    await ui.edit_message(callback)
    await set_timezone(app, user, TIMEZONES[callback_data.index][1], state)


@router.message(StateFilter(SettingsForm.timezone), F.text, ~F.text.startswith("/"))
async def on_timezone_text(message: Message, app: App, user: User, state: FSMContext) -> None:
    key = (message.text or "").strip()
    try:
        ZoneInfo(key)
    except (ZoneInfoNotFoundError, ValueError):
        await message.answer(texts.BAD_TIMEZONE)
        return
    await set_timezone(app, user, key, state)


# Команды во время ввода не перехватываем: они уходят своим хендлерам.
@router.message(
    StateFilter(SettingsForm.theme_time, SettingsForm.reveal_time), F.text, ~F.text.startswith("/")
)
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
