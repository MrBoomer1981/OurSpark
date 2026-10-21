"""Конфиг из переменных окружения: на Railway — из Variables, локально — из .env."""

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str
    port: int = 8000  # на Railway задан явно: на него ссылается API_UPSTREAM у web
    debug: bool = False  # true — подробные логи, /api/docs, подставные пользователи и отладочная панель
    bot_token: SecretStr | None = None  # бот, в котором живёт Mini App; без него — только с DEBUG
    internal_secret: SecretStr | None = None  # общий секрет с bot: подтверждение входа в PWA
    new_pairs: bool = True  # false — новые пары не создаются, собранные играют дальше

    @model_validator(mode="after")
    def _check_token(self) -> "Config":
        if self.bot_token is None and not self.debug:
            raise ValueError("Нужен BOT_TOKEN: без него api запускается только с DEBUG=true")
        return self
