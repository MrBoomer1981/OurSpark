"""Все запросы к базе.

Даты дней хранятся в часовом поясе пары (YYYY-MM-DD), моменты времени — в UTC.
Методы claim_* — брони событий: атомарный UPDATE … WHERE … IS NULL. True получает
только тот, кто забронировал первым, поэтому событие не уйдёт дважды.
"""

from __future__ import annotations

import datetime as dt
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


@dataclass(frozen=True, slots=True)
class User:
    user_id: int
    name: str


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


class Repo:
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

    # ── Участники ──

    async def members(self) -> list[User]:
        rows = await self._all("SELECT user_id, name FROM users ORDER BY joined_at, user_id")
        return [User(row["user_id"], row["name"]) for row in rows]

    async def member_count(self) -> int:
        return await self._count("SELECT COUNT(*) FROM users")

    async def get_member(self, user_id: int) -> User | None:
        row = await self._one("SELECT user_id, name FROM users WHERE user_id = ?", user_id)
        return User(row["user_id"], row["name"]) if row else None

    async def add_member(self, user_id: int, name: str, limit: int) -> bool:
        """Добавить участника, если есть место. Проверка и вставка — один запрос, третьим не войти."""
        added = await self._run(
            "INSERT OR IGNORE INTO users (user_id, name, joined_at) "
            "SELECT ?, ?, ? WHERE (SELECT COUNT(*) FROM users) < ?",
            user_id,
            name,
            _iso(dt.datetime.now(dt.UTC)),
            limit,
        )
        return added == 1

    # ── Настройки (ключ-значение: новая настройка не требует миграции) ──

    async def get_setting(self, key: str) -> str | None:
        row = await self._one("SELECT value FROM settings WHERE key = ?", key)
        return row["value"] if row else None

    async def set_setting(self, key: str, value: str) -> None:
        await self._run(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
            key,
            value,
        )

    # ── Дни ──

    async def get_day(self, day: dt.date) -> Day | None:
        row = await self._one("SELECT * FROM days WHERE date = ?", day.isoformat())
        return _day(row) if row else None

    async def ensure_day(self, day: dt.date) -> None:
        await self._run("INSERT OR IGNORE INTO days (date) VALUES (?)", day.isoformat())

    async def claim_theme(
        self, day: dt.date, theme: Theme, at: dt.datetime, author_id: int | None = None
    ) -> bool:
        changed = await self._run(
            "UPDATE days SET theme_title = ?, theme_hint = ?, theme_author = ?, theme_sent_at = ? "
            "WHERE date = ? AND theme_sent_at IS NULL AND skipped = 0",
            theme.title,
            theme.hint,
            author_id,
            _iso(at),
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
            "WHERE date = ? AND theme_title = ? AND revealed_at IS NULL "
            "AND NOT EXISTS (SELECT 1 FROM submissions WHERE date = ?)",
            theme.title,
            theme.hint,
            iso,
            old_title,
            iso,
        )
        return changed == 1

    async def mark_skipped(self, day: dt.date) -> None:
        await self.ensure_day(day)
        await self._run(
            "UPDATE days SET skipped = 1 WHERE date = ? AND theme_sent_at IS NULL", day.isoformat()
        )

    async def claim_reminder(self, day: dt.date, at: dt.datetime) -> bool:
        changed = await self._run(
            "UPDATE days SET reminder_sent_at = ? WHERE date = ? AND reminder_sent_at IS NULL "
            "AND theme_sent_at IS NOT NULL AND revealed_at IS NULL",
            _iso(at),
            day.isoformat(),
        )
        return changed == 1

    async def claim_reveal(self, day: dt.date, at: dt.datetime) -> bool:
        changed = await self._run(
            "UPDATE days SET revealed_at = ? WHERE date = ? AND revealed_at IS NULL "
            "AND theme_sent_at IS NOT NULL AND skipped = 0",
            _iso(at),
            day.isoformat(),
        )
        return changed == 1

    async def claim_exchange(self, day: dt.date, at: dt.datetime) -> bool:
        """Обмен бронируется, только если оба фото уже на месте — в том же запросе."""
        iso = day.isoformat()
        changed = await self._run(
            "UPDATE days SET exchanged_at = ? WHERE date = ? AND exchanged_at IS NULL "
            "AND (SELECT COUNT(*) FROM submissions WHERE date = ?) >= 2",
            _iso(at),
            iso,
            iso,
        )
        return changed == 1

    async def unrevealed_days_before(self, day: dt.date) -> list[dt.date]:
        rows = await self._all(
            "SELECT date FROM days WHERE date < ? AND theme_sent_at IS NOT NULL "
            "AND revealed_at IS NULL AND skipped = 0 ORDER BY date",
            day.isoformat(),
        )
        return [dt.date.fromisoformat(row["date"]) for row in rows]

    async def streak_marks(self) -> tuple[set[dt.date], set[dt.date]]:
        """Дни с обменом и пропущенные дни — из них считается серия."""
        rows = await self._all(
            "SELECT date, exchanged_at IS NOT NULL AS exchanged, skipped FROM days"
        )
        exchanged = {dt.date.fromisoformat(row["date"]) for row in rows if row["exchanged"]}
        skipped = {dt.date.fromisoformat(row["date"]) for row in rows if row["skipped"]}
        return exchanged, skipped

    async def exchange_count(self) -> int:
        return await self._count("SELECT COUNT(*) FROM days WHERE exchanged_at IS NOT NULL")

    async def history_count(self) -> int:
        return await self._count("SELECT COUNT(*) FROM days WHERE theme_sent_at IS NOT NULL")

    async def history_page(self, offset: int, limit: int) -> list[tuple[Day, int]]:
        """Дни с темой, от новых к старым, и сколько фото прислали в каждый."""
        rows = await self._all(
            "SELECT d.*, (SELECT COUNT(*) FROM submissions s WHERE s.date = d.date) AS photos "
            "FROM days d WHERE d.theme_sent_at IS NOT NULL "
            "ORDER BY d.date DESC LIMIT ? OFFSET ?",
            limit,
            offset,
        )
        return [(_day(row), row["photos"]) for row in rows]

    # ── Темы ──

    async def log_theme(self, day: dt.date, title: str, at: dt.datetime) -> None:
        await self._run(
            "INSERT INTO theme_log (date, title, shown_at) VALUES (?, ?, ?)",
            day.isoformat(),
            title,
            _iso(at),
        )

    async def theme_history(self) -> list[str]:
        rows = await self._all("SELECT title FROM theme_log ORDER BY id")
        return [row["title"] for row in rows]

    async def used_themes(self) -> set[str]:
        """Темы, по которым прислали хотя бы одно фото: больше они не выпадают."""
        rows = await self._all(
            "SELECT DISTINCT d.theme_title FROM days d WHERE d.theme_title IS NOT NULL "
            "AND EXISTS (SELECT 1 FROM submissions s WHERE s.date = d.date)"
        )
        return {row["theme_title"] for row in rows}

    async def themes_shown_on(self, day: dt.date) -> int:
        return await self._count("SELECT COUNT(*) FROM theme_log WHERE date = ?", day.isoformat())

    # ── Фото ──

    async def get_submissions(self, day: dt.date) -> list[Submission]:
        rows = await self._all(
            "SELECT * FROM submissions WHERE date = ? ORDER BY sent_at", day.isoformat()
        )
        return [_submission(row) for row in rows]

    async def save_submission(self, photo: Submission) -> SaveResult:
        """Сохранить фото дня: первое за день — «new», другое фото вместо прежнего — «replaced».

        То же самое фото ещё раз — «same»: Telegram передоставил сообщение после рестарта.
        Остальные фото того же альбома — «ignored»: из альбома берём одно.
        """
        fields = (photo.file_id, photo.kind, photo.caption, photo.media_group_id, _iso(photo.sent_at))
        inserted = await self._run(
            "INSERT OR IGNORE INTO submissions "
            "(date, user_id, file_id, kind, caption, media_group_id, sent_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            photo.date.isoformat(),
            photo.user_id,
            *fields,
        )
        if inserted:
            return "new"
        stored = await self._one(
            "SELECT file_id FROM submissions WHERE date = ? AND user_id = ?",
            photo.date.isoformat(),
            photo.user_id,
        )
        if stored is not None and stored["file_id"] == photo.file_id:
            return "same"
        replaced = await self._run(
            "UPDATE submissions "
            "SET file_id = ?, kind = ?, caption = ?, media_group_id = ?, sent_at = ? "
            "WHERE date = ? AND user_id = ? AND (? IS NULL OR media_group_id IS NOT ?)",
            *fields,
            photo.date.isoformat(),
            photo.user_id,
            photo.media_group_id,
            photo.media_group_id,
        )
        return "replaced" if replaced else "ignored"

    # ── Доставка: кому реально ушли тема и альбом обмена ──

    async def delivered_to(self, day: dt.date, kind: str) -> set[int]:
        rows = await self._all(
            "SELECT user_id FROM deliveries WHERE date = ? AND kind = ?", day.isoformat(), kind
        )
        return {row["user_id"] for row in rows}

    async def mark_delivered(self, day: dt.date, user_id: int, kind: str, at: dt.datetime) -> None:
        await self._run(
            "INSERT OR IGNORE INTO deliveries (date, user_id, kind, delivered_at) VALUES (?, ?, ?, ?)",
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
            f"SELECT d.date FROM days d WHERE d.date >= ? AND d.{column} < ? {too_late} "
            "AND (SELECT COUNT(*) FROM deliveries x WHERE x.date = d.date AND x.kind = ?) "
            "< (SELECT COUNT(*) FROM users) ORDER BY d.date",
            since.isoformat(),
            _iso(happened_before),
            kind,
        )
        return [dt.date.fromisoformat(row["date"]) for row in rows]

    # ── Копилка тем друг для друга (/addtheme) ──

    async def add_custom_theme(self, author_id: int, theme: Theme, at: dt.datetime) -> int:
        async with self.conn.execute(
            "INSERT INTO custom_themes (author_id, title, hint, created_at) VALUES (?, ?, ?, ?)",
            (author_id, theme.title, theme.hint, _iso(at)),
        ) as cursor:
            return cursor.lastrowid or 0

    async def custom_pending_count(self, author_id: int) -> int:
        return await self._count(
            "SELECT COUNT(*) FROM custom_themes WHERE author_id = ? AND shown_on IS NULL", author_id
        )

    async def next_custom_theme(self) -> CustomTheme | None:
        """Самая старая тема из копилки — сначала от того, чья тема выпадала не последней."""
        row = await self._one(
            "SELECT id, author_id, title, hint FROM custom_themes WHERE shown_on IS NULL "
            "ORDER BY author_id = (SELECT author_id FROM custom_themes WHERE shown_on IS NOT NULL "
            "ORDER BY shown_on DESC, id DESC LIMIT 1), id LIMIT 1"
        )
        if row is None:
            return None
        return CustomTheme(row["id"], row["author_id"], row["title"], row["hint"])

    async def mark_custom_shown(self, theme_id: int, day: dt.date) -> None:
        await self._run("UPDATE custom_themes SET shown_on = ? WHERE id = ?", day.isoformat(), theme_id)

    async def return_custom_theme(self, day: dt.date, author_id: int, title: str) -> None:
        """Тему из копилки сменили кнопкой — она возвращается в очередь."""
        await self._run(
            "UPDATE custom_themes SET shown_on = NULL WHERE shown_on = ? AND author_id = ? AND title = ?",
            day.isoformat(),
            author_id,
            title,
        )

    async def delete_custom_theme(self, theme_id: int, author_id: int) -> bool:
        """Удалить свою тему из копилки, пока она не выпала."""
        deleted = await self._run(
            "DELETE FROM custom_themes WHERE id = ? AND author_id = ? AND shown_on IS NULL",
            theme_id,
            author_id,
        )
        return deleted == 1

    # ── Реакции ──

    async def get_reaction(self, day: dt.date, user_id: int) -> str | None:
        row = await self._one(
            "SELECT emoji FROM reactions WHERE date = ? AND user_id = ?", day.isoformat(), user_id
        )
        return row["emoji"] if row else None

    async def set_reaction(self, day: dt.date, user_id: int, emoji: str, at: dt.datetime) -> None:
        await self._run(
            "INSERT INTO reactions (date, user_id, emoji, at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT (date, user_id) DO UPDATE SET emoji = excluded.emoji, at = excluded.at",
            day.isoformat(),
            user_id,
            emoji,
            _iso(at),
        )

    # ── «Открыть раньше» ──

    async def add_early_vote(self, day: dt.date, user_id: int, at: dt.datetime) -> bool:
        """Отметить согласие открыть фото раньше. False — согласие уже было."""
        added = await self._run(
            "INSERT OR IGNORE INTO early_open (date, user_id, at) VALUES (?, ?, ?)",
            day.isoformat(),
            user_id,
            _iso(at),
        )
        return added == 1

    async def early_votes(self, day: dt.date) -> set[int]:
        rows = await self._all("SELECT user_id FROM early_open WHERE date = ?", day.isoformat())
        return {row["user_id"] for row in rows}

    # ── Отправленные фото: чьё фото в каком сообщении (для ответов) ──

    async def remember_message(self, chat_id: int, message_id: int, day: dt.date, owner_id: int) -> None:
        await self._run(
            "INSERT OR REPLACE INTO sent_messages (chat_id, message_id, date, owner_id) VALUES (?, ?, ?, ?)",
            chat_id,
            message_id,
            day.isoformat(),
            owner_id,
        )

    async def message_owner(self, chat_id: int, message_id: int) -> tuple[dt.date, int] | None:
        """День и автор фото, к которому относится сообщение, — или None, если это не фото дня."""
        row = await self._one(
            "SELECT date, owner_id FROM sent_messages WHERE chat_id = ? AND message_id = ?",
            chat_id,
            message_id,
        )
        return (dt.date.fromisoformat(row["date"]), row["owner_id"]) if row else None

    # ── Служебное (/dev) ──

    async def reset_day(self, day: dt.date) -> None:
        iso = day.isoformat()
        await self._run("UPDATE custom_themes SET shown_on = NULL WHERE shown_on = ?", iso)
        for table in ("submissions", "theme_log", "deliveries", "reactions", "sent_messages", "early_open", "days"):
            await self._run(f"DELETE FROM {table} WHERE date = ?", iso)

    async def clear_history(self) -> None:
        await self._run("UPDATE custom_themes SET shown_on = NULL")
        for table in ("submissions", "theme_log", "deliveries", "reactions", "sent_messages", "early_open", "days"):
            await self._run(f"DELETE FROM {table}")
