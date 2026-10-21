"""Зависимости маршрутов: соединение с базой, конфиг, клиент Telegram и вошедший человек."""

from collections.abc import AsyncIterator
from typing import Annotated

import asyncpg
from fastapi import Depends, Header, HTTPException, Request

from app import texts
from app.config import Config
from app.store import auth, users
from app.store.users import User
from app.telegram import init_data
from app.telegram.client import Telegram


async def _connection(request: Request) -> AsyncIterator[asyncpg.Connection]:
    async with request.app.state.pool.acquire() as conn:
        yield conn


def _config(request: Request) -> Config:
    return request.app.state.config


def _telegram(request: Request) -> Telegram:
    return request.app.state.telegram


Conn = Annotated[asyncpg.Connection, Depends(_connection)]
Settings = Annotated[Config, Depends(_config)]
Tg = Annotated[Telegram, Depends(_telegram)]


async def _current_user(conn: Conn, settings: Settings, authorization: Annotated[str, Header()] = "") -> User:
    """Кто делает запрос, решает только сервер: подпись Telegram, токен сессии или (с DEBUG) подставной id."""
    scheme, _, credentials = authorization.partition(" ")
    if scheme == "tma" and settings.bot_token is not None:
        try:
            tg_user = init_data.check(credentials, settings.bot_token.get_secret_value())
        except init_data.InitDataError as error:
            raise HTTPException(401, detail=f"init_data_{error.reason}") from error
        return await users.ensure(conn, tg_user.id, tg_user.first_name)
    if scheme == "Bearer":
        user_id = await auth.session_user(conn, credentials)
        user = await users.get(conn, user_id) if user_id is not None else None
        if user is None:
            raise HTTPException(401, detail="session_invalid")
        return user
    if scheme == "debug" and settings.debug:
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
