"""Подключение к SQLite и миграции схемы.

Схема меняется только добавлением новой миграции в КОНЕЦ списка MIGRATIONS.
Уже применённые миграции не редактируются: номер последней применённой хранится
в PRAGMA user_version, и при старте бот докатывает недостающие.
"""

import os
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
    # 2 — кому реально ушли тема и альбом обмена: недошедшее бот досылает после рестарта.
    # Уже состоявшиеся события помечаем доставленными, чтобы не разослать их заново.
    """
    CREATE TABLE deliveries (
        date         TEXT NOT NULL,
        user_id      INTEGER NOT NULL,
        kind         TEXT NOT NULL,
        delivered_at TEXT NOT NULL,
        PRIMARY KEY (date, user_id, kind)
    );

    INSERT INTO deliveries (date, user_id, kind, delivered_at)
    SELECT d.date, u.user_id, 'theme', d.theme_sent_at FROM days d, users u
    WHERE d.theme_sent_at IS NOT NULL;

    INSERT INTO deliveries (date, user_id, kind, delivered_at)
    SELECT d.date, u.user_id, 'exchange', d.exchanged_at FROM days d, users u
    WHERE d.exchanged_at IS NOT NULL;
    """,
    # 3 — темы друг для друга (/addtheme), реакции, привязка отправленных фото к сообщениям
    # (для ответов) и вечерняя карточка. Прошедшим обменам карточку не досылаем.
    """
    ALTER TABLE days ADD COLUMN theme_author INTEGER;

    CREATE TABLE custom_themes (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        author_id  INTEGER NOT NULL,
        title      TEXT NOT NULL,
        hint       TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        shown_on   TEXT
    );

    CREATE TABLE reactions (
        date    TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        emoji   TEXT NOT NULL,
        at      TEXT NOT NULL,
        PRIMARY KEY (date, user_id)
    );

    CREATE TABLE sent_messages (
        chat_id    INTEGER NOT NULL,
        message_id INTEGER NOT NULL,
        date       TEXT NOT NULL,
        owner_id   INTEGER NOT NULL,
        PRIMARY KEY (chat_id, message_id)
    );

    INSERT INTO deliveries (date, user_id, kind, delivered_at)
    SELECT d.date, u.user_id, 'card', d.exchanged_at FROM days d, users u
    WHERE d.exchanged_at IS NOT NULL;
    """,
]


def require_volume(path: Path) -> None:
    """На Railway база обязана лежать на Volume: иначе каждый деплой стирает фото и историю."""
    if "RAILWAY_ENVIRONMENT_ID" not in os.environ:
        return  # не Railway — локальный запуск
    mount = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH")
    if mount and path.resolve().is_relative_to(Path(mount).resolve()):
        return
    raise SystemExit(
        f"База {path.resolve()} лежит не на Volume, и каждый деплой будет её стирать. "
        "Подключи к сервису Volume с путём /app/data (или поправь DB_PATH) и задеплой заново."
    )


async def connect(path: Path) -> aiosqlite.Connection:
    require_volume(path)
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
