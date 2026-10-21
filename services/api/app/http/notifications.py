"""Каналы уведомлений: подписка на web push и разрешение писать в Telegram."""

from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException

from app.http.deps import Conn, Ctx, CurrentUser
from app.http.models import ApiError, Me, PushSubscription
from app.http.views import view
from app.store import push, users

router = APIRouter(prefix="/notifications", responses={401: {"model": ApiError}, 422: {"model": ApiError}})

# Службы push браузеров. Чужой адрес не примем: иначе api слал бы запросы куда попросят.
PUSH_HOSTS = ("googleapis.com", "push.services.mozilla.com", "push.apple.com", "notify.windows.com")


@router.post("/push")
async def subscribe(body: PushSubscription, user: CurrentUser, conn: Conn, ctx: Ctx) -> Me:
    url = urlparse(body.endpoint)
    host = url.hostname or ""
    if url.scheme != "https" or not any(host == h or host.endswith("." + h) for h in PUSH_HOSTS):
        raise HTTPException(422, detail="push_endpoint")
    await push.save(conn, user.id, body.endpoint, body.keys.model_dump())
    return await view(conn, user.id, ctx)


@router.post("/telegram")
async def telegram_allowed(user: CurrentUser, conn: Conn, ctx: Ctx) -> Me:
    """Mini App получила разрешение (requestWriteAccess): боту снова можно писать этому человеку."""
    await users.set_reachable(conn, user.id, True)
    return await view(conn, user.id, ctx)
