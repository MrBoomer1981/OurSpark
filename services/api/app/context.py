"""Общий контекст api: конфиг, контент и каналы связи. Собирается один раз на старте."""

from dataclasses import dataclass

from app.config import Config
from app.content import Content
from app.notify.push import Push
from app.telegram.client import Telegram


@dataclass(frozen=True)
class Context:
    config: Config
    content: Content
    telegram: Telegram
    push: Push
