"""Подключение к SQLite и миграции схемы.

Схема меняется только добавлением новой миграции в КОНЕЦ списка MIGRATIONS.
Уже применённые миграции не редактируются: номер последней применённой хранится
в PRAGMA user_version, и при старте бот докатывает недостающие.
"""

from pathlib import Path

import aiosqlite
from loguru import logger

MIGRATIONS: list[str] = [
    # 1 — первая версия: участники, настройки, дни, показанные темы, фото.
    """
    CREATE TABLE users (
        user_id   INTEGER PRIMARY KEY,
        name      TEXT NOT NULL,
        joined_at TEXT NOT NULL
    );

    CREATE TABLE settings (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );

    CREATE TABLE days (
        date             TEXT PRIMARY KEY,
        theme_title      TEXT,
        theme_hint       TEXT,
        theme_sent_at    TEXT,
        reminder_sent_at TEXT,
        revealed_at      TEXT,
        exchanged_at     TEXT,
        skipped          INTEGER NOT NULL DEFAULT 0
    );

    CREATE TABLE theme_log (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        date     TEXT NOT NULL,
        title    TEXT NOT NULL,
        shown_at TEXT NOT NULL
    );

    CREATE TABLE submissions (
        date           TEXT NOT NULL,
        user_id        INTEGER NOT NULL,
        file_id        TEXT NOT NULL,
        kind           TEXT NOT NULL,
        caption        TEXT,
        media_group_id TEXT,
        sent_at        TEXT NOT NULL,
        PRIMARY KEY (date, user_id)
    );
    """,
]


async def connect(path: Path) -> aiosqlite.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Автокоммит: каждый запрос атомарен сам по себе. На этом держатся брони событий
    # вида UPDATE … WHERE … IS NULL (см. repo.py).
    conn = await aiosqlite.connect(path, isolation_level=None)
    conn.row_factory = aiosqlite.Row
    await conn.executescript("PRAGMA journal_mode = WAL; PRAGMA busy_timeout = 5000;")
    await migrate(conn)
    return conn


async def migrate(conn: aiosqlite.Connection) -> None:
    async with conn.execute("PRAGMA user_version") as cursor:
        row = await cursor.fetchone()
    current = row[0] if row else 0
    for version, script in enumerate(MIGRATIONS[current:], start=current + 1):
        await conn.executescript(f"BEGIN;\n{script}\nPRAGMA user_version = {version};\nCOMMIT;")
        logger.info("База: применена миграция {}", version)
