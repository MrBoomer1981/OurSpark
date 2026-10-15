"""Напоминание за несколько часов до обмена — тем, у кого ещё нет фото."""

from datetime import datetime

from bot import daily
from bot.app import App
from bot.feature import Feature


async def reminder_job(app: App, now: datetime) -> None:
    today = now.date()
    current = await app.repo.get_day(today)
    if current is None or current.theme_sent_at is None or current.skipped:
        return
    if current.reminder_sent_at is not None or current.revealed_at is not None:
        return
    schedule = await daily.get_schedule(app)
    remind_at = daily.reminder_at(app, today, schedule)
    if remind_at is None or now < remind_at or now >= app.at(today, schedule.reveal):
        return
    # Тема ушла позже времени напоминания (бот лежал утром) — не дёргаем сразу следом за ней.
    if current.theme_sent_at >= remind_at:
        return
    await daily.send_reminders(app, today)


feature = Feature(name="reminder", jobs=(reminder_job,))
