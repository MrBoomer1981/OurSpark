"""Зависимости маршрутов: соединение с базой, контекст и вошедший человек."""

from collections.abc import AsyncIterator
from dataclasses import replace
from typing import Annotated

import asyncpg
from fastapi import Depends, Header, HTTPException, Request

from app import texts
from app.context import Context
from app.store import auth, users
from app.store.users import User
from app.telegram import init_data


async def _connection(request: Request) -> AsyncIterator[asyncpg.Connection]:
    async with request.app.state.pool.acquire() as conn:
        yield conn


def _context(request: Request) -> Context:
    return request.app.state.ctx


Conn = Annotated[asyncpg.Connection, Depends(_connection)]
Ctx = Annotated[Context, Depends(_context)]


async def _current_user(conn: Conn, ctx: Ctx, authorization: Annotated[str, Header()] = "") -> User:
    """Кто делает запрос, решает только сервер: подпись Telegram, токен сессии или (с DEBUG) подставной id."""
    config = ctx.config
    scheme, _, credentials = authorization.partition(" ")
    if scheme == "tma" and config.bot_token is not None:
        try:
            tg_user = init_data.check(credentials, config.bot_token.get_secret_value())
        except init_data.InitDataError as error:
            raise HTTPException(401, detail=f"init_data_{error.reason}") from error
        user = await users.ensure(conn, tg_user.id, tg_user.first_name)
        # Telegram говорит, что боту можно писать этому человеку, — канал рабочий.
        if tg_user.allows_write_to_pm and user.tg_reachable is not True:
            await users.set_reachable(conn, user.id, True)
            user = replace(user, tg_reachable=True)
        return user
    if scheme == "Bearer":
        user_id = await auth.session_user(conn, credentials)
        found = await users.get(conn, user_id) if user_id is not None else None
        if found is None:
            raise HTTPException(401, detail="session_invalid")
        return found
    if scheme == "debug" and config.debug:
        # Только отрицательные id: в Telegram таких нет, поэтому настоящего человека так не подделать.
        try:
            user_id = int(credentials)
        except ValueError:
            user_id = 0
        if user_id < 0:
            existing = await users.get(conn, user_id)
            return existing or await users.ensure(conn, user_id, texts.STUB_USER.format(number=-user_id))
    raise HTTPException(401, detail="unauthorized")


CurrentUser = Annotated[User, Depends(_current_user)]
