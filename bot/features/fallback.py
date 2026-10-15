"""Ответ на всё, что не поймали другие фичи. В реестре всегда последний."""

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from bot import texts
from bot.feature import Feature

router = Router(name="fallback")


@router.message(F.text.startswith("/"))
async def unknown_command(message: Message) -> None:
    await message.answer(texts.UNKNOWN_COMMAND)


@router.message()
async def not_a_photo(message: Message) -> None:
    await message.answer(texts.NOT_A_PHOTO)


@router.callback_query()
async def stale_button(callback: CallbackQuery) -> None:
    await callback.answer()


feature = Feature(name="fallback", router=router)
