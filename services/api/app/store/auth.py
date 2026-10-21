"""SQL входа: сессии PWA и одноразовые nonce для входа через бота."""

import hashlib
import secrets
from typing import Literal

import asyncpg

# Сколько живёт nonce: за это время нужно и подтвердить вход в боте, и вернуться в PWA.
NONCE_TTL = "10 minutes"


def _hash(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


async def create_session(conn: asyncpg.Connection, user_id: int) -> str:
    """Новый токен сессии. В базе остаётся только его хеш."""
    token = secrets.token_urlsafe(32)
    await conn.execute("INSERT INTO sessions (token_hash, user_id) VALUES ($1, $2)", _hash(token), user_id)
    return token


async def session_user(conn: asyncpg.Connection, token: str) -> int | None:
    return await conn.fetchval(
        "UPDATE sessions SET last_seen_at = now() WHERE token_hash = $1 AND revoked_at IS NULL"
        " RETURNING user_id",
        _hash(token),
    )


async def create_nonce(conn: asyncpg.Connection) -> str:
    nonce = secrets.token_urlsafe(32)  # 43 символа: с «login_» влезает в лимит /start (64)
    await conn.execute("INSERT INTO login_nonces (nonce) VALUES ($1)", nonce)
    return nonce


async def confirm_nonce(conn: asyncpg.Connection, nonce: str, user_id: int) -> bool:
    """Бот подтвердил вход. Повторное подтверждение тем же человеком — тоже успех."""
    confirmed_by = await conn.fetchval(
        "UPDATE login_nonces SET confirmed_user_id = $2, confirmed_at = now()"
        f" WHERE nonce = $1 AND created_at > now() - interval '{NONCE_TTL}'"
        "  AND used_at IS NULL AND (confirmed_at IS NULL OR confirmed_user_id = $2)"
        " RETURNING confirmed_user_id",
        nonce,
        user_id,
    )
    return confirmed_by is not None


async def use_nonce(
    conn: asyncpg.Connection, nonce: str
) -> tuple[Literal["ok"], int] | tuple[Literal["pending", "expired"], None]:
    """Меняет подтверждённый nonce на человека — один раз."""
    user_id = await conn.fetchval(
        "UPDATE login_nonces SET used_at = now()"
        f" WHERE nonce = $1 AND created_at > now() - interval '{NONCE_TTL}'"
        "  AND confirmed_at IS NOT NULL AND used_at IS NULL"
        " RETURNING confirmed_user_id",
        nonce,
    )
    if user_id is not None:
        return "ok", user_id
    waiting = await conn.fetchval(
        "SELECT 1 FROM login_nonces"
        f" WHERE nonce = $1 AND created_at > now() - interval '{NONCE_TTL}' AND confirmed_at IS NULL",
        nonce,
    )
    return ("pending", None) if waiting else ("expired", None)
