"""Послание дня: ответить, сменить и открыть результат. Клиент шлёт намерения, а не состояния."""

from fastapi import APIRouter, HTTPException

from app.game import pairs, prompts, reveal
from app.game.prompts import PromptError, Reply
from app.http.deps import Conn, Ctx, CurrentUser
from app.http.models import AnswerRequest, ApiError, ChangeRequest, Me, RevealRequest
from app.http.views import view

router = APIRouter(prefix="/prompt", responses={401: {"model": ApiError}, 409: {"model": ApiError}})


@router.post("/answer")
async def answer(body: AnswerRequest, user: CurrentUser, conn: Conn, ctx: Ctx) -> Me:
    state = await pairs.state(conn, user)
    if state is None or state.partner is None:
        raise HTTPException(409, detail="no_pair")
    try:
        reply = Reply(option=body.option, text=body.text, prediction=body.prediction)
        await prompts.answer(conn, user, state.partner, body.session_id, reply, ctx.content)
    except PromptError as error:
        raise HTTPException(409, detail=error.code) from error
    return await view(conn, user.id, ctx)


@router.post("/change")
async def change(body: ChangeRequest, user: CurrentUser, conn: Conn, ctx: Ctx) -> Me:
    """«Другой вопрос»: пока никто не ответил, несколько раз в день."""
    try:
        await prompts.change(conn, user, body.session_id, ctx.content, ctx.config.timezone)
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
