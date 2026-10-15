"""Приём фото дня: обычное фото или картинка файлом (без сжатия)."""

from aiogram import F, Router
from aiogram.types import Message

from bot import daily
from bot.app import App
from bot.feature import Feature
from bot.repo import User

router = Router(name="photos")


@router.message(F.photo | F.document.mime_type.startswith("image/"))
async def on_photo(message: Message, app: App, user: User) -> None:
    await daily.submit_photo(app, message, user)


feature = Feature(name="photos", router=router)
