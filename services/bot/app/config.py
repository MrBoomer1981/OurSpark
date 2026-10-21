"""Конфиг из переменных окружения: на Railway — из Variables, локально — из .env."""

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: SecretStr
    web_app_url: str  # адрес Mini App — публичный домен web
    api_url: str  # api по приватной сети, например http://api.railway.internal:8000
    internal_secret: SecretStr  # общий секрет с api: подтверждение входа в PWA
    debug: bool = False

    @field_validator("web_app_url")
    @classmethod
    def _check_web_app_url(cls, value: str) -> str:
        if not value.startswith("https://"):
            raise ValueError("WEB_APP_URL должен начинаться с https://: Telegram открывает Mini App только по HTTPS")
        return value
