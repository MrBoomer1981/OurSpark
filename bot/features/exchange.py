"""Вечерний обмен и закрытие дней, которые бот проспал."""

from datetime import datetime

from bot import daily
from bot.app import App
from bot.feature import Feature


async def reveal_job(app: App, now: datetime) -> None:
    today = now.date()
    # Бот лежал во время обмена и поднялся уже на следующий день — закрываем пропущенное.
    for past in await app.repo.unrevealed_days_before(today):
        await daily.close_past_day(app, past)

    current = await app.repo.get_day(today)
    if current is None or current.theme_sent_at is None or current.skipped:
        return
    if current.revealed_at is not None:
        return
    schedule = await daily.get_schedule(app)
    if now >= app.at(today, schedule.reveal):
        await daily.reveal(app, today)


feature = Feature(name="exchange", jobs=(reveal_job,))
