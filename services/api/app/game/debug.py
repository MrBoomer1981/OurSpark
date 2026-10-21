"""Действия отладочной панели. Маршруты к ним есть только с DEBUG=true."""

import random

import asyncpg

from app import texts
from app.content import Content
from app.game import clock, pairs, prompts
from app.store import users


def stub_partner_id(pair_id: int) -> int:
    """Подставной партнёр у каждой пары свой. Отрицательный id: в Telegram таких нет."""
    return -(1000 + pair_id)


async def add_stub_partner(conn: asyncpg.Connection, user_id: int) -> None:
    """Подставной партнёр входит в пару человека — как настоящий, с уведомлением."""
    user = await users.get(conn, user_id)
    state = await pairs.state(conn, user) if user else None
    if state is None:
        return
    stub = await users.ensure(conn, stub_partner_id(state.pair.id), texts.STUB_PARTNER)
    await pairs.join(conn, stub.id, state.pair.invite_code)


async def answer_for_partner(conn: asyncpg.Connection, user_id: int, content: Content, default_timezone: str) -> None:
    """Партнёр отвечает на текущее послание случайным вариантом — как настоящий, с уведомлением.

    Это тестовый стенд, поэтому так можно и за настоящего партнёра, не только за подставного.
    """
    user = await users.get(conn, user_id)
    state = await pairs.state(conn, user) if user else None
    if user is None or state is None or state.partner is None:
        return
    today = await prompts.current(conn, state.pair.id, content, default_timezone)
    option = random.choice(today.card.options)
    await prompts.answer(conn, state.partner, user, today.session.id, option.key, content)


async def next_day(conn: asyncpg.Connection, user_id: int) -> None:
    user = await users.get(conn, user_id)
    if user is not None and user.pair_id is not None:
        await clock.next_day(conn, user.pair_id)
