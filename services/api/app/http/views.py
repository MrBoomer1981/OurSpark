"""Состояние человека для web: пара, питомец, послание дня, уведомления.

Его возвращают GET /api/me и все маршруты, которые что-то меняют, — web просто заменяет своё состояние.
"""

from typing import Literal

import asyncpg

from app.content import Content
from app.context import Context
from app.game import pairs, pet, prompts, rewards
from app.game.prompts import Today
from app.http.models import (
    CardView,
    Choice,
    Me,
    NotificationsView,
    OptionView,
    PairView,
    Partner,
    PetView,
    PromptView,
    ResultView,
    TraitShift,
    TraitValue,
)
from app.store import push, users
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
    traits = await pet.traits(conn, pair_id)
    me.pet = PetView(
        hatched_at=state.pet_hatched_at,
        sparks=await rewards.balance(conn, pair_id),
        traits=[TraitValue(key=key, name=name, value=traits[key]) for key, name in ctx.content.traits.items()],
    )
    today = await prompts.current(conn, pair_id, ctx.content, ctx.config.timezone)
    me.prompt = _prompt(today, user, ctx.content)
    me.pet_line = _pet_line(today, user, ctx.content)
    return me


def _choice(today: Today, option_key: str) -> Choice:
    option = today.card.option(option_key)
    return Choice(option=option_key, text=option.text if option else option_key)


def _prompt(today: Today, user: User, content: Content) -> PromptView:
    seed = today.session.id + abs(user.id)
    mine = today.answers.get(user.id)
    my_option = today.card.option(mine.answer) if mine else None
    view = PromptView(
        session_id=today.session.id,
        day=today.session.day,
        state=today.state(user.id),
        card=CardView(
            key=today.card.key,
            kind="choice",
            text=today.card.text,
            options=[OptionView(key=o.key, text=o.text) for o in today.card.options],
        ),
        mine=_choice(today, mine.answer) if mine else None,
        reaction=content.line("answer", my_option.trait, seed) if my_option else None,
        answer_sparks=rewards.ANSWER_SPARKS if mine else None,
        partner_answered=any(user_id != user.id for user_id in today.answers),
        seen=bool(mine and mine.result_seen_at),
        result=None,
    )
    partner = today.partner_answer(user.id)  # правило взаимности: None, пока не ответили оба
    result = today.session.result
    if partner is not None and mine is not None and result is not None:
        same = partner.answer == mine.answer
        view.result = ResultView(
            partner=_choice(today, partner.answer),
            same=same,
            line=(
                content.line("reveal", "same", seed, option=view.mine.text if view.mine else "")
                if same
                else content.line("reveal", "different", seed)
            ),
            sparks=result.get("sparks", 0),
            traits=[
                TraitShift(key=key, name=content.traits.get(key, key), delta=delta)
                for key, delta in result.get("traits", {}).items()
            ],
        )
    return view


def _pet_line(today: Today, user: User, content: Content) -> str:
    seed = today.session.id + abs(user.id)
    state = today.state(user.id)
    mine = today.answers.get(user.id)
    if state == "COMPLETED":
        case = "done" if mine and mine.result_seen_at else "ready"
    elif state == "READY_TO_REVEAL":
        case = "ready"
    elif state == "WAITING_FOR_PARTNER":
        case = "waiting"
    else:
        case = "partner_answered" if today.answers else "your_turn"
    return content.line("nest", case, seed)
