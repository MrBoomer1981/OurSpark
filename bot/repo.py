"""Все запросы к базе.

Registry — общие операции: пары и кто в какой паре. Repo — запросы одной пары: каждый
запрос ограничен её pair_id, поэтому пары друг друга не видят.

Даты дней хранятся в часовом поясе пары (YYYY-MM-DD), моменты времени — в UTC.
Методы claim_* — брони событий: атомарный UPDATE … WHERE … IS NULL. True получает
только тот, кто забронировал первым, поэтому событие не уйдёт дважды.
"""

from __future__ import annotations

import datetime as dt
import secrets
from dataclasses import dataclass
from typing import Literal

import aiosqlite

from bot.themes import Theme

SaveResult = Literal["new", "replaced", "same", "ignored"]

# Отслеживаемые рассылки: момент события в days и условие «досылать уже поздно».
_DELIVERY_EVENTS = {
    "theme": ("theme_sent_at", "AND d.revealed_at IS NULL"),
    "exchange": ("exchanged_at", ""),
    "card": ("exchanged_at", ""),
}
# Таблицы с данными дней пары — их чистит /dev.
_DAY_TABLES = ("submissions", "theme_log", "deliveries", "reactions", "sent_messages", "early_open", "days")


@dataclass(frozen=True, slots=True)
class User:
    user_id: int
    name: str


@dataclass(frozen=True, slots=True)
class Pair:
    id: int
    invite_code: str


@dataclass(frozen=True, slots=True)
class Day:
    date: dt.date
    theme_title: str | None
    theme_hint: str | None
    theme_author: int | None  # кто предложил тему через /addtheme; None — тема из файла
    theme_sent_at: dt.datetime | None
    reminder_sent_at: dt.datetime | None
    revealed_at: dt.datetime | None  # вечернее событие уже было
    exchanged_at: dt.datetime | None  # оба получили фото друг друга
    skipped: bool  # бот проспал время темы до самого обмена

    @property
    def theme(self) -> Theme:
        return Theme(self.theme_title or "", self.theme_hint or "")


@dataclass(frozen=True, slots=True)
class Submission:
    date: dt.date
    user_id: int
    file_id: str
    kind: str  # "photo" — сжатое фото, "document" — картинка файлом
    caption: str | None
    media_group_id: str | None
    sent_at: dt.datetime


@dataclass(frozen=True, slots=True)
class CustomTheme:
    """Тема из копилки /addtheme."""

    id: int
    author_id: int
    title: str
    hint: str


def _iso(moment: dt.datetime) -> str:
    return moment.astimezone(dt.UTC).isoformat(timespec="seconds")


def _moment(value: str | None) -> dt.datetime | None:
    return dt.datetime.fromisoformat(value) if value else None


def _day(row: aiosqlite.Row) -> Day:
    return Day(
        date=dt.date.fromisoformat(row["date"]),
        theme_title=row["theme_title"],
        theme_hint=row["theme_hint"],
        theme_author=row["theme_author"],
        theme_sent_at=_moment(row["theme_sent_at"]),
        reminder_sent_at=_moment(row["reminder_sent_at"]),
        revealed_at=_moment(row["revealed_at"]),
        exchanged_at=_moment(row["exchanged_at"]),
        skipped=bool(row["skipped"]),
    )


def _submission(row: aiosqlite.Row) -> Submission:
    return Submission(
        date=dt.date.fromisoformat(row["date"]),
        user_id=row["user_id"],
        file_id=row["file_id"],
        kind=row["kind"],
        caption=row["caption"],
        media_group_id=row["media_group_id"],
        sent_at=dt.datetime.fromisoformat(row["sent_at"]),
    )


class _Queries:
    def __init__(self, conn: aiosqlite.Connection) -> None:
        self.conn = conn

    async def _one(self, sql: str, *params: object) -> aiosqlite.Row | None:
        async with self.conn.execute(sql, params) as cursor:
            return await cursor.fetchone()

    async def _all(self, sql: str, *params: object) -> list[aiosqlite.Row]:
        async with self.conn.execute(sql, params) as cursor:
            return list(await cursor.fetchall())

    async def _run(self, sql: str, *params: object) -> int:
        """Выполнить запрос и вернуть число затронутых строк."""
        async with self.conn.execute(sql, params) as cursor:
            return cursor.rowcount

    async def _count(self, sql: str, *params: object) -> int:
        row = await self._one(sql, *params)
        return row[0] if row else 0


