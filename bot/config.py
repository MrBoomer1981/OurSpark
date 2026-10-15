"""Конфиг из переменных окружения: на Railway — из Variables, локально — из .env."""

import re
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Telegram пропускает в deep link только эти символы и не больше 64.
INVITE_CODE_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,64}")


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: SecretStr
    invite_code: str | None = None
    timezone: str = "Europe/Moscow"
    db_path: Path = Path("data/bot.db")
    themes_dir: Path = Path("themes")
    debug: bool = False

    @field_validator("invite_code", mode="before")
    @classmethod
    def _check_invite_code(cls, value: object) -> object:
        if value in (None, ""):
            return None
        if not isinstance(value, str) or not INVITE_CODE_PATTERN.fullmatch(value):
            raise ValueError("INVITE_CODE: только латиница, цифры, _ и -, не длиннее 64 символов")
        return value

    @field_validator("timezone")
    @classmethod
    def _check_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError(f"Неизвестный часовой пояс: {value}") from error
        return value
