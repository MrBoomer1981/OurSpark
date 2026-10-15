"""Вход по ссылке-приглашению, /start и /help."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import BotCommand, Message
from loguru import logger

from bot import daily, texts
from bot.app import App
from bot.feature import Feature
from bot.repo import User

router = Router(name="onboarding")


async def help_text(app: App) -> str:
    return texts.help_text(await daily.get_schedule(app), daily.MAX_REROLLS, daily.REMINDER_HOURS)


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
async def cmd_start(message: Message, command: CommandObject, app: App, user: User | None) -> None:
    if user is not None:
        await message.answer(await help_text(app))
        return
    sender = message.from_user
    if sender is None or command.args != app.invite_code:
        await message.answer(texts.PRIVATE)
        return
    name = sender.first_name or sender.username or "Участник"
    if not await app.repo.add_member(sender.id, name, limit=daily.PAIR_SIZE):
        await message.answer(texts.PRIVATE)
        return
    logger.info("Новый участник: {} ({})", name, sender.id)

    members = await app.repo.members()
    if len(members) < daily.PAIR_SIZE:
        await message.answer(texts.welcome_first(app.invite_link))
        return
    when = await first_theme_when(app)
    await message.answer(texts.welcome_second(daily.partner_name(members, sender.id), when))
    partner = daily.partner_of(members, sender.id)
    if partner is not None:
        await daily.notify(app, partner.user_id, texts.partner_joined(name, when))


@router.message(Command("help"))
async def cmd_help(message: Message, app: App) -> None:
    await message.answer(await help_text(app))


feature = Feature(
    name="onboarding",
    router=router,
    commands=(BotCommand(command="help", description=texts.COMMAND_HELP),),
)
