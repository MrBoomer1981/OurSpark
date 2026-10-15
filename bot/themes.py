"""Источники тем.

Сейчас источник один — список из themes.txt. Интерфейс общий (ThemeSource), чтобы
позже можно было подключить, например, генерацию через AI, а список оставить запасным.
"""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

RECENT_WITHOUT_REPEAT = 30
SEPARATOR = " — "


@dataclass(frozen=True, slots=True)
class Theme:
    title: str
    hint: str = ""


class ThemeSource(Protocol):
    async def pick(self, history: list[str]) -> Theme:
        """Выбрать тему. history — названия всех показанных тем, от старых к новым."""
        ...


class ListThemes:
    """Темы из файла: сначала те, что показывались реже других, без повтора последних 30."""

    def __init__(self, themes: list[Theme]) -> None:
        if not themes:
            raise ValueError("Список тем пуст")
        self.themes = themes

    @classmethod
    def load(cls, path: Path) -> ListThemes:
        themes: dict[str, Theme] = {}
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            title, _, hint = line.partition(SEPARATOR)
            themes.setdefault(title.strip(), Theme(title.strip(), hint.strip()))
        return cls(list(themes.values()))

    async def pick(self, history: list[str]) -> Theme:
        shown = Counter(history)
        recent = set(history[-RECENT_WITHOUT_REPEAT:])
        candidates = [theme for theme in self.themes if theme.title not in recent] or self.themes
        fewest = min(shown[theme.title] for theme in candidates)
        return random.choice([theme for theme in candidates if shown[theme.title] == fewest])
