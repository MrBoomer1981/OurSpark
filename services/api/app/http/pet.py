"""Питомец: купить и надеть косметику. Клиент шлёт намерения — что купить и что надеть, без цен."""

from fastapi import APIRouter, HTTPException

from app.game import pairs, pet
from app.game.pet import PetError
from app.http.deps import Conn, Ctx, CurrentUser
from app.http.models import ApiError, BuyRequest, Me, WearRequest
from app.http.views import view
from app.store.users import User

router = APIRouter(prefix="/pet", responses={401: {"model": ApiError}, 409: {"model": ApiError}})


async def _pair_id(conn: Conn, user: User) -> int:
    """Пара человека, если она собрана и питомец уже есть; иначе 409 no_pair."""
    state = await pairs.state(conn, user)
    if state is None or state.pet_hatched_at is None:
        raise HTTPException(409, detail="no_pair")
    return state.pair.id


@router.post("/buy")
async def buy(body: BuyRequest, user: CurrentUser, conn: Conn, ctx: Ctx) -> Me:
    try:
        await pet.buy(conn, await _pair_id(conn, user), user.id, body.item, ctx.content)
    except PetError as error:
        raise HTTPException(409, detail=error.code) from error
    return await view(conn, user.id, ctx)


@router.post("/wear")
async def wear(body: WearRequest, user: CurrentUser, conn: Conn, ctx: Ctx) -> Me:
    try:
        await pet.wear(conn, await _pair_id(conn, user), body.item, body.worn, ctx.content)
    except PetError as error:
        raise HTTPException(409, detail=error.code) from error
    return await view(conn, user.id, ctx)
