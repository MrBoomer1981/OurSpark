"""Контент игры из services/api/content/: карточки, шкалы, реплики питомца.

Файлы проверяются при старте: ошибка в них не даст api запуститься, а не всплывёт у пары посреди дня.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

CONTENT_DIR = Path(__file__).resolve().parents[2] / "content"
KINDS = ("choice",)  # совместный выбор; остальные типы — этап 4


@dataclass(frozen=True)
class Option:
    key: str
    text: str
    trait: str


@dataclass(frozen=True)
class Card:
    key: str
    kind: str
    text: str
    options: tuple[Option, ...]

    def option(self, key: str) -> Option | None:
        return next((option for option in self.options if option.key == key), None)


@dataclass(frozen=True)
class Content:
    cards: dict[str, Card]
    traits: dict[str, str]  # ключ шкалы → название
    lines: dict[str, dict[str, list[str]]]  # группа → случай → реплики

    def line(self, group: str, case: str, seed: int, **values: str) -> str:
        """Одна реплика из группы. Один и тот же seed — одна и та же реплика при каждом показе."""
        options = self.lines[group][case]
        return options[seed % len(options)].format(**values)


def load(directory: Path = CONTENT_DIR) -> Content:
    traits = _read(directory / "pet.yaml")["traits"]
    cards = [_card(raw, traits) for raw in _read(directory / "prompts.yaml")]
    keys = [card.key for card in cards]
    duplicates = {key for key in keys if keys.count(key) > 1}
    if duplicates:
        raise ValueError(f"prompts.yaml: ключи карточек повторяются: {sorted(duplicates)}")
    lines = _read(directory / "lines.yaml")
    _check_lines(lines, traits)
    return Content(cards={card.key: card for card in cards}, traits=traits, lines=lines)


def _read(path: Path) -> Any:
    with path.open(encoding="utf-8") as file:
        return yaml.safe_load(file)


def _card(raw: dict[str, Any], traits: dict[str, str]) -> Card:
    key = raw.get("key", "?")
    where = f"prompts.yaml, карточка {key}"
    if raw.get("kind") not in KINDS:
        raise ValueError(f"{where}: неизвестный kind {raw.get('kind')!r}")
    if not raw.get("text"):
        raise ValueError(f"{where}: нет текста")
    if not isinstance(raw.get("text"), str):
        raise ValueError(f"{where}: текст должен быть строкой (двоеточие — в кавычках)")
    options = tuple(Option(o["key"], o["text"], o["trait"]) for o in raw.get("options", []))
    for option in options:
        if not isinstance(option.text, str) or not option.text:
            raise ValueError(f"{where}: у варианта {option.key} текст должен быть строкой (двоеточие — в кавычках)")
    if len(options) < 2:
        raise ValueError(f"{where}: нужно хотя бы два варианта")
    if len({option.key for option in options}) != len(options):
        raise ValueError(f"{where}: ключи вариантов повторяются")
    for option in options:
        if option.trait not in traits:
            raise ValueError(f"{where}: у варианта {option.key} неизвестная шкала {option.trait!r}")
    return Card(key=key, kind=raw["kind"], text=raw["text"], options=options)


def _check_lines(lines: dict[str, dict[str, list[str]]], traits: dict[str, str]) -> None:
    required = {
        "nest": ["idle", "your_turn", "partner_answered", "waiting", "ready", "done"],
        "answer": list(traits),
        "reveal": ["same", "different"],
    }
    for group, cases in required.items():
        for case in cases:
            if not lines.get(group, {}).get(case):
                raise ValueError(f"lines.yaml: нет реплик {group}.{case}")
    for group, cases in lines.items():
        for case, items in cases.items():
            for item in items:
                if not isinstance(item, str):
                    raise ValueError(f"lines.yaml: {group}.{case}: {item!r} — не текст (двоеточие — в кавычках)")
