"""Кто я и что у меня: человек, пара, питомец. Плюс настройки, нужные web до входа."""

import asyncpg
from fastapi import APIRouter

from app.game import pairs
from app.http.deps import Conn, CurrentUser, Settings, Tg
from app.http.models import ApiError, AppConfig, Me, PairView, Partner, PetView
from app.store import users
from app.telegram.client import Telegram

router = APIRouter()


@router.get("/config")
async def app_config(settings: Settings) -> AppConfig:
    return AppConfig(debug=settings.debug, new_pairs=settings.new_pairs)


@router.get("/me", responses={401: {"model": ApiError}})
async def me(user: CurrentUser, conn: Conn, telegram: Tg) -> Me:
    return await view(conn, user.id, telegram)


async def view(conn: asyncpg.Connection, user_id: int, telegram: Telegram) -> Me:
    """Состояние человека. Его же возвращают маршруты, которые что-то меняют."""
    user = await users.get(conn, user_id)
    if user is None:
        raise LookupError(user_id)
    state = await pairs.state(conn, user)
    if state is None:
        return Me(id=user.id, name=user.name, pair=None, pet=None)
    return Me(
        id=user.id,
        name=user.name,
        pair=PairView(
            status="complete" if state.pair.completed_at else "waiting",
            invite_code=state.pair.invite_code,
            invite_link=telegram.app_link(state.pair.invite_code),
            partner=Partner(name=state.partner.name) if state.partner else None,
        ),
        pet=PetView(hatched_at=state.pet_hatched_at) if state.pet_hatched_at else None,
    )
