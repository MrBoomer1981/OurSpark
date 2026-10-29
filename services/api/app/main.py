"""Приложение FastAPI: на старте подключается к базе, доводит схему, читает контент и запускает рассылку.

Маршруты — под /api. Локально: uvicorn app.main:app --reload (порт 8000). На Railway: python -m app.
"""

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from app import content, logs
from app.config import Config
from app.context import Context
from app.http import auth, chronicle, debug, events, health, me, notifications, pairs, pet, prompt
from app.notify import relay
from app.notify.push import Push
from app.store import db
from app.telegram.client import Telegram


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    config: Config = app.state.config
    game_content = content.load()  # ошибка в файлах контента не даст api запуститься
    app.state.pool = pool = await db.connect(config.database_url)
    telegram = Telegram(config.bot_token)
    await telegram.start()
    push = Push(config)
    app.state.ctx = Context(config=config, content=game_content, telegram=telegram, push=push)
    logger.info(
        "Telegram: {} · новые пары: {} · DEBUG: {}",
        f"@{telegram.username}" if telegram.username else "выключен (нет BOT_TOKEN)",
        config.new_pairs,
        config.debug,
    )
    logger.info(
        "Контент: карточек {} · web push: {}", len(game_content.cards), "включён" if push.enabled else "выключен"
    )
    sender = asyncio.create_task(relay.run(pool, telegram, push))
    try:
        yield
    finally:
        sender.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await sender
        await telegram.close()
        await pool.close()


def create_app() -> FastAPI:
    config = Config()
    logs.setup(config.debug)
    # Схема OpenAPI и /api/docs — только в DEBUG: по схеме локально генерируются типы для web.
    app = FastAPI(
        title="Воронье гнездо",
        lifespan=lifespan,
        openapi_url="/api/openapi.json" if config.debug else None,
        docs_url="/api/docs",  # без схемы FastAPI документацию не включает
        redoc_url=None,
    )
    app.state.config = config
    for module in (health, me, pairs, prompt, pet, chronicle, notifications, events, auth):
        app.include_router(module.router, prefix="/api")
    if config.debug:
        app.include_router(debug.router, prefix="/api")
    return app


app = create_app()
