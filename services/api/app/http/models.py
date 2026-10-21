"""Модели запросов и ответов. По ним FastAPI строит схему OpenAPI, а web генерирует свои типы."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ApiError(BaseModel):
    detail: str  # код ошибки, например pair_full; текст для человека — в web


class AppConfig(BaseModel):
    debug: bool
    new_pairs: bool


class Partner(BaseModel):
    name: str


class PairView(BaseModel):
    status: Literal["waiting", "complete"]
    invite_code: str
    invite_link: str | None  # t.me/<бот>?startapp=<код>; без BOT_TOKEN ссылки нет
    partner: Partner | None


class PetView(BaseModel):
    hatched_at: datetime


class Me(BaseModel):
    id: int
    name: str
    pair: PairView | None
    pet: PetView | None


class JoinRequest(BaseModel):
    code: str = Field(min_length=1, max_length=64)


class LoginStart(BaseModel):
    nonce: str
    link: str  # t.me/<бот>?start=login_<nonce>


class LoginExchange(BaseModel):
    nonce: str = Field(max_length=64)


class LoginResult(BaseModel):
    status: Literal["pending", "ok"]
    token: str | None = None


class LoginConfirm(BaseModel):
    nonce: str = Field(max_length=64)
    user_id: int
    name: str = Field(max_length=256)


class LoginConfirmResult(BaseModel):
    result: Literal["ok", "expired"]
