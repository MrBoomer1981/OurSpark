"""Логика дня: тема → фото → напоминание → обмен, и серия.

Здесь же единственная реализация правила «только в обмен» — visible_photos():
фото партнёра видно только за дни, когда обмен состоялся.

Каждое событие сначала бронируется в базе (repo.claim_*), и только потом рассылается.
Поэтому повторный вызов — из планировщика, /dev или после рестарта — ничего не дублирует.
Кому реально ушли тема и альбом обмена, отмечается в deliveries: если бот упал посреди
рассылки, redeliver() дошлёт остальным.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING, Literal

from aiogram.exceptions import (
    TelegramAPIError,
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramServerError,
)
from aiogram.filters.callback_data import CallbackData
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaDocument,
    InputMediaPhoto,
    Message,
)
from loguru import logger

from bot import texts
from bot.repo import Submission, User

if TYPE_CHECKING:
    from bot.app import App

PAIR_SIZE = 2
MAX_REROLLS = 3
REMINDER_HOURS = 3
DEFAULT_THEME_TIME = time(9, 0)
DEFAULT_REVEAL_TIME = time(21, 0)
# Досылаем только события старше минуты: свежие, возможно, ещё рассылаются прямо сейчас.
REDELIVERY_DELAY = timedelta(minutes=1)
REDELIVERY_DAYS = 2
# Временные сбои Telegram: такую отправку стоит повторить. Остальные ошибки (бот заблокирован,
# сообщение не найдено) повторять бессмысленно.
TRANSIENT_ERRORS = (TelegramNetworkError, TelegramRetryAfter, TelegramServerError)

RerollResult = Literal["ok", "stale", "has_photo", "limit", "race"]


class RerollCallback(CallbackData, prefix="reroll"):
    day: str  # дата в ISO: кнопка из вчерашнего сообщения не меняет сегодняшнюю тему


# ── Расписание ──────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Schedule:
    theme: time
    reveal: time


async def get_schedule(app: App) -> Schedule:
    theme = await app.repo.get_setting("theme_time")
    reveal = await app.repo.get_setting("reveal_time")
    return Schedule(
        theme=time.fromisoformat(theme) if theme else DEFAULT_THEME_TIME,
        reveal=time.fromisoformat(reveal) if reveal else DEFAULT_REVEAL_TIME,
    )


async def set_schedule(app: App, schedule: Schedule) -> None:
    await app.repo.set_setting("theme_time", texts.hhmm(schedule.theme))
    await app.repo.set_setting("reveal_time", texts.hhmm(schedule.reveal))


def reminder_at(app: App, day: date, schedule: Schedule) -> datetime | None:
    """Момент напоминания или None, если по расписанию оно выпало бы не позже темы."""
    moment = app.at(day, schedule.reveal) - timedelta(hours=REMINDER_HOURS)
    return moment if moment > app.at(day, schedule.theme) else None


# ── Участники и отправка ────────────────────────────────────────────────────


def partner_of(members: list[User], user_id: int) -> User | None:
    return next((member for member in members if member.user_id != user_id), None)


def partner_name(members: list[User], user_id: int) -> str:
    partner = partner_of(members, user_id)
    return partner.name if partner else "партнёр"


async def notify(
    app: App, chat_id: int, text: str, reply_markup: InlineKeyboardMarkup | None = None
) -> bool:
    """Отправить сообщение. Ошибка с одним получателем не должна ронять рассылку второму.

    False — временный сбой, отправку стоит повторить. True — доставлено или повторять бессмысленно.
    """
    try:
        await app.bot.send_message(chat_id, text, reply_markup=reply_markup)
    except TRANSIENT_ERRORS as error:
        logger.warning("Не удалось написать {}, повторим: {}", chat_id, error)
        return False
    except TelegramAPIError as error:
        logger.warning("Не удалось написать {}: {}", chat_id, error)
    return True


async def send_photos(app: App, chat_id: int, photos: list[Submission]) -> bool:
    """Прислать фото дня альбомом, а если нельзя — по одному. Возвращает то же, что notify().

    Telegram не кладёт сжатые фото и файлы в один альбом, поэтому смешанная пара
    уходит двумя сообщениями.
    """
    if not photos:
        return True
    names = {member.user_id: member.name for member in await app.repo.members()}
    captions = [texts.photo_caption(names.get(photo.user_id, "?"), photo.caption) for photo in photos]
    pairs = list(zip(photos, captions, strict=True))
    kinds = {photo.kind for photo in photos}
    try:
        if len(photos) > 1 and kinds == {"photo"}:
            await app.bot.send_media_group(
                chat_id, [InputMediaPhoto(media=p.file_id, caption=c) for p, c in pairs]
            )
        elif len(photos) > 1 and kinds == {"document"}:
            await app.bot.send_media_group(
                chat_id, [InputMediaDocument(media=p.file_id, caption=c) for p, c in pairs]
            )
        else:
            for photo, caption in pairs:
                if photo.kind == "photo":
                    await app.bot.send_photo(chat_id, photo.file_id, caption=caption)
                else:
                    await app.bot.send_document(chat_id, photo.file_id, caption=caption)
    except TRANSIENT_ERRORS as error:
        logger.warning("Не удалось отправить фото {}, повторим: {}", chat_id, error)
        return False
    except TelegramAPIError as error:
        logger.warning("Не удалось отправить фото {}: {}", chat_id, error)
    return True


# ── Тема ────────────────────────────────────────────────────────────────────


def reroll_keyboard(day: date, left: int) -> InlineKeyboardMarkup | None:
    if left <= 0:
        return None
    button = InlineKeyboardButton(
        text=texts.reroll_button(left),
        callback_data=RerollCallback(day=day.isoformat()).pack(),
    )
    return InlineKeyboardMarkup(inline_keyboard=[[button]])


async def rerolls_left(app: App, day: date) -> int:
    # Первая тема дня тоже лежит в theme_log, поэтому смен было «показано − 1».
    return MAX_REROLLS - max(0, await app.repo.themes_shown_on(day) - 1)


async def send_theme(app: App, day: date) -> bool:
    """Выбрать тему дня и разослать. False — тема за этот день уже была."""
    await app.repo.ensure_day(day)
    theme = await app.themes.pick(await app.repo.theme_history(), await app.repo.used_themes())
    now = app.now()
    if not await app.repo.claim_theme(day, theme, now):
        return False
    await app.repo.log_theme(day, theme.title, now)
    await deliver_theme(app, day)
    logger.info("Тема на {}: «{}»", day, theme.title)
    return True


async def deliver_theme(app: App, day: date) -> None:
    """Разослать тему дня тем, кому она ещё не ушла. Повторный вызов безопасен."""
    current = await app.repo.get_day(day)
    if current is None or current.theme_title is None:
        return
    schedule = await get_schedule(app)
    left = 0 if await app.repo.get_submissions(day) else await rerolls_left(app, day)
    keyboard = reroll_keyboard(day, left)
    text = texts.theme_message(current.theme, schedule.reveal)
    delivered = await app.repo.delivered_to(day, "theme")
    for member in await app.repo.members():
        if member.user_id in delivered:
            continue
        if await notify(app, member.user_id, text, keyboard):
            await app.repo.mark_delivered(day, member.user_id, "theme", app.now())


async def skip_day(app: App, day: date) -> None:
    """Бот проспал утро до самого обмена: день пропускаем, чтобы тема и обмен не пришли разом."""
    await app.repo.mark_skipped(day)
    logger.warning("День {} пропущен: во время темы бот не работал", day)


async def reroll_theme(app: App, day: date, by: User) -> RerollResult:
    current = await app.repo.get_day(day)
    if day != app.today() or current is None or current.theme_title is None:
        return "stale"
    if current.revealed_at is not None or current.skipped:
        return "stale"
    if await app.repo.get_submissions(day):
        return "has_photo"
    left = await rerolls_left(app, day)
    if left <= 0:
        return "limit"
    # Другая тема — всегда простая: пришла сложная, а готовиться не хочется.
    theme = await app.themes.pick(
        await app.repo.theme_history(), await app.repo.used_themes(), simple_only=True
    )
    if not await app.repo.replace_theme(day, current.theme_title, theme):
        return "race"
    await app.repo.log_theme(day, theme.title, app.now())
    schedule = await get_schedule(app)
    keyboard = reroll_keyboard(day, left - 1)
    for member in await app.repo.members():
        await notify(app, member.user_id, texts.theme_changed(by.name, theme, schedule.reveal), keyboard)
    logger.info("Тема на {} сменена по просьбе {}: «{}»", day, by.name, theme.title)
    return "ok"


# ── Фото ────────────────────────────────────────────────────────────────────


async def submit_photo(app: App, message: Message, user: User) -> None:
    """Принять фото дня.

    День считается по времени отправки сообщения, а не обработки: фото, отправленное
    в 23:58, пока бот перезапускался, всё равно попадёт в свой день.
    """
    if message.photo:
        file_id, kind = message.photo[-1].file_id, "photo"
    elif message.document:
        file_id, kind = message.document.file_id, "document"
    else:
        return

    members = await app.repo.members()
    if len(members) < PAIR_SIZE:
        await message.answer(texts.need_partner(app.invite_link))
        return
    day = app.local_date(message.date)
    schedule = await get_schedule(app)
    current = await app.repo.get_day(day)
    if current is None or current.theme_sent_at is None:
        skipped = current is not None and current.skipped
        text = texts.photo_day_skipped(schedule.theme) if skipped else texts.photo_before_theme(schedule.theme)
        await message.answer(text)
        return
    if current.exchanged_at is not None:
        await message.answer(texts.photo_day_closed(schedule.theme))
        return

    result = await app.repo.save_submission(
        Submission(
            date=day,
            user_id=user.user_id,
            file_id=file_id,
            kind=kind,
            caption=message.caption,
            media_group_id=message.media_group_id,
            sent_at=message.date,
        )
    )
    if result == "ignored":  # остальные фото того же альбома
        return
    # Партнёру пишем только про первое фото дня. «same» — то же фото пришло повторно
    # (Telegram передоставил сообщение после рестарта): отвечаем как обычно, без уведомлений.
    first_photo = result == "new"

    partner = partner_of(members, user.user_id)
    current = await app.repo.get_day(day)  # перечитываем: вечер мог наступить, пока фото сохранялось
    if current is not None and current.revealed_at is not None:
        # Вечер уже был — это опоздавшее фото. Если второе на месте, обмен прямо сейчас.
        if await try_exchange(app, day):
            return
        await message.answer(texts.photo_accepted_late(partner_name(members, user.user_id)))
        if first_photo and partner:
            await notify(app, partner.user_id, texts.partner_photo_waiting_late(user.name))
        return

    replaced = result == "replaced"
    reply = texts.photo_replaced(schedule.reveal) if replaced else texts.photo_accepted(schedule.reveal)
    if message.media_group_id:
        reply += texts.ALBUM_NOTE
    await message.answer(reply)
    if first_photo and partner:
        await notify(app, partner.user_id, texts.partner_photo_waiting(user.name))


# ── Напоминание ─────────────────────────────────────────────────────────────


async def send_reminders(app: App, day: date) -> bool:
    """Напомнить тем, у кого ещё нет фото. False — напоминание уже было или вечер прошёл."""
    if not await app.repo.claim_reminder(day, app.now()):
        return False
    current = await app.repo.get_day(day)
    title = current.theme_title if current and current.theme_title else ""
    members = await app.repo.members()
    sent = {photo.user_id for photo in await app.repo.get_submissions(day)}
    schedule = await get_schedule(app)
    left = app.at(day, schedule.reveal) - app.now()
    for member in members:
        if member.user_id in sent:
            continue
        partner = partner_of(members, member.user_id)
        waiting = partner.name if partner and partner.user_id in sent else None
        await notify(app, member.user_id, texts.reminder(title, schedule.reveal, left, waiting))
    return True


# ── Обмен ───────────────────────────────────────────────────────────────────


async def visible_photos(app: App, day: date, viewer_id: int) -> list[Submission]:
    """Правило «только в обмен»: фото партнёра видно, только если обмен за день состоялся.

    Порядок: сначала фото партнёра, потом своё.
    """
    current = await app.repo.get_day(day)
    photos = await app.repo.get_submissions(day)
    if current is None or current.exchanged_at is None:
        return [photo for photo in photos if photo.user_id == viewer_id]
    return sorted(photos, key=lambda photo: photo.user_id == viewer_id)


async def try_exchange(app: App, day: date) -> bool:
    """Провести обмен, если оба фото на месте и обмена ещё не было."""
    if not await app.repo.claim_exchange(day, app.now()):
        return False
    await deliver_exchange(app, day)
    logger.info("Обмен за {}", day)
    for feature in app.features:
        if feature.on_exchange is None:
            continue
        try:
            await feature.on_exchange(app, day)
        except Exception:
            logger.exception("Хук on_exchange фичи {} упал", feature.name)
    return True


async def deliver_exchange(app: App, day: date) -> None:
    """Разослать фото обмена тем, кому они ещё не ушли. Повторный вызов безопасен."""
    delivered = await app.repo.delivered_to(day, "exchange")
    for member in await app.repo.members():
        if member.user_id in delivered:
            continue
        if await send_photos(app, member.user_id, await visible_photos(app, day, member.user_id)):
            await app.repo.mark_delivered(day, member.user_id, "exchange", app.now())


async def reveal(app: App, day: date) -> bool:
    """Вечернее событие. False — оно за этот день уже было или темы не было."""
    if not await app.repo.claim_reveal(day, app.now()):
        return False
    if await try_exchange(app, day):
        return True
    members = await app.repo.members()
    sent = {photo.user_id for photo in await app.repo.get_submissions(day)}
    schedule = await get_schedule(app)
    for member in members:
        partner = partner_name(members, member.user_id)
        if not sent:
            text = texts.reveal_nobody(schedule.theme)
        elif member.user_id in sent:
            text = texts.reveal_waiting_partner(partner)
        else:
            text = texts.reveal_missing_yours(partner)
        await notify(app, member.user_id, text)
    logger.info("Вечер {}: фото {} из {}", day, len(sent), len(members))
    return True


async def close_past_day(app: App, day: date) -> None:
    """День прошёл без вечернего события (бот в это время лежал).

    Обмен — только если оба фото есть; звать дослать фото уже поздно.
    """
    if await app.repo.claim_reveal(day, app.now()):
        await try_exchange(app, day)


# ── Досылка после рестарта ──────────────────────────────────────────────────


async def redeliver(app: App, now: datetime) -> None:
    """Задача ядра: дослать тему и альбом обмена тем, кому они не дошли.

    Бот мог упасть или перезапуститься посреди рассылки (например, при деплое).
    Тему досылаем, пока не наступил вечер, альбом — в течение REDELIVERY_DAYS дней.
    """
    before = now - REDELIVERY_DELAY
    today = app.local_date(now)
    for day in await app.repo.undelivered_days("theme", today, before):
        logger.info("Досылаем тему за {}", day)
        await deliver_theme(app, day)
    since = today - timedelta(days=REDELIVERY_DAYS)
    for day in await app.repo.undelivered_days("exchange", since, before):
        logger.info("Досылаем обмен за {}", day)
        await deliver_exchange(app, day)


# ── Серия ───────────────────────────────────────────────────────────────────


async def streak(app: App, today: date) -> int:
    """Сколько дней подряд был обмен.

    Сегодняшний день серию не рвёт, пока не закончился. Дни, которые бот проспал
    (skipped), тоже не рвут.
    """
    exchanged, skipped = await app.repo.streak_marks()
    day = today if today in exchanged else today - timedelta(days=1)
    count = 0
    while day in exchanged or day in skipped:
        if day in exchanged:
            count += 1
        day -= timedelta(days=1)
    return count
