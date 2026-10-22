"""Раскрытие — главный шаг, который затрагивает несколько областей: послание, искры, питомец, летопись.

Всё идёт одной транзакцией. Первое «Открыть результат» любого из партнёров бронирует completed_at
и применяет всё, что пара получает, ровно один раз; следующие вызовы только отмечают, что этот
человек результат увидел. Рост, привычки и реликвии проверяются только здесь: раскрытие — общий
момент пары, и прогресс меняется в одном месте.
"""

from collections import Counter
from typing import Any

import asyncpg

from app.content import Content
from app.game import chronicle, clock, pet, rewards
from app.game.pairs import PAIR_SIZE
from app.game.prompts import PromptError
from app.store import prompts
from app.store.prompts import Answer, Session
from app.store.users import User


async def reveal(conn: asyncpg.Connection, user: User, session_id: int, content: Content, default_timezone: str) -> None:
    async with conn.transaction():
        session = await prompts.get(conn, session_id, lock=True)
        if session is None or session.pair_id != user.pair_id:
            raise PromptError("prompt_changed")
        answers = await prompts.answers(conn, session.id)
        if user.id not in answers or len(answers) < PAIR_SIZE:
            raise PromptError("not_ready")
        day = await clock.today(conn, session.pair_id, default_timezone)
        if await prompts.claim(conn, session.id, day):
            await prompts.save_result(conn, session.id, await _apply(conn, session, answers, content))
        await prompts.mark_seen(conn, session.id, user.id)


async def _apply(
    conn: asyncpg.Connection, session: Session, answers: dict[int, Answer], content: Content
) -> dict[str, Any]:
    """Всё, что пара получает за раскрытие, и снимок для экрана результата. Зовётся только под бронью."""
    pair_id = session.pair_id
    card = content.cards[session.prompt_key]
    options = []
    for answer in answers.values():
        if answer.answer is None:
            continue  # ответ текстом (о близости): шкал не двигает
        option = card.option(answer.answer)
        if option is None:
            raise ValueError(f"в карточке {card.key} нет варианта {answer.answer}: ключи вариантов менять нельзя")
        options.append(option)
    deltas = Counter(option.trait for option in options if option.trait is not None)
    await rewards.for_reveal(conn, pair_id, session.id)
    await pet.shift(conn, pair_id, deltas)

    news: list[dict[str, str]] = []  # что открылось: показывается обоим на экране результата
    for stage in await pet.grow(conn, pair_id, await rewards.earned(conn, pair_id), content):
        news.append({"kind": "stage", "stage": stage.key})
        await chronicle.write(conn, pair_id, f"stage:{stage.key}", chronicle.STAGE, stage=stage.key)
    for trait, level in await pet.learn_habits(conn, pair_id, content):
        news.append({"kind": "habit", "trait": trait.key, "level": level.key})
        await chronicle.write(
            conn, pair_id, f"habit:{trait.key}:{level.key}", chronicle.HABIT, trait=trait.key, level=level.key
        )
    completed = await prompts.completed_keys(conn, pair_id)  # с этим посланием: бронь уже в транзакции
    in_theme = sum(1 for key in completed if key in content.cards and content.cards[key].theme == card.theme)
    if await pet.find_relic(conn, pair_id, card.theme, in_theme):
        news.append({"kind": "relic", "theme": card.theme})
        await chronicle.write(conn, pair_id, f"relic:{card.theme}", chronicle.RELIC, theme=card.theme)

    # Совпавший выбор попадает в летопись, только если для варианта задана запись.
    same = len(options) == PAIR_SIZE and len({option.key for option in options}) == 1
    page = same and options[0].chronicle is not None
    if page:
        await chronicle.write(
            conn, pair_id, f"choice:{session.id}", chronicle.CHOICE, prompt=card.key, option=options[0].key
        )
    return {"sparks": rewards.REVEAL_SPARKS, "traits": dict(deltas), "news": news, "chronicle": page}
