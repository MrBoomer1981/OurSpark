"""Реестр фич.

Порядок важен: в нём подключаются роутеры (первый подходящий хендлер забирает
сообщение) и вызываются задачи планировщика. Новая фича = модуль рядом + строка здесь.
"""

from bot.config import Config
from bot.feature import Feature
from bot.features import (
    daily_theme,
    dev,
    exchange,
    fallback,
    history,
    onboarding,
    partner_themes,
    photos,
    reactions,
    reminder,
    settings,
)


def build_features(config: Config) -> list[Feature]:
    features = [
        daily_theme.feature,
        photos.feature,
        partner_themes.feature,
        reactions.feature,
        reminder.feature,
        exchange.feature,
        history.feature,
        settings.feature,
        onboarding.feature,
    ]
    if config.debug:
        features.append(dev.feature)
    features.append(fallback.feature)  # всегда последний: отвечает на всё, что не поймали другие
    return features
