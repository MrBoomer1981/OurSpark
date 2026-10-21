"""Раскрытие — единственный шаг, который затрагивает несколько областей: послание, искры, шкалы питомца.

Всё идёт одной транзакцией. Первое «Открыть результат» любого из партнёров бронирует completed_at
и применяет награды и шкалы ровно один раз; следующие вызовы только отмечают, что этот человек
результат увидел.
"""

from collections import Counter

import asyncpg

from app.content import Content
from app.game import clock, pet, rewards
from app.game.pairs import PAIR_SIZE
from app.game.prompts import PromptError
from app.store import prompts
from app.store.users import User


async def reveal(conn: asyncpg.Connection, user: User, session_id: int, content: Content, default_timezone: str) -> None:
    async with conn.transaction():
        session = await prompts.get(conn, session_id, lock=True)
        if session is None or session.pair_id != user.pair_id:
            raise PromptError("prompt_changed")
        answers = await prompts.answers(conn, session.id)
        if user.id not in answers or len(answers) < PAIR_SIZE:
            raise PromptError("not_ready")
        if session.completed_at is None:
            card = content.cards[session.prompt_key]
            deltas: Counter[str] = Counter()
            for answer in answers.values():
                option = card.option(answer.answer)
                if option is None:
                    raise ValueError(f"в карточке {card.key} нет варианта {answer.answer}: ключи вариантов менять нельзя")
                deltas[option.trait] += 1
            day = await clock.today(conn, session.pair_id, default_timezone)
            result = {"sparks": rewards.REVEAL_SPARKS, "traits": dict(deltas)}
            if await prompts.complete(conn, session.id, day, result):
                await rewards.for_reveal(conn, session.pair_id, session.id)
                await pet.shift(conn, session.pair_id, deltas)
        await prompts.mark_seen(conn, session.id, user.id)