class Registry(_Queries):
    """Пары и участники: кто в какой паре, создание пары, вход по ссылке, выход."""

    async def user_pair(self, user_id: int) -> int | None:
        row = await self._one(
            "SELECT u.pair_id FROM users u JOIN pairs p ON p.id = u.pair_id "
            "WHERE u.user_id = ? AND p.closed_at IS NULL",
            user_id,
        )
        return row["pair_id"] if row else None

    async def get_pair(self, pair_id: int) -> Pair | None:
        row = await self._one(
            "SELECT id, invite_code FROM pairs WHERE id = ? AND closed_at IS NULL", pair_id
        )
        return Pair(row["id"], row["invite_code"]) if row else None

    async def pair_by_code(self, code: str) -> Pair | None:
        row = await self._one(
            "SELECT id, invite_code FROM pairs WHERE invite_code = ? AND closed_at IS NULL", code
        )
        return Pair(row["id"], row["invite_code"]) if row else None

    async def create_pair(self, user_id: int, name: str, at: dt.datetime) -> Pair:
        code = secrets.token_urlsafe(12)  # только символы, которые Telegram пропускает в ссылке
        async with self.conn.execute(
            "INSERT INTO pairs (invite_code, created_at) VALUES (?, ?)", (code, _iso(at))
        ) as cursor:
            pair_id = cursor.lastrowid or 0
        await self._run(
            "INSERT INTO users (user_id, name, joined_at, pair_id) VALUES (?, ?, ?, ?) "
            "ON CONFLICT (user_id) DO UPDATE SET name = excluded.name, "
            "joined_at = excluded.joined_at, pair_id = excluded.pair_id",
            user_id,
            name,
            _iso(at),
            pair_id,
        )
        return Pair(pair_id, code)

    async def join_pair(self, pair_id: int, user_id: int, name: str, at: dt.datetime, limit: int) -> bool:
        """Войти в пару, если в ней есть место. Проверка и запись — один запрос, третьим не войти."""
        changed = await self._run(
            "INSERT INTO users (user_id, name, joined_at, pair_id) "
            "SELECT ?, ?, ?, ? WHERE (SELECT COUNT(*) FROM users WHERE pair_id = ?) < ? "
            "ON CONFLICT (user_id) DO UPDATE SET name = excluded.name, "
            "joined_at = excluded.joined_at, pair_id = excluded.pair_id",
            user_id,
            name,
            _iso(at),
            pair_id,
            pair_id,
            limit,
        )
        return changed == 1

    async def leave_pair(self, pair_id: int, at: dt.datetime) -> None:
        """Распустить пару: она закрывается, участники свободны. История остаётся в базе."""
        await self._run(
            "UPDATE pairs SET closed_at = ? WHERE id = ? AND closed_at IS NULL", _iso(at), pair_id
        )
        await self._run("UPDATE users SET pair_id = NULL WHERE pair_id = ?", pair_id)

    async def active_pairs(self, size: int) -> list[int]:
        """Собранные пары — те, для которых работает расписание."""
        rows = await self._all(
            "SELECT p.id FROM pairs p WHERE p.closed_at IS NULL "
            "AND (SELECT COUNT(*) FROM users u WHERE u.pair_id = p.id) >= ? ORDER BY p.id",
            size,
        )
        return [row["id"] for row in rows]

    async def stats(self) -> tuple[int, int]:
        """(открытых пар, людей в парах) — для лога при старте."""
        pairs = await self._count("SELECT COUNT(*) FROM pairs WHERE closed_at IS NULL")
        people = await self._count(
            "SELECT COUNT(*) FROM users u JOIN pairs p ON p.id = u.pair_id WHERE p.closed_at IS NULL"
        )
        return pairs, people


