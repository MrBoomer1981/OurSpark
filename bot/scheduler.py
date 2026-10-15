"""Планировщик: раз в TICK_SECONDS проходит по всем собранным парам и вызывает задачи фич.

Задачи — не cron: каждая сама сверяет часы пары с базой и решает, пора ли действовать.
Поэтому после рестарта или деплоя пропущенное просто доделывается на ближайшем тике.
Пары независимы: ошибка в одной не мешает остальным.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from loguru import logger

from bot import daily

if TYPE_CHECKING:
    from bot.app import Core
    from bot.feature import Job

TICK_SECONDS = 30


def all_jobs(core: Core) -> list[tuple[str, Job]]:
    # Задача ядра идёт первой: досылает то, что не дошло из-за падения посреди рассылки.
    jobs: list[tuple[str, Job]] = [("ядро", daily.redeliver)]
    jobs += [(feature.name, job) for feature in core.features for job in feature.jobs]
    return jobs


async def tick(core: Core, jobs: list[tuple[str, Job]]) -> None:
    """Один проход: все задачи для каждой собранной пары, в её часовом поясе."""
    try:
        pair_ids = await core.registry.active_pairs(daily.PAIR_SIZE)
    except Exception:
        logger.exception("Планировщик: не удалось получить список пар")
        return
    for pair_id in pair_ids:
        app = await core.pair_app(pair_id)
        if app is None:
            continue
        now = app.now()
        for name, job in jobs:
            try:
                await job(app, now)
            except Exception:
                logger.exception("Пара {}: задача {} упала", pair_id, name)


async def run_scheduler(core: Core) -> None:
    jobs = all_jobs(core)
    logger.info("Планировщик: задач {}, тик {} с", len(jobs), TICK_SECONDS)
    while True:
        await tick(core, jobs)
        await asyncio.sleep(TICK_SECONDS)
