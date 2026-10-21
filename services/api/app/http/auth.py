"""Вход в PWA через бота.

1. PWA просит nonce и открывает t.me/<бот>?start=login_<nonce>.
2. Бот спрашивает подтверждение и сообщает о нём сюда по приватной сети, с общим секретом.
3. PWA меняет подтверждённый nonce на токен сессии — один раз.
"""

import hmac
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException

from app.http.deps import Conn, Ctx
from app.http.models import ApiError, LoginConfirm, LoginConfirmResult, LoginExchange, LoginResult, LoginStart
from app.store import auth, users

router = APIRouter()


@router.post("/auth/login", responses={503: {"model": ApiError}})
async def login_start(conn: Conn, ctx: Ctx) -> LoginStart:
    telegram = ctx.telegram
    if telegram.username is None:
        raise HTTPException(503, detail="telegram_off")
    nonce = await auth.create_nonce(conn)
    return LoginStart(nonce=nonce, link=telegram.start_link(f"login_{nonce}"))


@router.post("/auth/login/exchange", responses={410: {"model": ApiError}})
async def login_exchange(body: LoginExchange, conn: Conn) -> LoginResult:
    async with conn.transaction():
        status, user_id = await auth.use_nonce(conn, body.nonce)
        if status == "expired":
            raise HTTPException(410, detail="login_expired")
        if user_id is None:
            return LoginResult(status="pending")
        return LoginResult(status="ok", token=await auth.create_session(conn, user_id))


# Только для bot: Caddy в web не пускает к /api/internal/* снаружи, а без секрета не пустит и api.
@router.post("/internal/login/confirm", include_in_schema=False)
async def login_confirm(
    body: LoginConfirm,
    conn: Conn,
    ctx: Ctx,
    x_internal_secret: Annotated[str, Header()] = "",
) -> LoginConfirmResult:
    secret = ctx.config.internal_secret
    if secret is None or not hmac.compare_digest(x_internal_secret.encode(), secret.get_secret_value().encode()):
        raise HTTPException(403, detail="forbidden")
    await users.ensure(conn, body.user_id, body.name)
    confirmed = await auth.confirm_nonce(conn, body.nonce, body.user_id)
    return LoginConfirmResult(result="ok" if confirmed else "expired")
