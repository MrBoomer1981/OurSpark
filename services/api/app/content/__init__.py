"""Контент игры из services/api/content/: карточки, темы, питомец, реплики.

Файлы проверяются при старте: ошибка в них не даст api запуститься, а не всплывёт у пары посреди дня.
"""

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

CONTENT_DIR = Path(__file__).resolve().parents[2] / "content"
KINDS = ("choice",)  # совместный выбор; остальные типы — этап 4
RELIC_SERIES = 3  # реликвия темы — за столько завершённых посланий этой темы


@dataclass(frozen=True)
class Option:
    key: str
    text: str
    trait: str
    chronicle: str | None  # запись летописи, если вариант выбрали оба


@dataclass(frozen=True)
class Card:
    key: str
    kind: str
    theme: str
    text: str
    options: tuple[Option, ...]

    def option(self, key: str) -> Option | None:
        return next((option for option in self.options if option.key == key), None)


@dataclass(frozen=True)
class Theme:
    key: str
    name: str
    relic: str
    relic_text: str


@dataclass(frozen=True)
class Stage:
    key: str
    name: str
    sparks: int  # столько искр пара должна заработать за всё время
    line: str | None  # реакция питомца на рост; у первой стадии её нет


@dataclass(frozen=True)
class Level:
    """Порог шкалы и привычка, которую он открывает."""

    key: str
    at: int
    habit: str  # описание на экране «Питомец»
    line: str  # реплика питомца в Гнезде


@dataclass(frozen=True)
class Trait:
    key: str
    name: str
    levels: tuple[Level, ...]  # по возрастанию порога

    def level(self, key: str) -> Level | None:
        return next((level for level in self.levels if level.key == key), None)

    def next_at(self, value: int) -> int | None:
        """Следующий порог выше value; None — открыто всё."""
        return next((level.at for level in self.levels if level.at > value), None)


@dataclass(frozen=True)
class Requirement:
    """Когда предмет появляется в продаже: стадия или порог шкалы."""

    stage: str | None = None
    trait: str | None = None
    at: int = 0


@dataclass(frozen=True)
class Item:
    key: str
    slot: str
    name: str
    price: int
    requires: Requirement | None
    line: str  # реакция питомца на обнову


@dataclass(frozen=True)
class Content:
    cards: dict[str, Card]
    themes: dict[str, Theme]
    stages: tuple[Stage, ...]  # по порядку роста; первая открыта с самого начала
    traits: dict[str, Trait]
    slots: dict[str, str]  # ключ слота → название, в порядке показа
    items: dict[str, Item]
    lines: dict[str, dict[str, list[str]]]  # группа → случай → реплики

    def line(self, group: str, case: str, seed: int, **values: str) -> str:
        """Одна реплика из группы. Один и тот же seed — одна и та же реплика при каждом показе."""
        return pick(self.lines[group][case], seed).format(**values)

    def stage(self, key: str) -> Stage | None:
        return next((stage for stage in self.stages if stage.key == key), None)


def pick(options: list[str], seed: int) -> str:
    return options[seed % len(options)]


def load(directory: Path = CONTENT_DIR) -> Content:
    pet = _read(directory / "pet.yaml")
    traits = _traits(pet.get("traits"))
    stages = _stages(pet.get("stages"))
    slots = _slots(pet.get("slots"))
    items = _items(pet.get("items"), stages, traits, slots)
    themes = _themes(_read(directory / "themes.yaml"))
    cards = _cards(_read(directory / "prompts.yaml"), traits, themes)
    lines = _read(directory / "lines.yaml")
    _check_lines(lines, traits)
    return Content(
        cards=cards, themes=themes, stages=stages, traits=traits, slots=slots, items=items, lines=lines
    )


def _read(path: Path) -> Any:
    with path.open(encoding="utf-8") as file:
        return yaml.safe_load(file)


def _mapping(raw: Any, where: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"{where}: ожидались поля «ключ: значение», а не {raw!r}")
    return raw


def _text(raw: dict[str, Any], field: str, where: str) -> str:
    value = raw.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{where}: {field} — нужен непустой текст (двоеточие — в кавычках)")
    return value


def _optional_text(raw: dict[str, Any], field: str, where: str) -> str | None:
    return None if raw.get(field) is None else _text(raw, field, where)


def _number(raw: dict[str, Any], field: str, where: str, *, minimum: int) -> int:
    value = raw.get(field)
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise ValueError(f"{where}: {field} — нужно целое число не меньше {minimum}")
    return value


def _unique(keys: list[str], where: str) -> None:
    duplicates = sorted(key for key, count in Counter(keys).items() if count > 1)
    if duplicates:
        raise ValueError(f"{where}: ключи повторяются: {duplicates}")


def _traits(raw: Any) -> dict[str, Trait]:
    if not isinstance(raw, dict) or not raw:
        raise ValueError("pet.yaml: нет шкал (traits)")
    traits = {}
    for key, body in raw.items():
        where = f"pet.yaml, шкала {key}"
        body = _mapping(body, where)
        levels = []
        for index, level in enumerate(body.get("levels") or []):
            level_where = f"{where}, порог №{index + 1}"
            level = _mapping(level, level_where)
            levels.append(
                Level(
                    key=_text(level, "key", level_where),
                    at=_number(level, "at", level_where, minimum=1),
                    habit=_text(level, "habit", level_where),
                    line=_text(level, "line", level_where),
                )
            )
        _unique([level.key for level in levels], where)
        if [level.at for level in levels] != sorted({level.at for level in levels}):
            raise ValueError(f"{where}: пороги должны расти и не повторяться")
        traits[key] = Trait(key=key, name=_text(body, "name", where), levels=tuple(levels))
    return traits


