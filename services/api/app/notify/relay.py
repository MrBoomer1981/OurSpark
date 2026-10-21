"""Рассылка из outbox: цикл бронирует созревшие уведомления и отправляет их в Telegram.

Бронь делает рассылку безопасной при двух копиях api во время деплоя. Если копия упала
между отправкой и отметкой, через CLAIM_TIMEOUT уведомление уйдёт ещё раз: лучше дважды, чем никогда.
"""

import asyncio
from datetime import timedelta
from html import escape

import asyncpg
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from loguru import logger

from app import notify, texts
from app.store import outbox, users
from app.store.outbox import Message
from app.telegram.client import Telegram

POLL_SECONDS = 2
BATCH = 20
MAX_ATTEMPTS = 8  # с паузами 5 с → 10 мин: около получаса попыток


async def run(pool: asyncpg.Pool, telegram: Telegram) -> None:
    while True:
        try:
            async with pool.acquire() as conn:
                for message in await outbox.claim(conn, BATCH):
                    await deliver(conn, telegram, message)
        except Exception:
            logger.exception("Outbox: проход не удался")
        await asyncio.sleep(POLL_SECONDS)


def render(message: Message, telegram: Telegram) -> tuple[str, InlineKeyboardMarkup | None]:
    if message.kind == notify.PARTNER_JOINED:
        text = texts.PARTNER_JOINED.format(name=escape(message.payload["name"]))
    else:
        raise ValueError(f"неизвестный вид уведомления: {message.kind}")
    link = telegram.app_link()
    keyboard = (
        InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=texts.OPEN_NEST, url=link)]])
        if link
        else None
    )
    return text, keyboard


async def deliver(conn: asyncpg.Connection, telegram: Telegram, message: Message) -> None:
    if message.user_id < 0:  # подставной пользователь: в Telegram его нет
        await outbox.mark_sent(conn, message.id)
        return
    if telegram.bot is None:
        await outbox.mark_failed(conn, message.id, "нет BOT_TOKEN")
        return
    try:
        text, keyboard = render(message, telegram)
        await telegram.bot.send_message(message.user_id, text, reply_markup=keyboard)
    except (KeyError, ValueError) as error:  # ошибка в коде, а не в сети: повтор не поможет
        logger.error("Outbox: не собрать уведомление {} ({}): {!r}", message.id, message.kind, error)
        await outbox.mark_failed(conn, message.id, repr(error))
    except TelegramRetryAfter as error:
        await outbox.retry_later(conn, message.id, timedelta(seconds=error.retry_after), str(error))
    except TelegramForbiddenError as error:  # бот заблокирован или человек его ни разу не запускал
        await outbox.mark_failed(conn, message.id, str(error))
        await users.set_reachable(conn, message.user_id, False)
    except TelegramBadRequest as error:
        await outbox.mark_failed(conn, message.id, str(error))
        if "chat not found" in str(error).lower():
            await users.set_reachable(conn, message.user_id, False)
        else:
            logger.error("Outbox: Telegram отклонил уведомление {} ({}): {}", message.id, message.kind, error)
    except Exception as error:
        if message.attempts >= MAX_ATTEMPTS:
            logger.error("Outbox: уведомление {} ({}) не ушло: {!r}", message.id, message.kind, error)
            await outbox.mark_failed(conn, message.id, repr(error))
        else:
            delay = timedelta(seconds=min(5 * 2 ** (message.attempts - 1), 600))
            await outbox.retry_later(conn, message.id, delay, repr(error))
    else:
        await outbox.mark_sent(conn, message.id)
        await users.set_reachable(conn, message.user_id, True)
