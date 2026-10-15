"""Точка входа: python -m bot."""

import asyncio
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from loguru import logger

from bot import db
from bot.access import AccessMiddleware
from bot.app import Core
from bot.config import Config
from bot.features import build_features
from bot.repo import Registry
from bot.scheduler import run_scheduler
from bot.themes import ListThemes


async def main() -> None:
    config = Config()
    logger.remove()
    # Значения переменных в трейсбэках (diagnose) — только в DEBUG: там бывают имена и подписи к фото.
    logger.add(
        sys.stderr,
        level="DEBUG" if config.debug else "INFO",
        backtrace=config.debug,
        diagnose=config.debug,
    )

    conn = await db.connect(config.db_path)  # на Railway без Volume бот здесь остановится
    registry = Registry(conn)
    pairs, people = await registry.stats()
    # После деплоя по этой строке видно, что ничего не пропало.
    logger.info("База: {} · пар: {} · участников: {}", config.db_path.resolve(), pairs, people)
    themes = ListThemes.load(config.themes_dir)
    logger.info("Темы: простых {}, посложнее {}", len(themes.simple), len(themes.creative))

    bot = Bot(
        config.bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True),
    )
    me = await bot.get_me()
    core = Core(
        bot=bot,
        conn=conn,
        registry=registry,
        config=config,
        themes=themes,
        bot_username=me.username or "",
    )
    core.features = build_features(config)

    dp = Dispatcher(core=core)
    access = AccessMiddleware()
    dp.message.outer_middleware(access)
    dp.callback_query.outer_middleware(access)
    for feature in core.features:
        if feature.router is not None:
            dp.include_router(feature.router)
    await bot.set_my_commands([command for feature in core.features for command in feature.commands])
    logger.info("Фичи: {} · новые пары: {}", ", ".join(f.name for f in core.features), config.new_pairs)

    # Накопившиеся обновления не сбрасываем: фото, присланные во время деплоя, должны дойти.
    await bot.delete_webhook(drop_pending_updates=False)
    scheduler = asyncio.create_task(run_scheduler(core))
    try:
        # По одному (handle_as_tasks=False): Telegram считает сообщение доставленным, только когда
        # бот его обработал. Если бота остановят посреди обработки (деплой), оно придёт заново.
        await dp.start_polling(
            bot, allowed_updates=dp.resolve_used_update_types(), handle_as_tasks=False
        )
    finally:
        scheduler.cancel()
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
