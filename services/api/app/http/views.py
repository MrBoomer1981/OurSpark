"""Состояние человека для web: пара, питомец, послание дня, уведомления.

Его возвращают GET /api/me и все маршруты, которые что-то меняют, — web просто заменяет своё состояние.
"""

from collections import Counter
from typing import Any, Literal

import asyncpg

from app.content import RELIC_SERIES, Content, pick
from app.context import Context
from app.game import pairs, pet, prompts, rewards
from app.game.prompts import TEXT_LIMIT, Today
from app.http.models import (
    AnswerView,
    CardView,
    GuessView,
    HabitView,
    ItemView,
    Me,
    NewsView,
    NotificationsView,
    OptionView,
    PairView,
    Partner,
    PetView,
    PromptView,
    RelicView,
    ResultView,
    SlotView,
    StageView,
    TraitRequirement,
    TraitShift,
    TraitValue,
)
from app.store import push, users
from app.store.prompts import Answer
from app.store.users import User

TELEGRAM: dict[bool | None, Literal["on", "off", "unknown"]] = {True: "on", False: "off", None: "unknown"}


async def view(conn: asyncpg.Connection, user_id: int, ctx: Context) -> Me:
    user = await users.get(conn, user_id)
    if user is None:
        raise LookupError(user_id)
    notifications = NotificationsView(
        telegram=TELEGRAM[user.tg_reachable],
        push=bool(await push.active(conn, user.id)),
    )
    me = Me(id=user.id, name=user.name, pair=None, pet=None, prompt=None, pet_line=None, notifications=notifications)
    state = await pairs.state(conn, user)
    if state is None:
        return me
    me.pair = PairView(
        status="complete" if state.pair.completed_at else "waiting",
        invite_code=state.pair.invite_code,
        invite_link=ctx.telegram.app_link(state.pair.invite_code),
        partner=Partner(name=state.partner.name) if state.partner else None,
    )
    if state.pet_hatched_at is None:
        return me  # пара ещё не собрана: ни питомца, ни посланий
    pair_id = state.pair.id
    opened = await pet.unlocked(conn, pair_id)
    me.pet = await _pet(conn, pair_id, opened, ctx.content)
    today = await prompts.current(conn, pair_id, ctx.content, ctx.config.timezone)
    me.prompt = _prompt(today, user, ctx.content)
    me.pet_line = _pet_line(today, user, opened, ctx.content)
    return me


async def _pet(conn: asyncpg.Connection, pair_id: int, opened: set[str], content: Content) -> PetView:
    state = await pet.get(conn, pair_id)
    if state is None:
        raise LookupError(pair_id)
    completed = Counter(
        content.cards[key].theme for key in await prompts.completed_keys(conn, pair_id) if key in content.cards
    )
    return PetView(
        hatched_at=state.created_at,
        sparks=await rewards.balance(conn, pair_id),
        earned=await rewards.earned(conn, pair_id),
        stage=pet.stage(content, opened).key,
        stages=[
            StageView(key=s.key, name=s.name, sparks=s.sparks, reached=pet.reached(content, opened, s.key))
            for s in content.stages
        ],
        traits=[
            TraitValue(key=key, name=trait.name, value=value, next_at=trait.next_at(value))
            for key, trait in content.traits.items()
            for value in [state.traits.get(key, 0)]
        ],
        habits=[HabitView(trait=trait.name, text=level.habit) for trait, level in pet.habits(content, opened)],
        slots=[SlotView(key=key, name=name) for key, name in content.slots.items()],
        items=[_item(item_key, state.traits, state.equipped, opened, content) for item_key in content.items],
        relics=[
            RelicView(
                theme=theme.name,
                name=theme.relic,
                text=theme.relic_text,
                found=pet.RELIC + key in opened,
                progress=min(completed[key], RELIC_SERIES),
                needed=RELIC_SERIES,
            )
            for key, theme in content.themes.items()
        ],
    )


def _item(key: str, traits: dict[str, int], equipped: dict[str, str], opened: set[str], content: Content) -> ItemView:
    item = content.items[key]
    if pet.ITEM + key in opened:
        state: Literal["owned", "available", "locked"] = "owned"
    elif pet.available(item, content, opened, traits):
        state = "available"
    else:
        state = "locked"
    requires = item.requires
    stage = content.stage(requires.stage) if requires and requires.stage else None
    trait = content.traits.get(requires.trait) if requires and requires.trait else None
    return ItemView(
        key=key,
        slot=item.slot,
        name=item.name,
        price=item.price,
        state=state,
        worn=equipped.get(item.slot) == key,
        requires_stage=stage.name if stage else None,
        requires_trait=TraitRequirement(name=trait.name, at=requires.at) if trait and requires else None,
        line=item.line,
    )


def _option(today: Today, key: str) -> AnswerView:
    option = today.card.option(key)
    return AnswerView(option=key, text=option.text if option else key)


def _answer(today: Today, answer: Answer) -> AnswerView:
    """Ответ вариантом или текстом."""
    if answer.answer is None:
        return AnswerView(option=None, text=answer.text or "")
    return _option(today, answer.answer)


