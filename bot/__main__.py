"""Точка входа: python -m bot."""

import asyncio
import secrets
import sys
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from loguru import logger

from bot import daily, db
from bot.access import AccessMiddleware
from bot.app import App
from bot.config import Config
from bot.features import build_features
from bot.repo import Repo
from bot.scheduler import run_scheduler
from bot.themes import ListThemes


async def invite_code(config: Config, repo: Repo) -> str:
    """Код приглашения: из INVITE_CODE, иначе сгенерированный один раз и сохранённый в базе."""
    if config.invite_code:
        return config.invite_code
    code = await repo.get_setting("invite_code")
    if code is None:
        code = secrets.token_urlsafe(12)
        await repo.set_setting("invite_code", code)
    return code


async def main() -> None:
    config = Config()
    logger.remove()
    logger.add(sys.stderr, level="DEBUG" if config.debug else "INFO")

    conn = await db.connect(config.db_path)
    repo = Repo(conn)
    themes = ListThemes.load(config.themes_path)
    logger.info("Тем в списке: {}", len(themes.themes))

    bot = Bot(
        config.bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML, link_preview_is_disabled=True),
    )
    me = await bot.get_me()
    app = App(
        bot=bot,
        repo=repo,
        config=config,
        themes=themes,
        tz=ZoneInfo(config.timezone),
        bot_username=me.username or "",
        invite_code=await invite_code(config, repo),
    )
    app.features = build_features(config)

    dp = Dispatcher(app=app)
    access = AccessMiddleware()
    dp.message.outer_middleware(access)
    dp.callback_query.outer_middleware(access)
    for feature in app.features:
        if feature.router is not None:
            dp.include_router(feature.router)
    await bot.set_my_commands([command for feature in app.features for command in feature.commands])
    logger.info("Фичи: {}", ", ".join(feature.name for feature in app.features))

    members = await repo.member_count()
    if members < daily.PAIR_SIZE:
        logger.info("Ссылка-приглашение ({} из {} участников): {}", members, daily.PAIR_SIZE, app.invite_link)

    # Накопившиеся обновления не сбрасываем: фото, присланные во время деплоя, должны дойти.
    await bot.delete_webhook(drop_pending_updates=False)
    scheduler = asyncio.create_task(run_scheduler(app))
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.cancel()
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
