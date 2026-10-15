"""Источники тем.

Темы делятся на две группы. Простые (themes/simple.txt) снимаются за минуту там, где
ты сейчас; над темами посложнее (themes/creative.txt) надо подумать или что-то поискать.
Каждый день бот берёт простую тему с вероятностью SIMPLE_SHARE, иначе — посложнее.
Кнопка «Другая тема» всегда даёт простую.

Тема, по которой прислали хотя бы одно фото, использована и больше не выпадает.
Показанные без фото (и заменённые кнопкой) могут вернуться, но не раньше чем через
RECENT_WITHOUT_REPEAT показов; среди остальных бот берёт те, что показывались реже.

Интерфейс общий (ThemeSource), чтобы позже можно было подключить, например, генерацию
через AI, а списки оставить запасными.
"""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from loguru import logger

SIMPLE_SHARE = 0.7
RECENT_WITHOUT_REPEAT = 30
SEPARATOR = " — "


@dataclass(frozen=True, slots=True)
class Theme:
    title: str
    hint: str = ""


class ThemeSource(Protocol):
    async def pick(self, history: list[str], used: set[str], *, simple_only: bool = False) -> Theme:
        """Выбрать тему.

        history — названия всех показанных тем, от старых к новым; used — темы, по которым
        уже прислали фото; simple_only — только из простых (для кнопки «Другая тема»).
        """
        ...


def read_themes(path: Path) -> list[Theme]:
    themes: dict[str, Theme] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        title, _, hint = line.partition(SEPARATOR)
        themes.setdefault(title.strip(), Theme(title.strip(), hint.strip()))
    return list(themes.values())


class ListThemes:
    """Темы из двух файлов: простые и посложнее."""

    def __init__(self, simple: list[Theme], creative: list[Theme]) -> None:
        if not simple and not creative:
            raise ValueError("Список тем пуст")
        # По названию бот узнаёт тему в истории, поэтому оно должно быть уникальным в обеих группах.
        taken = {theme.title for theme in simple}
        self.simple = simple
        self.creative = [theme for theme in creative if theme.title not in taken]

    @classmethod
    def load(cls, folder: Path) -> ListThemes:
        return cls(read_themes(folder / "simple.txt"), read_themes(folder / "creative.txt"))

    def unused(self, used: set[str]) -> tuple[int, int]:
        """Сколько тем ещё не использовано: (простых, посложнее)."""
        return (
            sum(theme.title not in used for theme in self.simple),
            sum(theme.title not in used for theme in self.creative),
        )

    async def pick(self, history: list[str], used: set[str], *, simple_only: bool = False) -> Theme:
        if simple_only or random.random() < SIMPLE_SHARE:
            groups = (self.simple, self.creative)
        else:
            groups = (self.creative, self.simple)
        shown = Counter(history)
        recent = set(history[-RECENT_WITHOUT_REPEAT:])
        for group in groups:
            fresh = [theme for theme in group if theme.title not in used]
            if fresh:
                return _least_shown([t for t in fresh if t.title not in recent] or fresh, shown)
        logger.warning("Все темы использованы — повторяем старые. Пора дописать новые в themes/")
        everything = [*groups[0], *groups[1]]
        return _least_shown([t for t in everything if t.title not in recent] or everything, shown)


def _least_shown(candidates: list[Theme], shown: Counter[str]) -> Theme:
    fewest = min(shown[theme.title] for theme in candidates)
    return random.choice([theme for theme in candidates if shown[theme.title] == fewest])