def _prompt(today: Today, user: User, content: Content) -> PromptView:
    seed = today.session.id + abs(user.id)
    card = today.card
    mine = today.answers.get(user.id)
    my_option = card.option(mine.answer) if mine and mine.answer else None
    view = PromptView(
        session_id=today.session.id,
        day=today.session.day,
        state=today.state(user.id),
        card=CardView(
            key=card.key,
            kind=card.kind,
            text=card.text,
            options=[OptionView(key=o.key, text=o.text) for o in card.options],
            max_length=TEXT_LIMIT if card.kind == "closeness" else None,
        ),
        mine=_answer(today, mine) if mine else None,
        prediction=_option(today, mine.prediction) if mine and mine.prediction else None,
        changes_left=today.changes_left,
        reaction=_reaction(card.kind, my_option.trait if my_option else None, content, seed) if mine else None,
        answer_sparks=rewards.ANSWER_SPARKS if mine else None,
        partner_answered=any(user_id != user.id for user_id in today.answers),
        seen=bool(mine and mine.result_seen_at),
        result=None,
    )
    partner = today.partner_answer(user.id)  # правило взаимности: None, пока не ответили оба
    result = today.session.result
    if partner is not None and mine is not None and result is not None:
        same = mine.answer is not None and partner.answer == mine.answer
        my_guess = partner_guess = None
        if card.kind == "guess" and mine.prediction and partner.prediction:
            my_guess = GuessView(text=_option(today, mine.prediction).text, correct=mine.prediction == partner.answer)
            partner_guess = GuessView(
                text=_option(today, partner.prediction).text, correct=partner.prediction == mine.answer
            )
        view.result = ResultView(
            partner=_answer(today, partner),
            same=same,
            my_guess=my_guess,
            partner_guess=partner_guess,
            line=_reveal_line(card.kind, same, [my_guess, partner_guess], view.mine, content, seed),
            sparks=result.get("sparks", 0),
            traits=[
                TraitShift(key=key, name=content.traits[key].name if key in content.traits else key, delta=delta)
                for key, delta in result.get("traits", {}).items()
            ],
            news=[news for raw in result.get("news", []) if (news := _news(raw, content)) is not None],
            chronicle=my_option.chronicle if result.get("chronicle") and my_option else None,
        )
    return view


def _reaction(kind: str, trait: str | None, content: Content, seed: int) -> str:
    """Реакция питомца на свой ответ: по шкале варианта, а без шкалы — по типу вопроса.

    В «Угадай партнёра» питомец всегда говорит о прогнозе: он главный в этом ответе.
    """
    if kind in ("light", "choice") and trait is not None:
        return content.line("answer", trait, seed)
    return content.line("reply", "light" if kind == "choice" else kind, seed)


def _reveal_line(
    kind: str, same: bool, guesses: list[GuessView | None], mine: AnswerView | None, content: Content, seed: int
) -> str:
    """Общая реакция питомца после раскрытия — по типу вопроса."""
    if kind == "closeness":
        return content.line("reveal", "closeness", seed)
    if kind == "guess":
        hits = sum(1 for guess in guesses if guess is not None and guess.correct)
        return content.line("reveal", ("guess_none", "guess_one", "guess_both")[hits], seed)
    case = ("light_" if kind == "light" else "") + ("same" if same else "different")
    return content.line("reveal", case, seed, option=mine.text if mine else "")


def _news(raw: dict[str, Any], content: Content) -> NewsView | None:
    """Строка «что нового» из снимка раскрытия. Ключей нет в контенте — строку не показываем."""
    if raw.get("kind") == "stage" and (stage := content.stage(raw.get("stage", ""))) is not None:
        return NewsView(kind="stage", name=stage.name, text=stage.line or "")
    if raw.get("kind") == "habit" and (trait := content.traits.get(raw.get("trait", ""))) is not None:
        level = trait.level(raw.get("level", ""))
        return NewsView(kind="habit", name=trait.name, text=level.habit) if level else None
    if raw.get("kind") == "relic" and (theme := content.themes.get(raw.get("theme", ""))) is not None:
        return NewsView(kind="relic", name=theme.relic, text=theme.relic_text)
    return None


def _pet_line(today: Today, user: User, opened: set[str], content: Content) -> str:
    seed = today.session.id + abs(user.id)
    state = today.state(user.id)
    mine = today.answers.get(user.id)
    if state == "COMPLETED" and mine and mine.result_seen_at:
        # Послание прочитано: питомец говорит что-то своё — в том числе реплики открытых привычек.
        lines = content.lines["nest"]["done"] + [level.line for _, level in pet.habits(content, opened)]
        return pick(lines, seed)
    if state in ("COMPLETED", "READY_TO_REVEAL"):
        case = "ready"
    elif state == "WAITING_FOR_PARTNER":
        case = "waiting"
    else:
        case = "partner_answered" if today.answers else "your_turn"
    return content.line("nest", case, seed)
