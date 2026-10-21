"""Отладочная панель. Роутер подключается только с DEBUG=true — без него этих маршрутов нет."""

from fastapi import APIRouter, HTTPException

from app.game import debug
from app.game.pairs import PairError
from app.game.prompts import PromptError
from app.http.deps import Conn, Ctx, CurrentUser
from app.http.models import ApiError, Me
from app.http.views import view

router = APIRouter(prefix="/debug", responses={401: {"model": ApiError}, 409: {"model": ApiError}})


@router.post("/partner")
async def stub_partner(user: CurrentUser, conn: Conn, ctx: Ctx) -> Me:
    """Подставной партнёр входит в пару — так одному человеку видно и сборку пары, и уведомление."""
    try:
        await debug.add_stub_partner(conn, user.id)
    except PairError as error:
        raise HTTPException(409, detail=error.code) from error
    return await view(conn, user.id, ctx)


@router.post("/partner-answer")
async def partner_answer(user: CurrentUser, conn: Conn, ctx: Ctx) -> Me:
    """Партнёр отвечает на текущее послание случайным вариантом."""
    try:
        await debug.answer_for_partner(conn, user.id, ctx.content, ctx.config.timezone)
    except PromptError as error:
        raise HTTPException(409, detail=error.code) from error
    return await view(conn, user.id, ctx)


@router.post("/next-day")
async def next_day(user: CurrentUser, conn: Conn, ctx: Ctx) -> Me:
    """Часы пары на день вперёд: если послание раскрыто, придёт новое."""
    await debug.next_day(conn, user.id)
    return await view(conn, user.id, ctx)


@router.post("/sparks")
async def sparks(user: CurrentUser, conn: Conn, ctx: Ctx) -> Me:
    """+100 искр в кошелёк пары."""
    await debug.grant_sparks(conn, user.id)
    return await view(conn, user.id, ctx)


@router.post("/reset-day")
async def reset_day(user: CurrentUser, conn: Conn, ctx: Ctx) -> Me:
    """Стереть текущее послание с ответами: назначится новое."""
    await debug.reset_day(conn, user.id)
    return await view(conn, user.id, ctx)


@router.post("/reset-progress")
async def reset_progress(user: CurrentUser, conn: Conn, ctx: Ctx) -> Me:
    """Пара с чистого листа: послания, искры, шкалы, косметика, реликвии, летопись."""
    await debug.reset_progress(conn, user.id)
    return await view(conn, user.id, ctx)
