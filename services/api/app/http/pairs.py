"""Пара: создать, войти по приглашению, выйти. Каждый маршрут возвращает новое состояние."""

from fastapi import APIRouter, HTTPException

from app.game import pairs
from app.game.pairs import PairError
from app.http.deps import Conn, CurrentUser, Settings, Tg
from app.http.me import view
from app.http.models import ApiError, JoinRequest, Me

router = APIRouter(prefix="/pairs", responses={401: {"model": ApiError}, 409: {"model": ApiError}})


@router.post("")
async def create_pair(user: CurrentUser, conn: Conn, settings: Settings, telegram: Tg) -> Me:
    try:
        await pairs.create(conn, user.id, new_pairs=settings.new_pairs)
    except PairError as error:
        raise HTTPException(409, detail=error.code) from error
    return await view(conn, user.id, telegram)


@router.post("/join")
async def join_pair(body: JoinRequest, user: CurrentUser, conn: Conn, telegram: Tg) -> Me:
    try:
        await pairs.join(conn, user.id, body.code)
    except PairError as error:
        raise HTTPException(409, detail=error.code) from error
    return await view(conn, user.id, telegram)


@router.post("/leave")
async def leave_pair(user: CurrentUser, conn: Conn, telegram: Tg) -> Me:
    await pairs.leave(conn, user.id)
    return await view(conn, user.id, telegram)
