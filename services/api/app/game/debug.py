"""Действия отладочной панели. Маршруты к ним есть только с DEBUG=true."""

import random

import asyncpg

from app import texts
from app.content import Content
from app.game import chronicle, clock, pairs, pet, prompts, rewards
from app.store import prompts as prompt_store
from app.store import rewards as reward_store
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
    """Партнёр отвечает на текущее послание — случайным вариантом (и прогнозом) или текстом-заглушкой,
    как настоящий, с уведомлением.

    Это тестовый стенд, поэтому так можно и за настоящего партнёра, не только за подставного.
    """
    user = await users.get(conn, user_id)
    state = await pairs.state(conn, user) if user else None
    if user is None or state is None or state.partner is None:
        return
    today = await prompts.current(conn, state.pair.id, content, default_timezone)
    card = today.card
    if card.kind == "closeness":
        reply = prompts.Reply(text=texts.STUB_ANSWER)
    else:
        reply = prompts.Reply(
            option=random.choice(card.options).key,
            prediction=random.choice(card.options).key if card.kind == "guess" else None,
        )
    await prompts.answer(conn, state.partner, user, today.session.id, reply, content)


async def _pair_id(conn: asyncpg.Connection, user_id: int) -> int | None:
    user = await users.get(conn, user_id)
    return user.pair_id if user else None


async def next_day(conn: asyncpg.Connection, user_id: int) -> None:
    pair_id = await _pair_id(conn, user_id)
    if pair_id is not None:
        await clock.next_day(conn, pair_id)


async def grant_sparks(conn: asyncpg.Connection, user_id: int) -> None:
    """Искры в кошелёк пары. Заработанные: рост учтёт их при следующем раскрытии."""
    user = await users.get(conn, user_id)
    if user is not None and user.pair_id is not None and await pet.hatched_at(conn, user.pair_id):
        await rewards.for_debug(conn, user.pair_id, user.id)


async def reset_day(conn: asyncpg.Connection, user_id: int) -> None:
    """Стирает текущее послание с ответами: при следующем открытии Гнезда назначится новое.

    Искры и шкалы, уже полученные за него, остаются — это отладка, а не откат.
    """
    pair_id = await _pair_id(conn, user_id)
    if pair_id is None:
        return
    session = await prompt_store.latest(conn, pair_id)
    if session is not None:
        await prompt_store.delete(conn, session.id)


async def reset_progress(conn: asyncpg.Connection, user_id: int) -> None:
    """Пара с чистого листа: послания, искры, шкалы, косметика, реликвии и летопись — кроме первой страницы."""
    pair_id = await _pair_id(conn, user_id)
    if pair_id is None:
        return
    async with conn.transaction():
        await prompt_store.delete_pair(conn, pair_id)
        await reward_store.reset(conn, pair_id)
        await pet.reset(conn, pair_id)
        await chronicle.reset(conn, pair_id)
