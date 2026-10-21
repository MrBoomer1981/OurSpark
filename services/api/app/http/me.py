"""Кто я и что у меня. Плюс настройки, нужные web до входа."""

from fastapi import APIRouter

from app.http.deps import Conn, Ctx, CurrentUser
from app.http.models import ApiError, AppConfig, Me
from app.http.views import view

router = APIRouter()


@router.get("/config")
async def app_config(ctx: Ctx) -> AppConfig:
    return AppConfig(
        debug=ctx.config.debug,
        new_pairs=ctx.config.new_pairs,
        vapid_public_key=ctx.push.public_key if ctx.push.enabled else None,
    )


@router.get("/me", responses={401: {"model": ApiError}})
async def me(user: CurrentUser, conn: Conn, ctx: Ctx) -> Me:
    """Состояние человека. Заодно назначает послание дня, если пора: оно назначается, когда открывают Гнездо."""
    return await view(conn, user.id, ctx)