class Repo(_Queries):
    """Запросы одной пары. Каждый запрос ограничен pair_id."""

    def __init__(self, conn: aiosqlite.Connection, pair_id: int) -> None:
        super().__init__(conn)
        self.pair_id = pair_id

    # ── Участники ──

    async def members(self) -> list[User]:
        rows = await self._all(
            "SELECT user_id, name FROM users WHERE pair_id = ? ORDER BY joined_at, user_id",
            self.pair_id,
        )
        return [User(row["user_id"], row["name"]) for row in rows]

    async def member_count(self) -> int:
        return await self._count("SELECT COUNT(*) FROM users WHERE pair_id = ?", self.pair_id)

    async def get_member(self, user_id: int) -> User | None:
        row = await self._one(
            "SELECT user_id, name FROM users WHERE user_id = ? AND pair_id = ?", user_id, self.pair_id
        )
        return User(row["user_id"], row["name"]) if row else None

    # ── Настройки пары (ключ-значение: новая настройка не требует миграции) ──

    async def get_setting(self, key: str) -> str | None:
        row = await self._one(
            "SELECT value FROM pair_settings WHERE pair_id = ? AND key = ?", self.pair_id, key
        )
        return row["value"] if row else None

    async def set_setting(self, key: str, value: str) -> None:
        await self._run(
            "INSERT INTO pair_settings (pair_id, key, value) VALUES (?, ?, ?) "
            "ON CONFLICT (pair_id, key) DO UPDATE SET value = excluded.value",
            self.pair_id,
            key,
            value,
        )

    # ── Дни ──

    async def get_day(self, day: dt.date) -> Day | None:
        row = await self._one(
            "SELECT * FROM days WHERE pair_id = ? AND date = ?", self.pair_id, day.isoformat()
        )
        return _day(row) if row else None

    async def ensure_day(self, day: dt.date) -> None:
        await self._run(
            "INSERT OR IGNORE INTO days (pair_id, date) VALUES (?, ?)", self.pair_id, day.isoformat()
        )

    async def claim_theme(
        self, day: dt.date, theme: Theme, at: dt.datetime, author_id: int | None = None
    ) -> bool:
        changed = await self._run(
            "UPDATE days SET theme_title = ?, theme_hint = ?, theme_author = ?, theme_sent_at = ? "
            "WHERE pair_id = ? AND date = ? AND theme_sent_at IS NULL AND skipped = 0",
            theme.title,
            theme.hint,
            author_id,
            _iso(at),
            self.pair_id,
            day.isoformat(),
        )
        return changed == 1

    async def replace_theme(self, day: dt.date, old_title: str, theme: Theme) -> bool:
        """Сменить тему, только если её никто не успел сменить и фото за день ещё нет.

        Новая тема всегда из файла, поэтому автор темы сбрасывается.
        """
        iso = day.isoformat()
        changed = await self._run(
            "UPDATE days SET theme_title = ?, theme_hint = ?, theme_author = NULL "
            "WHERE pair_id = ? AND date = ? AND theme_title = ? AND revealed_at IS NULL "
            "AND NOT EXISTS (SELECT 1 FROM submissions WHERE pair_id = ? AND date = ?)",
            theme.title,
            theme.hint,
            self.pair_id,
            iso,
            old_title,
            self.pair_id,
            iso,
        )
        return changed == 1

    async def mark_skipped(self, day: dt.date) -> None:
        await self.ensure_day(day)
        await self._run(
            "UPDATE days SET skipped = 1 WHERE pair_id = ? AND date = ? AND theme_sent_at IS NULL",
            self.pair_id,
            day.isoformat(),
        )

    async def claim_reminder(self, day: dt.date, at: dt.datetime) -> bool:
        changed = await self._run(
            "UPDATE days SET reminder_sent_at = ? WHERE pair_id = ? AND date = ? "
            "AND reminder_sent_at IS NULL AND theme_sent_at IS NOT NULL AND revealed_at IS NULL",
            _iso(at),
            self.pair_id,
            day.isoformat(),
        )
        return changed == 1

    async def claim_reveal(self, day: dt.date, at: dt.datetime) -> bool:
        changed = await self._run(
            "UPDATE days SET revealed_at = ? WHERE pair_id = ? AND date = ? AND revealed_at IS NULL "
            "AND theme_sent_at IS NOT NULL AND skipped = 0",
            _iso(at),
            self.pair_id,
            day.isoformat(),
        )
        return changed == 1

    async def claim_exchange(self, day: dt.date, at: dt.datetime) -> bool:
        """Обмен бронируется, только если оба фото уже на месте — в том же запросе."""
        iso = day.isoformat()
        changed = await self._run(
            "UPDATE days SET exchanged_at = ? WHERE pair_id = ? AND date = ? AND exchanged_at IS NULL "
            "AND (SELECT COUNT(*) FROM submissions WHERE pair_id = ? AND date = ?) >= 2",
            _iso(at),
            self.pair_id,
            iso,
            self.pair_id,
            iso,
        )
        return changed == 1

    async def unrevealed_days_before(self, day: dt.date) -> list[dt.date]:
        rows = await self._all(
            "SELECT date FROM days WHERE pair_id = ? AND date < ? AND theme_sent_at IS NOT NULL "
            "AND revealed_at IS NULL AND skipped = 0 ORDER BY date",
            self.pair_id,
            day.isoformat(),
        )
        return [dt.date.fromisoformat(row["date"]) for row in rows]

    async def streak_marks(self) -> tuple[set[dt.date], set[dt.date]]:
        """Дни с обменом и пропущенные дни — из них считается серия."""
        rows = await self._all(
            "SELECT date, exchanged_at IS NOT NULL AS exchanged, skipped FROM days WHERE pair_id = ?",
            self.pair_id,
        )
        exchanged = {dt.date.fromisoformat(row["date"]) for row in rows if row["exchanged"]}
        skipped = {dt.date.fromisoformat(row["date"]) for row in rows if row["skipped"]}
        return exchanged, skipped

    async def exchange_count(self) -> int:
        return await self._count(
            "SELECT COUNT(*) FROM days WHERE pair_id = ? AND exchanged_at IS NOT NULL", self.pair_id
        )

    async def history_count(self) -> int:
        return await self._count(
            "SELECT COUNT(*) FROM days WHERE pair_id = ? AND theme_sent_at IS NOT NULL", self.pair_id
        )

    async def history_page(self, offset: int, limit: int) -> list[tuple[Day, int]]:
        """Дни с темой, от новых к старым, и сколько фото прислали в каждый."""
        rows = await self._all(
            "SELECT d.*, (SELECT COUNT(*) FROM submissions s "
            "WHERE s.pair_id = d.pair_id AND s.date = d.date) AS photos "
            "FROM days d WHERE d.pair_id = ? AND d.theme_sent_at IS NOT NULL "
            "ORDER BY d.date DESC LIMIT ? OFFSET ?",
            self.pair_id,
            limit,
            offset,
        )
        return [(_day(row), row["photos"]) for row in rows]

    # ── Темы ──

    async def log_theme(self, day: dt.date, title: str, at: dt.datetime) -> None:
        await self._run(
            "INSERT INTO theme_log (pair_id, date, title, shown_at) VALUES (?, ?, ?, ?)",
            self.pair_id,
            day.isoformat(),
            title,
            _iso(at),
        )

    async def theme_history(self) -> list[str]:
        rows = await self._all("SELECT title FROM theme_log WHERE pair_id = ? ORDER BY id", self.pair_id)
        return [row["title"] for row in rows]

    async def used_themes(self) -> set[str]:
        """Темы, по которым пара прислала хотя бы одно фото: больше они не выпадают."""
        rows = await self._all(
            "SELECT DISTINCT d.theme_title FROM days d WHERE d.pair_id = ? AND d.theme_title IS NOT NULL "
            "AND EXISTS (SELECT 1 FROM submissions s WHERE s.pair_id = d.pair_id AND s.date = d.date)",
            self.pair_id,
        )
        return {row["theme_title"] for row in rows}

    async def themes_shown_on(self, day: dt.date) -> int:
        return await self._count(
            "SELECT COUNT(*) FROM theme_log WHERE pair_id = ? AND date = ?", self.pair_id, day.isoformat()
        )

    # ── Фото ──

    async def get_submissions(self, day: dt.date) -> list[Submission]:
        rows = await self._all(
            "SELECT * FROM submissions WHERE pair_id = ? AND date = ? ORDER BY sent_at",
            self.pair_id,
            day.isoformat(),
        )
        return [_submission(row) for row in rows]

    async def save_submission(self, photo: Submission) -> SaveResult:
        """Сохранить фото дня: первое за день — «new», другое фото вместо прежнего — «replaced».

        То же самое фото ещё раз — «same»: Telegram передоставил сообщение после рестарта.
        Остальные фото того же альбома — «ignored»: из альбома берём одно.
        """
        iso = photo.date.isoformat()
        fields = (photo.file_id, photo.kind, photo.caption, photo.media_group_id, _iso(photo.sent_at))
        inserted = await self._run(
            "INSERT OR IGNORE INTO submissions "
            "(pair_id, date, user_id, file_id, kind, caption, media_group_id, sent_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            self.pair_id,
            iso,
            photo.user_id,
            *fields,
        )
        if inserted:
            return "new"
        stored = await self._one(
            "SELECT file_id FROM submissions WHERE pair_id = ? AND date = ? AND user_id = ?",
            self.pair_id,
            iso,
            photo.user_id,
        )
        if stored is not None and stored["file_id"] == photo.file_id:
            return "same"
        replaced = await self._run(
            "UPDATE submissions "
            "SET file_id = ?, kind = ?, caption = ?, media_group_id = ?, sent_at = ? "
            "WHERE pair_id = ? AND date = ? AND user_id = ? AND (? IS NULL OR media_group_id IS NOT ?)",
            *fields,
            self.pair_id,
            iso,
            photo.user_id,
            photo.media_group_id,
            photo.media_group_id,
        )
        return "replaced" if replaced else "ignored"

    # ── Доставка: кому реально ушли тема, альбом обмена и карточка ──

    async def delivered_to(self, day: dt.date, kind: str) -> set[int]:
        rows = await self._all(
            "SELECT user_id FROM deliveries WHERE pair_id = ? AND date = ? AND kind = ?",
            self.pair_id,
            day.isoformat(),
            kind,
        )
        return {row["user_id"] for row in rows}

    async def mark_delivered(self, day: dt.date, user_id: int, kind: str, at: dt.datetime) -> None:
        await self._run(
            "INSERT OR IGNORE INTO deliveries (pair_id, date, user_id, kind, delivered_at) "
            "VALUES (?, ?, ?, ?, ?)",
            self.pair_id,
            day.isoformat(),
            user_id,
            kind,
            _iso(at),
        )

    async def undelivered_days(
        self, kind: str, since: dt.date, happened_before: dt.datetime
    ) -> list[dt.date]:
        """Дни не раньше since, где событие kind случилось до happened_before, но дошло не всем."""
        column, too_late = _DELIVERY_EVENTS[kind]
        rows = await self._all(
            f"SELECT d.date FROM days d WHERE d.pair_id = ? AND d.date >= ? AND d.{column} < ? {too_late} "
            "AND (SELECT COUNT(*) FROM deliveries x "
            "WHERE x.pair_id = d.pair_id AND x.date = d.date AND x.kind = ?) "
            "< (SELECT COUNT(*) FROM users WHERE pair_id = d.pair_id) ORDER BY d.date",
            self.pair_id,
            since.isoformat(),
            _iso(happened_before),
            kind,
        )
        return [dt.date.fromisoformat(row["date"]) for row in rows]

    # ── Копилка тем друг для друга (/addtheme) ──

    async def add_custom_theme(self, author_id: int, theme: Theme, at: dt.datetime) -> int:
        async with self.conn.execute(
            "INSERT INTO custom_themes (pair_id, author_id, title, hint, created_at) VALUES (?, ?, ?, ?, ?)",
            (self.pair_id, author_id, theme.title, theme.hint, _iso(at)),
        ) as cursor:
            return cursor.lastrowid or 0

    async def custom_pending_count(self, author_id: int) -> int:
        return await self._count(
            "SELECT COUNT(*) FROM custom_themes WHERE pair_id = ? AND author_id = ? AND shown_on IS NULL",
            self.pair_id,
            author_id,
        )

    async def next_custom_theme(self) -> CustomTheme | None:
        """Самая старая тема из копилки — сначала от того, чья тема выпадала не последней."""
        row = await self._one(
            "SELECT id, author_id, title, hint FROM custom_themes WHERE pair_id = ? AND shown_on IS NULL "
            "ORDER BY author_id = (SELECT author_id FROM custom_themes WHERE pair_id = ? "
            "AND shown_on IS NOT NULL ORDER BY shown_on DESC, id DESC LIMIT 1), id LIMIT 1",
            self.pair_id,
            self.pair_id,
        )
        if row is None:
            return None
        return CustomTheme(row["id"], row["author_id"], row["title"], row["hint"])

    async def mark_custom_shown(self, theme_id: int, day: dt.date) -> None:
        await self._run(
            "UPDATE custom_themes SET shown_on = ? WHERE pair_id = ? AND id = ?",
            day.isoformat(),
            self.pair_id,
            theme_id,
        )

    async def return_custom_theme(self, day: dt.date, author_id: int, title: str) -> None:
        """Тему из копилки сменили кнопкой — она возвращается в очередь."""
        await self._run(
            "UPDATE custom_themes SET shown_on = NULL "
            "WHERE pair_id = ? AND shown_on = ? AND author_id = ? AND title = ?",
            self.pair_id,
            day.isoformat(),
            author_id,
            title,
        )

    async def delete_custom_theme(self, theme_id: int, author_id: int) -> bool:
        """Удалить свою тему из копилки, пока она не выпала."""
        deleted = await self._run(
            "DELETE FROM custom_themes WHERE pair_id = ? AND id = ? AND author_id = ? AND shown_on IS NULL",
            self.pair_id,
            theme_id,
            author_id,
        )
        return deleted == 1

    # ── Реакции ──

    async def get_reaction(self, day: dt.date, user_id: int) -> str | None:
        row = await self._one(
            "SELECT emoji FROM reactions WHERE pair_id = ? AND date = ? AND user_id = ?",
            self.pair_id,
            day.isoformat(),
            user_id,
        )
        return row["emoji"] if row else None

    async def set_reaction(self, day: dt.date, user_id: int, emoji: str, at: dt.datetime) -> None:
        await self._run(
            "INSERT INTO reactions (pair_id, date, user_id, emoji, at) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT (date, user_id) DO UPDATE SET emoji = excluded.emoji, at = excluded.at",
            self.pair_id,
            day.isoformat(),
            user_id,
            emoji,
            _iso(at),
        )

    # ── «Открыть раньше» ──

    async def add_early_vote(self, day: dt.date, user_id: int, at: dt.datetime) -> bool:
        """Отметить согласие открыть фото раньше. False — согласие уже было."""
        added = await self._run(
            "INSERT OR IGNORE INTO early_open (pair_id, date, user_id, at) VALUES (?, ?, ?, ?)",
            self.pair_id,
            day.isoformat(),
            user_id,
            _iso(at),
        )
        return added == 1

    async def early_votes(self, day: dt.date) -> set[int]:
        rows = await self._all(
            "SELECT user_id FROM early_open WHERE pair_id = ? AND date = ?", self.pair_id, day.isoformat()
        )
        return {row["user_id"] for row in rows}

    # ── Отправленные фото: чьё фото в каком сообщении (для ответов) ──

    async def remember_message(self, chat_id: int, message_id: int, day: dt.date, owner_id: int) -> None:
        await self._run(
            "INSERT OR REPLACE INTO sent_messages (chat_id, message_id, pair_id, date, owner_id) "
            "VALUES (?, ?, ?, ?, ?)",
            chat_id,
            message_id,
            self.pair_id,
            day.isoformat(),
            owner_id,
        )

    async def message_owner(self, chat_id: int, message_id: int) -> tuple[dt.date, int] | None:
        """День и автор фото, к которому относится сообщение, — или None, если это не фото дня."""
        row = await self._one(
            "SELECT date, owner_id FROM sent_messages WHERE chat_id = ? AND message_id = ? AND pair_id = ?",
            chat_id,
            message_id,
            self.pair_id,
        )
        return (dt.date.fromisoformat(row["date"]), row["owner_id"]) if row else None

    # ── Служебное (/dev) ──

    async def reset_day(self, day: dt.date) -> None:
        iso = day.isoformat()
        await self._run(
            "UPDATE custom_themes SET shown_on = NULL WHERE pair_id = ? AND shown_on = ?", self.pair_id, iso
        )
        for table in _DAY_TABLES:
            await self._run(f"DELETE FROM {table} WHERE pair_id = ? AND date = ?", self.pair_id, iso)

    async def clear_history(self) -> None:
        await self._run("UPDATE custom_themes SET shown_on = NULL WHERE pair_id = ?", self.pair_id)
        for table in _DAY_TABLES:
            await self._run(f"DELETE FROM {table} WHERE pair_id = ?", self.pair_id)
