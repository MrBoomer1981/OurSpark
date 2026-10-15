"""Планировщик: раз в TICK_SECONDS вызывает задачи всех фич.

Задачи — не cron: каждая сама сверяет часы с базой и решает, пора ли действовать.
Поэтому после рестарта или деплоя пропущенное просто доделывается на ближайшем тике.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from bot.app import App

TICK_SECONDS = 30


async def run_scheduler(app: App) -> None:
    jobs = [(feature.name, job) for feature in app.features for job in feature.jobs]
    logger.info("Планировщик: задач {}, тик {} с", len(jobs), TICK_SECONDS)
    while True:
        now = app.now()
        for name, job in jobs:
            try:
                await job(app, now)
            except Exception:
                logger.exception("Задача фичи {} упала", name)
        await asyncio.sleep(TICK_SECONDS)
