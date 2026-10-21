"""SQL журнала наград. Баланс искр — сумма по журналу; у каждого события свой ключ."""

import asyncpg


async def grant(conn: asyncpg.Connection, pair_id: int, user_id: int | None, event_key: str, sparks: int) -> bool:
    """Записывает искры за событие (трата — с минусом). Второй раз за то же событие — ничего, и возвращает False."""
    inserted = await conn.fetchval(
        "INSERT INTO reward_ledger (pair_id, user_id, event_key, sparks) VALUES ($1, $2, $3, $4)"
        " ON CONFLICT (event_key) DO NOTHING RETURNING 1",
        pair_id,
        user_id,
        event_key,
        sparks,
    )
    return inserted is not None


async def balance(conn: asyncpg.Connection, pair_id: int) -> int:
    return await conn.fetchval("SELECT coalesce(sum(sparks), 0) FROM reward_ledger WHERE pair_id = $1", pair_id)


async def earned(conn: asyncpg.Connection, pair_id: int) -> int:
    """Заработано за всё время, без трат."""
    return await conn.fetchval(
        "SELECT coalesce(sum(sparks), 0) FROM reward_ledger WHERE pair_id = $1 AND sparks > 0", pair_id
    )


async def reset(conn: asyncpg.Connection, pair_id: int) -> None:
    """Только для отладки."""
    await conn.execute("DELETE FROM reward_ledger WHERE pair_id = $1", pair_id)
