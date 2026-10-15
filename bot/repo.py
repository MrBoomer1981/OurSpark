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

SaveResult = Literal["new", "replaced", "ignored"]


@dataclass(frozen=True, slots=True)
class User:
    user_id: int
    name: str


@dataclass(frozen=True, slots=True)
class Day:
    date: dt.date
    theme_title: str | None
    theme_hint: str | None
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


def _iso(moment: dt.datetime) -> str:
    return moment.astimezone(dt.UTC).isoformat(timespec="seconds")


def _moment(value: str | None) -> dt.datetime | None:
    return dt.datetime.fromisoformat(value) if value else None


def _day(row: aiosqlite.Row) -> Day:
    return Day(
        date=dt.date.fromisoformat(row["date"]),
        theme_title=row["theme_title"],
        theme_hint=row["theme_hint"],
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

    async def claim_theme(self, day: dt.date, theme: Theme, at: dt.datetime) -> bool:
        changed = await self._run(
            "UPDATE days SET theme_title = ?, theme_hint = ?, theme_sent_at = ? "
            "WHERE date = ? AND theme_sent_at IS NULL AND skipped = 0",
            theme.title,
            theme.hint,
            _iso(at),
            day.isoformat(),
        )
        return changed == 1

    async def replace_theme(self, day: dt.date, old_title: str, theme: Theme) -> bool:
        """Сменить тему, только если её никто не успел сменить и фото за день ещё нет."""
        iso = day.isoformat()
        changed = await self._run(
            "UPDATE days SET theme_title = ?, theme_hint = ? "
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

    async def themes_shown_on(self, day: dt.date) -> int:
        return await self._count("SELECT COUNT(*) FROM theme_log WHERE date = ?", day.isoformat())

    # ── Фото ──

    async def get_submissions(self, day: dt.date) -> list[Submission]:
        rows = await self._all(
            "SELECT * FROM submissions WHERE date = ? ORDER BY sent_at", day.isoformat()
        )
        return [_submission(row) for row in rows]

    async def save_submission(self, photo: Submission) -> SaveResult:
        """Сохранить фото дня: первое за день — «new», повторное — «replaced».

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

    # ── Служебное (/dev) ──

    async def reset_day(self, day: dt.date) -> None:
        for table in ("submissions", "theme_log", "days"):
            await self._run(f"DELETE FROM {table} WHERE date = ?", day.isoformat())

    async def clear_history(self) -> None:
        for table in ("submissions", "theme_log", "days"):
            await self._run(f"DELETE FROM {table}")
