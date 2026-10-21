"""Проверка initData — подписанных Telegram данных о том, кто открыл Mini App."""

from datetime import UTC, datetime, timedelta
from typing import Literal

from aiogram.utils.web_app import WebAppUser, safe_parse_webapp_init_data

# Mini App может долго висеть открытой, но initData старше суток не принимаем:
# перехваченную строку нельзя будет использовать вечно.
MAX_AGE = timedelta(days=1)


class InitDataError(Exception):
    def __init__(self, reason: Literal["invalid", "expired"]) -> None:
        super().__init__(reason)
        self.reason = reason


def check(init_data: str, bot_token: str) -> WebAppUser:
    try:
        data = safe_parse_webapp_init_data(bot_token, init_data)
    except ValueError as error:
        raise InitDataError("invalid") from error
    if data.user is None:
        raise InitDataError("invalid")
    auth_date = data.auth_date if data.auth_date.tzinfo else data.auth_date.replace(tzinfo=UTC)
    if datetime.now(UTC) - auth_date > MAX_AGE:
        raise InitDataError("expired")
    return data.user
