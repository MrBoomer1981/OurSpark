"""Конфиг из переменных окружения: на Railway — из Variables, локально — из .env."""

from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: SecretStr
    timezone: str = "Europe/Moscow"  # часовой пояс новых пар; каждая пара может сменить свой в /settings
    db_path: Path = Path("data/bot.db")
    themes_dir: Path = Path("themes")
    debug: bool = False
    new_pairs: bool = True  # false — бот не принимает новые пары, собранные играют дальше

    @field_validator("timezone")
    @classmethod
    def _check_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError(f"Неизвестный часовой пояс: {value}") from error
        return value
