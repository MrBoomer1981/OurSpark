"""Схема базы: миграции по порядку, номер миграции — её место в списке (с единицы).

Схема меняется только новой миграцией в конце списка. Применённые миграции не правятся:
в проде они уже выполнены, и правка туда не дойдёт.
"""

MIGRATIONS: list[str] = [
    # 1 — каркас: люди, пары, вход, питомец, outbox
    """
    CREATE TABLE pairs (
        id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        invite_code  text NOT NULL UNIQUE,
        created_at   timestamptz NOT NULL DEFAULT now(),
        completed_at timestamptz,  -- пара собрана: вошёл второй
        closed_at    timestamptz   -- пара распущена: данные остаются, но недоступны
    );

    CREATE TABLE users (
        user_id      bigint PRIMARY KEY,  -- id в Telegram; отрицательные — подставные (только DEBUG)
        name         text NOT NULL,
        pair_id      bigint REFERENCES pairs (id),
        created_at   timestamptz NOT NULL DEFAULT now(),
        tg_reachable boolean  -- NULL — ещё не писали; false — Telegram отказал (бот заблокирован)
    );
    CREATE INDEX users_by_pair ON users (pair_id);

    CREATE TABLE sessions (
        token_hash   bytea PRIMARY KEY,  -- sha256 токена; сам токен есть только у PWA
        user_id      bigint NOT NULL REFERENCES users (user_id),
        created_at   timestamptz NOT NULL DEFAULT now(),
        last_seen_at timestamptz NOT NULL DEFAULT now(),
        revoked_at   timestamptz
    );

    CREATE TABLE login_nonces (
        nonce             text PRIMARY KEY,
        created_at        timestamptz NOT NULL DEFAULT now(),
        confirmed_user_id bigint REFERENCES users (user_id),
        confirmed_at      timestamptz,
        used_at           timestamptz
    );

    CREATE TABLE pets (
        pair_id    bigint PRIMARY KEY REFERENCES pairs (id),
        created_at timestamptz NOT NULL DEFAULT now()
    );

    CREATE TABLE outbox (
        id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        user_id    bigint NOT NULL REFERENCES users (user_id),
        kind       text NOT NULL,
        payload    jsonb NOT NULL DEFAULT '{}',
        dedup_key  text NOT NULL UNIQUE,
        created_at timestamptz NOT NULL DEFAULT now(),
        due_at     timestamptz NOT NULL DEFAULT now(),  -- не раньше этого времени: так ждут повторы
        claimed_at timestamptz,
        sent_at    timestamptz,
        failed_at  timestamptz,
        attempts   integer NOT NULL DEFAULT 0,
        error      text
    );
    CREATE INDEX outbox_due ON outbox (due_at) WHERE sent_at IS NULL AND failed_at IS NULL;
    """,
]
