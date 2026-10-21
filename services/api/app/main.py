"""Приложение FastAPI: на старте подключается к базе, доводит схему и запускает рассылку; маршруты — под /api.

Локально: uvicorn app.main:app --reload (порт 8000). На Railway: python -m app.
"""

import asyncio
import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from app import logs
from app.config import Config
from app.http import auth, debug, health, me, pairs
from app.notify import relay
from app.store import db
from app.telegram.client import Telegram


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    config: Config = app.state.config
    app.state.pool = pool = await db.connect(config.database_url)
    app.state.telegram = telegram = Telegram(config.bot_token)
    await telegram.start()
    logger.info(
        "Telegram: {} · новые пары: {} · DEBUG: {}",
        f"@{telegram.username}" if telegram.username else "выключен (нет BOT_TOKEN)",
        config.new_pairs,
        config.debug,
    )
    sender = asyncio.create_task(relay.run(pool, telegram))
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
    for module in (health, me, pairs, auth):
        app.include_router(module.router, prefix="/api")
    if config.debug:
        app.include_router(debug.router, prefix="/api")
    return app


app = create_app()