def _stages(raw: Any) -> tuple[Stage, ...]:
    if not isinstance(raw, list) or not raw:
        raise ValueError("pet.yaml: нет стадий (stages)")
    stages = []
    for index, body in enumerate(raw):
        where = f"pet.yaml, стадия №{index + 1}"
        body = _mapping(body, where)
        sparks = _number(body, "sparks", where, minimum=0)
        stages.append(
            Stage(
                key=_text(body, "key", where),
                name=_text(body, "name", where),
                sparks=sparks,
                line=_text(body, "line", where) if index > 0 else _optional_text(body, "line", where),
            )
        )
    _unique([stage.key for stage in stages], "pet.yaml, стадии")
    if stages[0].sparks != 0:
        raise ValueError("pet.yaml: первая стадия открыта с самого начала — sparks: 0")
    if any(later.sparks <= earlier.sparks for earlier, later in zip(stages, stages[1:])):
        raise ValueError("pet.yaml: пороги стадий должны расти")
    return tuple(stages)


def _slots(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict) or not raw:
        raise ValueError("pet.yaml: нет слотов (slots)")
    for key, name in raw.items():
        if not isinstance(name, str) or not name:
            raise ValueError(f"pet.yaml, слот {key}: нужно название")
    return dict(raw)


def _items(raw: Any, stages: tuple[Stage, ...], traits: dict[str, Trait], slots: dict[str, str]) -> dict[str, Item]:
    items = []
    for index, body in enumerate(raw or []):
        where = f"pet.yaml, предмет №{index + 1}"
        body = _mapping(body, where)
        slot = _text(body, "slot", where)
        if slot not in slots:
            raise ValueError(f"{where}: неизвестный слот {slot!r}")
        items.append(
            Item(
                key=_text(body, "key", where),
                slot=slot,
                name=_text(body, "name", where),
                price=_number(body, "price", where, minimum=1),
                requires=_requirement(body.get("requires"), where, stages, traits),
                line=_text(body, "line", where),
            )
        )
    _unique([item.key for item in items], "pet.yaml, предметы")
    return {item.key: item for item in items}


def _requirement(raw: Any, where: str, stages: tuple[Stage, ...], traits: dict[str, Trait]) -> Requirement | None:
    if raw is None:
        return None
    if isinstance(raw, dict) and set(raw) == {"stage"}:
        if raw["stage"] not in {stage.key for stage in stages}:
            raise ValueError(f"{where}: requires — неизвестная стадия {raw['stage']!r}")
        return Requirement(stage=raw["stage"])
    if isinstance(raw, dict) and set(raw) == {"trait", "at"}:
        if raw["trait"] not in traits:
            raise ValueError(f"{where}: requires — неизвестная шкала {raw['trait']!r}")
        return Requirement(trait=raw["trait"], at=_number(raw, "at", where, minimum=1))
    raise ValueError(f"{where}: requires — либо {{stage: <ключ>}}, либо {{trait: <ключ>, at: <число>}}")


def _themes(raw: Any) -> dict[str, Theme]:
    if not isinstance(raw, dict) or not raw:
        raise ValueError("themes.yaml: нет тем")
    themes = {}
    for key, body in raw.items():
        where = f"themes.yaml, тема {key}"
        body = _mapping(body, where)
        themes[key] = Theme(
            key=key,
            name=_text(body, "name", where),
            relic=_text(body, "relic", where),
            relic_text=_text(body, "relic_text", where),
        )
    return themes


def _cards(raw: Any, traits: dict[str, Trait], themes: dict[str, Theme]) -> dict[str, Card]:
    cards = [_card(body, traits, themes) for body in raw or []]
    _unique([card.key for card in cards], "prompts.yaml, карточки")
    per_theme = Counter(card.theme for card in cards)
    short = sorted(key for key in themes if per_theme[key] < RELIC_SERIES)
    if short:
        raise ValueError(f"themes.yaml: в темах {short} меньше {RELIC_SERIES} карточек — реликвию не получить")
    return {card.key: card for card in cards}


def _card(raw: Any, traits: dict[str, Trait], themes: dict[str, Theme]) -> Card:
    where = f"prompts.yaml, карточка {raw.get('key', '?') if isinstance(raw, dict) else raw!r}"
    raw = _mapping(raw, where)
    if raw.get("kind") not in KINDS:
        raise ValueError(f"{where}: неизвестный kind {raw.get('kind')!r}")
    theme = raw.get("theme")
    if theme not in themes:
        raise ValueError(f"{where}: неизвестная тема {theme!r} (темы — в themes.yaml)")
    options = []
    for index, body in enumerate(raw.get("options") or []):
        option_where = f"{where}, вариант №{index + 1}"
        body = _mapping(body, option_where)
        trait = body.get("trait")
        if trait not in traits:
            raise ValueError(f"{option_where}: неизвестная шкала {trait!r}")
        options.append(
            Option(
                key=_text(body, "key", option_where),
                text=_text(body, "text", option_where),
                trait=trait,
                chronicle=_optional_text(body, "chronicle", option_where),
            )
        )
    if len(options) < 2:
        raise ValueError(f"{where}: нужно хотя бы два варианта")
    _unique([option.key for option in options], where)
    return Card(
        key=_text(raw, "key", where),
        kind=raw["kind"],
        theme=theme,
        text=_text(raw, "text", where),
        options=tuple(options),
    )


def _check_lines(lines: dict[str, dict[str, list[str]]], traits: dict[str, Trait]) -> None:
    required = {
        "nest": ["idle", "your_turn", "partner_answered", "waiting", "ready", "done"],
        "answer": list(traits),
        "reveal": ["same", "different"],
        "chronicle": ["hatch", "stage", "habit", "relic"],
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
