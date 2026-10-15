"""Пары: /start, создание пары, вход по ссылке-приглашению, /leave и /help."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.filters.callback_data import CallbackData
from aiogram.types import (
    BotCommand,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.types import User as TelegramUser
from loguru import logger

from bot import daily, texts, ui
from bot.access import PAIR_CALLBACK_PREFIX
from bot.app import App, Core
from bot.feature import Feature
from bot.repo import User

router = Router(name="onboarding")


class PairCallback(CallbackData, prefix=PAIR_CALLBACK_PREFIX):
    action: str  # create — создать пару, leave — выйти из пары, stay — передумать


def keyboard(*buttons: tuple[str, str]) -> InlineKeyboardMarkup:
    row = [InlineKeyboardButton(text=text, callback_data=PairCallback(action=action).pack()) for text, action in buttons]
    return InlineKeyboardMarkup(inline_keyboard=[row])


def display_name(sender: TelegramUser) -> str:
    return sender.first_name or sender.username or "Участник"


def create_keyboard(core: Core) -> InlineKeyboardMarkup | None:
    return keyboard((texts.CREATE_PAIR_BUTTON, "create")) if core.config.new_pairs else None


async def help_text(app: App | None) -> str:
    if app is None:
        schedule = daily.Schedule(daily.DEFAULT_THEME_TIME, daily.DEFAULT_REVEAL_TIME)
    else:
        schedule = await daily.get_schedule(app)
    return texts.help_text(schedule, daily.MAX_REROLLS, daily.REMINDER_HOURS)


async def first_theme_when(app: App) -> str:
    """Когда придёт первая тема для только что собравшейся пары."""
    now, today = app.now(), app.today()
    schedule = await daily.get_schedule(app)
    if now < app.at(today, schedule.theme):
        return texts.first_theme_today(schedule.theme)
    if now < app.at(today, schedule.reveal):
        return texts.FIRST_THEME_NOW
    return texts.first_theme_tomorrow(schedule.theme)


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, core: Core, app: App | None) -> None:
    sender = message.from_user
    if sender is None:
        return
    code = command.args
    if app is not None:  # уже в паре
        if code and code != app.invite_code:
            partner = daily.partner_of(await app.repo.members(), sender.id)
            await message.answer(texts.already_in_pair(partner.name if partner else None))
        elif await app.repo.member_count() < daily.PAIR_SIZE:
            await message.answer(texts.need_partner(app.invite_link))
        else:
            await message.answer(await help_text(app))
        return

    if not code:
        text = texts.INTRO if core.config.new_pairs else texts.NEW_PAIRS_CLOSED
        await message.answer(text, reply_markup=create_keyboard(core))
        return
    pair = await core.registry.pair_by_code(code)
    if pair is None:
        await message.answer(texts.INVITE_INVALID, reply_markup=create_keyboard(core))
        return
    name = display_name(sender)
    if not await core.registry.join_pair(pair.id, sender.id, name, core.clock(), limit=daily.PAIR_SIZE):
        await message.answer(texts.PAIR_FULL, reply_markup=create_keyboard(core))
        return
    app = await core.pair_app(pair.id)
    if app is None:
        return
    logger.info("Пара {}: новый участник {}", pair.id, sender.id)
    members = await app.repo.members()
    when = await first_theme_when(app)
    await message.answer(texts.welcome_second(daily.partner_name(members, sender.id), when))
    partner = daily.partner_of(members, sender.id)
    if partner is not None:
        await daily.notify(app, partner.user_id, texts.partner_joined(name, when))


@router.callback_query(PairCallback.filter(F.action == "create"))
async def on_create(callback: CallbackQuery, core: Core, app: App | None) -> None:
    if app is not None:
        await callback.answer(texts.ALREADY_IN_PAIR_SHORT, show_alert=True)
        return
    if not core.config.new_pairs:
        await callback.answer(texts.NEW_PAIRS_CLOSED, show_alert=True)
        return
    sender = callback.from_user
    pair = await core.registry.create_pair(sender.id, display_name(sender), core.clock())
    logger.info("Новая пара {}", pair.id)
    await callback.answer()
    await ui.edit_message(callback)
    await core.bot.send_message(sender.id, texts.welcome_first(core.invite_link(pair.invite_code)))


@router.message(Command("leave"))
async def cmd_leave(message: Message, app: App | None) -> None:
    if app is None:
        await message.answer(texts.NOT_IN_PAIR)
        return
    await message.answer(
        texts.LEAVE_CONFIRM, reply_markup=keyboard((texts.LEAVE_YES, "leave"), (texts.LEAVE_NO, "stay"))
    )


@router.callback_query(PairCallback.filter(F.action == "leave"))
async def on_leave(callback: CallbackQuery, core: Core, app: App | None, user: User | None) -> None:
    if app is None or user is None:
        await callback.answer(texts.NOT_IN_PAIR, show_alert=True)
        return
    members = await app.repo.members()
    await core.registry.leave_pair(app.pair_id, core.clock())
    logger.info("Пара {} распалась", app.pair_id)
    await callback.answer()
    await ui.edit_message(callback, texts.LEFT)
    for member in members:
        if member.user_id != user.user_id:
            await daily.notify(app, member.user_id, texts.partner_left(user.name))


@router.callback_query(PairCallback.filter(F.action == "stay"))
async def on_stay(callback: CallbackQuery) -> None:
    await callback.answer()
    await ui.edit_message(callback, texts.STAYED)


@router.message(Command("help"))
async def cmd_help(message: Message, app: App | None) -> None:
    await message.answer(await help_text(app))


feature = Feature(
    name="onboarding",
    router=router,
    commands=(BotCommand(command="help", description=texts.COMMAND_HELP),),
)
