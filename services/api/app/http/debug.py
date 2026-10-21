"""Отладочная панель. Роутер подключается только с DEBUG=true — без него этих маршрутов нет."""

from fastapi import APIRouter, HTTPException

from app.game import debug
from app.game.pairs import PairError
from app.http.deps import Conn, CurrentUser, Tg
from app.http.me import view
from app.http.models import ApiError, Me

router = APIRouter(prefix="/debug", responses={401: {"model": ApiError}, 409: {"model": ApiError}})


@router.post("/partner")
async def stub_partner(user: CurrentUser, conn: Conn, telegram: Tg) -> Me:
    """Подставной партнёр входит в пару — так одному человеку видно и сборку пары, и уведомление."""
    try:
        await debug.add_stub_partner(conn, user.id)
    except PairError as error:
        raise HTTPException(409, detail=error.code) from error
    return await view(conn, user.id, telegram)
