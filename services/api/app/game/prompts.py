"""Послание дня: назначение, смена, ответ и то, что видит каждый из пары.

Состояние послания не хранится отдельным полем, а выводится из ответов и completed_at (Today.state).
Правило взаимности живёт только в Today.partner_answer: ответ партнёра — вариант, текст, прогноз —
виден, лишь когда ответили оба.
"""

import random
from dataclasses import dataclass
from typing import Literal

import asyncpg

from app import notify
from app.content import KINDS, Card, Content
from app.game import clock, rewards
from app.game.pairs import PAIR_SIZE
from app.store import prompts
from app.store.prompts import Answer, Session
from app.store.users import User

CHANGES_PER_DAY = 3  # «Другой вопрос»: столько раз в день пара может сменить послание
TEXT_LIMIT = 600  # свободный ответ, знаков

State = Literal["ASSIGNED", "WAITING_FOR_PARTNER", "READY_TO_REVEAL", "COMPLETED"]
PromptErrorCode = Literal[
    "prompt_changed", "bad_option", "empty_answer", "not_ready", "prompt_answered", "no_changes_left"
]


class PromptError(Exception):
    def __init__(self, code: PromptErrorCode) -> None:
        super().__init__(code)
        self.code: PromptErrorCode = code


@dataclass(frozen=True)
class Reply:
    """Что прислал человек — смотря по типу карточки: вариант, текст или вариант с прогнозом."""

    option: str | None = None
    text: str | None = None
    prediction: str | None = None


@dataclass(frozen=True)
class Today:
    session: Session
    card: Card
    answers: dict[int, Answer]
    changes_left: int  # сколько раз сегодня ещё можно сменить послание; 0 — нельзя (уже отвечают или лимит)

    def state(self, viewer_id: int) -> State:
        if self.session.completed_at is not None:
            return "COMPLETED"
        if len(self.answers) >= PAIR_SIZE:
            return "READY_TO_REVEAL"
        return "WAITING_FOR_PARTNER" if viewer_id in self.answers else "ASSIGNED"

    def partner_answer(self, viewer_id: int) -> Answer | None:
        """Правило взаимности: ответ партнёра виден, только когда ответили оба."""
        if viewer_id not in self.answers or len(self.answers) < PAIR_SIZE:
            return None
        return next(answer for user_id, answer in self.answers.items() if user_id != viewer_id)


async def current(conn: asyncpg.Connection, pair_id: int, content: Content, default_timezone: str) -> Today:
    """Послание пары. Если прежнее раскрыто не сегодня, назначает новое."""
    day = await clock.today(conn, pair_id, default_timezone)
    shown, changed = await prompts.shown_today(conn, pair_id, day)
    session = await prompts.latest(conn, pair_id)
    if session is None or (session.completed_on is not None and session.completed_on < day):
        key = await _pick(conn, pair_id, content, exclude=shown)
        if await prompts.create(conn, pair_id, day, key):
            await prompts.log(conn, pair_id, day, key, changed=False)
        session = await prompts.latest(conn, pair_id)
    assert session is not None
    answers = await prompts.answers(conn, session.id)
    can_change = session.completed_at is None and not answers
    return Today(
        session,
        content.cards[session.prompt_key],
        answers,
        changes_left=max(CHANGES_PER_DAY - changed, 0) if can_change else 0,
    )


async def completed_keys(conn: asyncpg.Connection, pair_id: int) -> set[str]:
    """Карточки, которые пара завершила хотя бы раз."""
    return await prompts.completed_keys(conn, pair_id)


async def _pick(conn: asyncpg.Connection, pair_id: int, content: Content, *, exclude: set[str]) -> str:
    """Карточка для пары. Сначала тип — по долям среди типов, где остались незавершённые карточки,
    потом случайная карточка этого типа. Показанные сегодня (exclude) не выпадают. Когда пара
    завершила всё — та, что была давнее всех.
    """
    used = await prompts.used_keys(conn, pair_id)  # от новых к старым
    completed = {key for key, done in used if done}
    fresh = [card for card in content.cards.values() if card.key not in completed and card.key not in exclude]
    if fresh:
        kinds = sorted({card.kind for card in fresh})
        kind = random.choices(kinds, weights=[KINDS[kind] for kind in kinds])[0]
        return random.choice([card.key for card in fresh if card.kind == kind])
    last_seen: dict[str, int] = {}
    for position, (key, _) in enumerate(used):
        last_seen.setdefault(key, position)
    candidates = [key for key in content.cards if key not in exclude] or list(content.cards)
    return max(candidates, key=lambda key: last_seen.get(key, len(used)))


async def change(
    conn: asyncpg.Connection, user: User, session_id: int, content: Content, default_timezone: str
) -> None:
    """«Другой вопрос»: пока никто не ответил, до CHANGES_PER_DAY раз в день.

    Сменённое послание удаляется, новое получает новый id: ответ, отправленный на старое,
    вернёт prompt_changed, а не попадёт в другую карточку.
    """
    async with conn.transaction():
        # Под блокировкой строки послания: смена и ответ не пройдут одновременно.
        session = await prompts.get(conn, session_id, lock=True)
        if session is None or session.pair_id != user.pair_id or session.completed_at is not None:
            raise PromptError("prompt_changed")
        if await prompts.answers(conn, session.id):
            raise PromptError("prompt_answered")
        day = await clock.today(conn, session.pair_id, default_timezone)
        shown, changed = await prompts.shown_today(conn, session.pair_id, day)
        if changed >= CHANGES_PER_DAY:
            raise PromptError("no_changes_left")
        key = await _pick(conn, session.pair_id, content, exclude=shown | {session.prompt_key})
        await prompts.replace(conn, session, key)
        await prompts.log(conn, session.pair_id, day, key, changed=True)


def _check(card: Card, reply: Reply) -> tuple[str | None, str | None, str | None]:
    """Ответ по типу карточки: вариант, текст или вариант с прогнозом. Лишнее — ошибка, а не тихий пропуск."""
    if card.kind == "closeness":
        if reply.option is not None or reply.prediction is not None:
            raise PromptError("bad_option")
        text = (reply.text or "").strip()
        if not text:
            raise PromptError("empty_answer")
        return None, text, None
    if reply.text is not None or reply.option is None or card.option(reply.option) is None:
        raise PromptError("bad_option")
    if card.kind != "guess":
        if reply.prediction is not None:
            raise PromptError("bad_option")
        return reply.option, None, None
    if reply.prediction is None or card.option(reply.prediction) is None:
        raise PromptError("bad_option")
    return reply.option, None, reply.prediction


async def answer(
    conn: asyncpg.Connection,
    user: User,
    partner: User,
    session_id: int,
    reply: Reply,
    content: Content,
) -> None:
    """Ответ на послание — вместе с прогнозом, если это «Угадай партнёра»: прогноз записан раньше,
    чем что-то раскрыто, и потом не меняется. Повторная отправка ничего не меняет: ни ответа, ни искр,
    ни уведомлений.
    """
    async with conn.transaction():
        # Строка послания под блокировкой: ответы двоих записываются по очереди,
        # поэтому ровно один из них видит, что ответ партнёра уже есть.
        session = await prompts.get(conn, session_id, lock=True)
        if session is None or session.pair_id != user.pair_id:
            raise PromptError("prompt_changed")
        if session.completed_at is not None:
            return
        option, text, prediction = _check(content.cards[session.prompt_key], reply)
        if not await prompts.add_answer(conn, session.id, user.id, option, text, prediction):
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
