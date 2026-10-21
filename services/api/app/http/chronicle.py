"""Летопись пары. Отдельно от /me: записей становится всё больше, а нужны они только на своём экране."""

from fastapi import APIRouter

from app.game import chronicle, pairs
from app.http.deps import Conn, Ctx, CurrentUser
from app.http.models import ApiError, ChronicleEntryView, ChronicleView

router = APIRouter(responses={401: {"model": ApiError}})


@router.get("/chronicle")
async def get_chronicle(user: CurrentUser, conn: Conn, ctx: Ctx) -> ChronicleView:
    state = await pairs.state(conn, user)
    if state is None or state.pet_hatched_at is None:
        return ChronicleView(entries=[])
    entries = []
    for entry in await chronicle.entries(conn, state.pair.id):
        text = chronicle.text(entry, ctx.content)  # None — неизвестный вид или ключей больше нет в контенте
        if text is not None:
            entries.append(ChronicleEntryView(id=entry.id, kind=entry.kind, text=text, created_at=entry.created_at))
    return ChronicleView(entries=entries)
