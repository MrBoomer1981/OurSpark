"""Мелочи интерфейса, общие для фич."""

from contextlib import suppress

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message


async def edit_message(
    callback: CallbackQuery, text: str | None = None, markup: InlineKeyboardMarkup | None = None
) -> None:
    """Поменять сообщение под нажатой кнопкой: текст (если передан) и кнопки.

    Ошибки Telegram глотаем: сообщение могло устареть или не измениться («message is not modified»).
    """
    if not isinstance(callback.message, Message):
        return
    with suppress(TelegramBadRequest):
        if text is None:
            await callback.message.edit_reply_markup(reply_markup=markup)
        else:
            await callback.message.edit_text(text, reply_markup=markup)
