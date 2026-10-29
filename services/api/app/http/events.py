"""События для метрик закрытого теста: web сообщает, что открыт экран. Ответ пустой — на игру это не влияет."""

from fastapi import APIRouter, Response

from app.game import metrics
from app.http.deps import Conn, Ctx, CurrentUser
from app.http.models import ApiError, ScreenEvent

router = APIRouter(responses={401: {"model": ApiError}})


@router.post("/events", status_code=204)
async def screen_opened(body: ScreenEvent, user: CurrentUser, conn: Conn, ctx: Ctx) -> Response:
    await metrics.screen(conn, user, body.screen, ctx.config.timezone)
    return Response(status_code=204)
