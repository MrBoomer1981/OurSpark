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
    # 2 — послание дня: ответы, раскрытие, искры, шкалы питомца, web push
    """
    CREATE TABLE pair_settings (
        pair_id bigint NOT NULL REFERENCES pairs (id),
        key     text NOT NULL,  -- timezone, debug_day_offset
        value   text NOT NULL,
        PRIMARY KEY (pair_id, key)
    );

    ALTER TABLE pets
        ADD COLUMN curiosity  integer NOT NULL DEFAULT 0,
        ADD COLUMN mischief   integer NOT NULL DEFAULT 0,
        ADD COLUMN tenderness integer NOT NULL DEFAULT 0,
        ADD COLUMN courage    integer NOT NULL DEFAULT 0;

    CREATE TABLE prompt_sessions (
        id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        pair_id      bigint NOT NULL REFERENCES pairs (id),
        day          date NOT NULL,  -- день назначения по часам пары
        prompt_key   text NOT NULL,  -- постоянный ключ карточки из content/prompts.yaml
        assigned_at  timestamptz NOT NULL DEFAULT now(),
        completed_at timestamptz,    -- результат открыт: искры и шкалы применены
        completed_on date,           -- день раскрытия по часам пары: следующее послание — не раньше завтра
        result       jsonb,          -- снимок раскрытия: что получила пара, его видят оба
        UNIQUE (pair_id, day)
    );

    CREATE TABLE answers (
        session_id     bigint NOT NULL REFERENCES prompt_sessions (id),
        user_id        bigint NOT NULL REFERENCES users (user_id),
        answer         text NOT NULL,  -- ключ выбранного варианта
        created_at     timestamptz NOT NULL DEFAULT now(),
        result_seen_at timestamptz,    -- человек открыл результат: раскрытие ему больше не проигрывается
        PRIMARY KEY (session_id, user_id)
    );

    CREATE TABLE reward_ledger (
        id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        pair_id    bigint NOT NULL REFERENCES pairs (id),
        user_id    bigint REFERENCES users (user_id),  -- кто заработал; NULL — вся пара
        event_key  text NOT NULL UNIQUE,  -- одно событие — одна запись: повтор не начислит второй раз
        sparks     integer NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now()
    );
    CREATE INDEX reward_ledger_by_pair ON reward_ledger (pair_id);

    CREATE TABLE push_subs (
        endpoint   text PRIMARY KEY,
        user_id    bigint NOT NULL REFERENCES users (user_id),
        keys       jsonb NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now(),
        failed_at  timestamptz  -- служба push ответила 404/410: подписка протухла
    );
    CREATE INDEX push_subs_by_user ON push_subs (user_id) WHERE failed_at IS NULL;
    """,
    # 3 — прогрессия: что открыла пара, летопись, надетая косметика
    """
    ALTER TABLE pets ADD COLUMN equipped jsonb NOT NULL DEFAULT '{}';  -- слот → ключ предмета

    CREATE TABLE unlocks (
        pair_id     bigint NOT NULL REFERENCES pairs (id),
        key         text NOT NULL,  -- stage:<ключ> · habit:<шкала>:<ключ> · item:<ключ> · relic:<тема>
        unlocked_at timestamptz NOT NULL DEFAULT now(),
        PRIMARY KEY (pair_id, key)
    );

    CREATE TABLE chronicle (
        id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        pair_id    bigint NOT NULL REFERENCES pairs (id),
        event_key  text NOT NULL,  -- одно событие — одна запись: повтор не допишет вторую
        kind       text NOT NULL,  -- hatch · choice · stage · habit · relic
        data       jsonb NOT NULL DEFAULT '{}',  -- ключи контента: текст записи собирается по ним при показе
        created_at timestamptz NOT NULL DEFAULT now(),
        UNIQUE (pair_id, event_key)
    );

    -- Уже собранным парам — первая страница летописи: питомец вылупился.
    INSERT INTO chronicle (pair_id, event_key, kind, created_at)
    SELECT pair_id, 'hatch', 'hatch', created_at FROM pets;
    """,
    # 4 — все типы посланий: свободный ответ, прогноз, журнал показов
    """
    ALTER TABLE answers
        ALTER COLUMN answer DROP NOT NULL,  -- ключ варианта; у ответа текстом — NULL
        ADD COLUMN text text,               -- свободный ответ (о близости)
        ADD COLUMN prediction text,         -- «Угадай партнёра»: ключ варианта, который выберет партнёр
        ADD CONSTRAINT answers_not_empty CHECK (answer IS NOT NULL OR text IS NOT NULL);

    CREATE TABLE prompt_log (
        id         bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        pair_id    bigint NOT NULL REFERENCES pairs (id),
        day        date NOT NULL,  -- день пары, когда карточку показали
        prompt_key text NOT NULL,
        changed    boolean NOT NULL DEFAULT false,  -- показана вместо сменённой («Другой вопрос»)
        created_at timestamptz NOT NULL DEFAULT now()
    );
    CREATE INDEX prompt_log_by_pair_day ON prompt_log (pair_id, day);

    -- Уже назначенные послания — в журнал показов.
    INSERT INTO prompt_log (pair_id, day, prompt_key, created_at)
    SELECT pair_id, day, prompt_key, assigned_at FROM prompt_sessions;
    """,
]
