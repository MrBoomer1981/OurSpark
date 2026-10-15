"""Feature — единица расширения бота.

Новая фишка = модуль в bot/features/ с объектом Feature + строка в реестре
bot/features/__init__.py. Ядро (daily.py, scheduler.py) для этого трогать не нужно.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import TYPE_CHECKING

from aiogram import Router
from aiogram.types import BotCommand

if TYPE_CHECKING:
    from bot.app import App

# Задача планировщика: вызывается раз в ~30 с и сама решает, пора ли действовать.
Job = Callable[["App", datetime], Awaitable[None]]
# Хук на событие дня: получает дату дня, к которому относится событие.
DayHook = Callable[["App", date], Awaitable[None]]


@dataclass(frozen=True)
class Feature:
    name: str
    router: Router | None = None
    jobs: tuple[Job, ...] = ()
    commands: tuple[BotCommand, ...] = ()
    # После каждого состоявшегося обмена. Место для коллажа, реакций, ачивок.
    on_exchange: DayHook | None = None
