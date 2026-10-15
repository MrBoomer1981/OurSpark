"""Приём фото дня: обычное фото или картинка файлом (без сжатия)."""

from aiogram import F, Router
from aiogram.types import Message
from loguru import logger

from bot import daily, texts
from bot.app import App
from bot.feature import Feature
from bot.repo import User

router = Router(name="photos")


@router.message(F.photo | F.document.mime_type.startswith("image/"))
async def on_photo(message: Message, app: App, user: User) -> None:
    try:
        await daily.submit_photo(app, message, user)
    except Exception:
        # Молча терять фото нельзя: пусть пришлют ещё раз.
        logger.exception("Не удалось принять фото от {}", user.user_id)
        await message.answer(texts.PHOTO_SAVE_FAILED)


feature = Feature(name="photos", router=router)
