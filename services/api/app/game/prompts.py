"""Послание дня: назначение, ответ и то, что видит каждый из пары.

Состояние послания не хранится отдельным полем, а выводится из ответов и completed_at (Today.state).
Правило взаимности живёт только в Today.partner_answer: выбор партнёра виден, лишь когда ответили оба.
"""

import random
from dataclasses import dataclass
from typing import Literal

import asyncpg

from app import notify
from app.content import Card, Content
from app.game import clock, rewards
from app.game.pairs import PAIR_SIZE
from app.store import prompts
from app.store.prompts import Answer, Session
from app.store.users import User

State = Literal["ASSIGNED", "WAITING_FOR_PARTNER", "READY_TO_REVEAL", "COMPLETED"]
PromptErrorCode = Literal["prompt_changed", "bad_option", "not_ready"]


class PromptError(Exception):
    def __init__(self, code: PromptErrorCode) -> None:
        super().__init__(code)
        self.code: PromptErrorCode = code


@dataclass(frozen=True)
class Today:
    session: Session
    card: Card
    answers: dict[int, Answer]

    def state(self, viewer_id: int) -> State:
        if self.session.completed_at is not None:
            return "COMPLETED"
        if len(self.answers) >= PAIR_SIZE:
            return "READY_TO_REVEAL"
        return "WAITING_FOR_PARTNER" if viewer_id in self.answers else "ASSIGNED"

    def partner_answer(self, viewer_id: int) -> Answer | None:
        """Правило взаимности: выбор партнёра виден, только когда ответили оба."""
        if viewer_id not in self.answers or len(self.answers) < PAIR_SIZE:
            return None
        return next(answer for user_id, answer in self.answers.items() if user_id != viewer_id)


async def current(conn: asyncpg.Connection, pair_id: int, content: Content, default_timezone: str) -> Today:
    """Послание пары. Если прежнее раскрыто не сегодня, назначает новое."""
    day = await clock.today(conn, pair_id, default_timezone)
    session = await prompts.latest(conn, pair_id)
    if session is None or (session.completed_on is not None and session.completed_on < day):
        await prompts.create(conn, pair_id, day, await _pick(conn, pair_id, content))
        session = await prompts.latest(conn, pair_id)
    assert session is not None
    return Today(session, content.cards[session.prompt_key], await prompts.answers(conn, session.id))


async def _pick(conn: asyncpg.Connection, pair_id: int, content: Content) -> str:
    """Карточка на сегодня: ещё не завершённая парой, а если пройдены все — та, что была давнее всех."""
    used = await prompts.used_keys(conn, pair_id)  # от новых к старым
    completed = {key for key, done in used if done}
    fresh = [key for key in content.cards if key not in completed]
    if fresh:
        return random.choice(fresh)
    last_seen: dict[str, int] = {}
    for position, (key, _) in enumerate(used):
        last_seen.setdefault(key, position)
    return max(content.cards, key=lambda key: last_seen.get(key, len(used)))


async def answer(
    conn: asyncpg.Connection,
    user: User,
    partner: User,
    session_id: int,
    option_key: str,
    content: Content,
) -> None:
    """Ответ на послание. Повторная отправка ничего не меняет: ни ответа, ни искр, ни уведомлений."""
    async with conn.transaction():
        # Строка послания под блокировкой: ответы двоих записываются по очереди,
        # поэтому ровно один из них видит, что ответ партнёра уже есть.
        session = await prompts.get(conn, session_id, lock=True)
        if session is None or session.pair_id != user.pair_id:
            raise PromptError("prompt_changed")
        if session.completed_at is not None:
            return
        option = content.cards[session.prompt_key].option(option_key)
        if option is None:
            raise PromptError("bad_option")
        if not await prompts.add_answer(conn, session.id, user.id, option.key):
            return
        await rewards.for_answer(conn, session.pair_id, user.id, session.id)
        if partner.id in await prompts.answers(conn, session.id):
            await notify.enqueue(
                conn, partner.id, notify.RESULT_READY, {}, key=f"result_ready:{session.id}:{partner.id}"
            )
        else:
            await notify.enqueue(
                conn,
                partner.id,
                notify.PARTNER_ANSWERED,
                {"name": user.name},
                key=f"partner_answered:{session.id}:{partner.id}",
            )
