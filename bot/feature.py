"""Feature — единица расширения бота.

Новая фишка = модуль в bot/features/ с объектом Feature + строка в реестре
bot/features/__init__.py. Ядро (daily.py, scheduler.py) для этого трогать не нужно.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import TYPE_CHECKING

from aiogram import Router
from aiogram.types import BotCommand, InlineKeyboardButton

if TYPE_CHECKING:
    from bot.app import App
    from bot.repo import User


@dataclass
class CardPart:
    """Вклад фичи в вечернюю карточку обмена: строки текста и ряд кнопок."""

    lines: list[str] = field(default_factory=list)
    buttons: list[InlineKeyboardButton] = field(default_factory=list)


# Задача планировщика: вызывается раз в ~30 с и сама решает, пора ли действовать.
Job = Callable[["App", datetime], Awaitable[None]]
# Хук на событие дня: получает дату дня, к которому относится событие.
DayHook = Callable[["App", date], Awaitable[None]]
# Часть вечерней карточки для конкретного участника (viewer) за день.
CardHook = Callable[["App", date, "User"], Awaitable[CardPart]]


@dataclass(frozen=True)
class Feature:
    name: str
    router: Router | None = None
    jobs: tuple[Job, ...] = ()
    commands: tuple[BotCommand, ...] = ()
    # Строки и кнопки в вечерней карточке (одно сообщение после альбома обмена).
    # Карточка досылается после рестарта, поэтому сюда можно класть важное.
    card: CardHook | None = None
    # После каждого состоявшегося обмена — для побочных действий (например, коллаж).
    # Вызывается один раз и может не сработать, если бот упадёт посреди обмена.
    on_exchange: DayHook | None = None
