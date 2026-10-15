"""Утренняя тема, кнопка «Другая тема» и /today."""

from __future__ import annotations

from datetime import date, datetime

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import BotCommand, CallbackQuery, Message

from bot import daily, texts, ui
from bot.app import App
from bot.feature import Feature
from bot.repo import User

router = Router(name="daily_theme")


async def theme_job(app: App, now: datetime) -> None:
    """Разослать тему, когда наступит её время."""
    if await app.repo.member_count() < daily.PAIR_SIZE:
        return
    today = now.date()
    current = await app.repo.get_day(today)
    if current is not None and (current.theme_sent_at is not None or current.skipped):
        return
    schedule = await daily.get_schedule(app)
    if now < app.at(today, schedule.theme):
        return
    if now >= app.at(today, schedule.reveal):
        await daily.skip_day(app, today)
        return
    await daily.send_theme(app, today)


@router.message(Command("today"))
async def cmd_today(message: Message, app: App, user: User) -> None:
    members = await app.repo.members()
    if len(members) < daily.PAIR_SIZE:
        await message.answer(texts.need_partner(app.invite_link))
        return
    today = app.today()
    schedule = await daily.get_schedule(app)
    current = await app.repo.get_day(today)
    if current is None or current.theme_sent_at is None:
        skipped = current is not None and current.skipped
        await message.answer(texts.TODAY_SKIPPED if skipped else texts.today_no_theme(schedule.theme))
        return

    sent = {photo.user_id for photo in await app.repo.get_submissions(today)}
    partner = daily.partner_of(members, user.user_id)
    keyboard = None
    if current.exchanged_at is not None:
        status = texts.TODAY_EXCHANGED
    elif current.revealed_at is not None:
        status = texts.TODAY_LATE
    else:
        status = texts.today_until(schedule.reveal, app.at(today, schedule.reveal) - app.now())
        if not sent:
            keyboard = daily.reroll_keyboard(today, await daily.rerolls_left(app, today))
        elif len(sent) >= daily.PAIR_SIZE:
            # Оба фото на месте — можно открыть раньше, если согласны оба.
            votes = await app.repo.early_votes(today)
            name = daily.partner_name(members, user.user_id)
            if user.user_id in votes:
                status += "\n" + texts.early_you_wait(name)
            else:
                partner_wants = partner is not None and partner.user_id in votes
                status += "\n" + (texts.early_partner_wants(name) if partner_wants else texts.EARLY_HINT)
                keyboard = daily.early_open_keyboard(today)
    text = texts.today_status(
        current.theme,
        author=await daily.user_name(app, current.theme_author),
        mine=user.user_id in sent,
        partner=daily.partner_name(members, user.user_id),
        partner_has=partner is not None and partner.user_id in sent,
        status=status,
        streak=await daily.streak(app, today),
    )
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(daily.RerollCallback.filter())
async def on_reroll(
    callback: CallbackQuery, callback_data: daily.RerollCallback, app: App, user: User
) -> None:
    result = await daily.reroll_theme(app, date.fromisoformat(callback_data.day), user)
    if result != "ok":
        await callback.answer(texts.REROLL_DENIED[result], show_alert=True)
        return
    await callback.answer()
    await ui.edit_message(callback)


feature = Feature(
    name="daily_theme",
    router=router,
    jobs=(theme_job,),
    commands=(BotCommand(command="today", description=texts.COMMAND_TODAY),),
)
