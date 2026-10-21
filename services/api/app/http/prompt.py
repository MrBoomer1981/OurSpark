"""Послание дня: ответить и открыть результат. Клиент шлёт намерения — что выбрать и что открыть."""

from fastapi import APIRouter, HTTPException

from app.game import pairs, prompts, reveal
from app.game.prompts import PromptError
from app.http.deps import Conn, Ctx, CurrentUser
from app.http.models import AnswerRequest, ApiError, Me, RevealRequest
from app.http.views import view

router = APIRouter(prefix="/prompt", responses={401: {"model": ApiError}, 409: {"model": ApiError}})


@router.post("/answer")
async def answer(body: AnswerRequest, user: CurrentUser, conn: Conn, ctx: Ctx) -> Me:
    state = await pairs.state(conn, user)
    if state is None or state.partner is None:
        raise HTTPException(409, detail="no_pair")
    try:
        await prompts.answer(conn, user, state.partner, body.session_id, body.option, ctx.content)
    except PromptError as error:
        raise HTTPException(409, detail=error.code) from error
    return await view(conn, user.id, ctx)


@router.post("/reveal")
async def open_result(body: RevealRequest, user: CurrentUser, conn: Conn, ctx: Ctx) -> Me:
    try:
        await reveal.reveal(conn, user, body.session_id, ctx.content, ctx.config.timezone)
    except PromptError as error:
        raise HTTPException(409, detail=error.code) from error
    return await view(conn, user.id, ctx)
