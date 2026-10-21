"""Точка входа: python -m app."""

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import MenuButtonWebApp, WebAppInfo
from loguru import logger

from app import logs, texts
from app.api import Api
from app.config import Config
from app.handlers import router


async def main() -> None:
    config = Config()
    logs.setup(config.debug)

    bot = Bot(
        config.bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True),
    )
    me = await bot.get_me()
    # Кнопка меню во всех личных чатах с ботом открывает гнездо. Ставим её при каждом старте,
    # чтобы адрес Mini App жил в одном месте — в WEB_APP_URL.
    await bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(text=texts.MENU_BUTTON, web_app=WebAppInfo(url=config.web_app_url))
    )
    logger.info("Бот: @{} · Mini App: {} · api: {}", me.username, config.web_app_url, config.api_url)

    api = Api(config.api_url, config.internal_secret.get_secret_value())
    dp = Dispatcher(web_app_url=config.web_app_url, api=api)
    dp.include_router(router)
    # Накопившиеся обновления не сбрасываем: /start, присланный во время деплоя, получит ответ.
    await bot.delete_webhook(drop_pending_updates=False)
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await api.close()


if __name__ == "__main__":
    asyncio.run(main())
