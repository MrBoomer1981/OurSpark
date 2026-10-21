"""Пары: создать, войти по приглашению, выйти.

Правила те же, что у фото-бота: ровно два участника, человек — максимум в одной паре,
выход распускает пару (данные остаются в базе, но недоступны).
Порядок блокировок везде один — сначала строка пары, потом строка человека, — иначе
встречные запросы могли бы заблокировать друг друга.
"""

import secrets
import string
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

import asyncpg

from app import notify
from app.game import pet
from app.store import pairs, users
from app.store.pairs import Pair
from app.store.users import User

PAIR_SIZE = 2
# Только буквы и цифры: «_» и «-» остаются свободными для других параметров ссылки ?startapp=.
INVITE_ALPHABET = string.ascii_letters + string.digits
INVITE_LENGTH = 10

PairErrorCode = Literal["in_pair", "new_pairs_closed", "invite_not_found", "pair_closed", "pair_full", "in_other_pair"]


class PairError(Exception):
    def __init__(self, code: PairErrorCode) -> None:
        super().__init__(code)
        self.code: PairErrorCode = code


@dataclass(frozen=True)
class PairState:
    pair: Pair
    partner: User | None
    pet_hatched_at: datetime | None


async def state(conn: asyncpg.Connection, user: User) -> PairState | None:
    if user.pair_id is None:
        return None
    pair = await pairs.get(conn, user.pair_id)
    if pair is None:
        return None
    partner = next((m for m in await users.members(conn, pair.id) if m.id != user.id), None)
    return PairState(pair, partner, await pet.hatched_at(conn, pair.id))


async def create(conn: asyncpg.Connection, user_id: int, *, new_pairs: bool) -> None:
    async with conn.transaction():
        user = await users.get(conn, user_id, lock=True)
        if user is None:
            raise LookupError(user_id)
        if user.pair_id is not None:
            raise PairError("in_pair")
        if not new_pairs:
            raise PairError("new_pairs_closed")
        code = "".join(secrets.choice(INVITE_ALPHABET) for _ in range(INVITE_LENGTH))
        pair = await pairs.create(conn, code)
        await users.set_pair(conn, user_id, pair.id)


async def join(conn: asyncpg.Connection, user_id: int, invite_code: str) -> None:
    async with conn.transaction():
        # Блокировка строки пары: два человека одновременно не войдут в неё третьим.
        pair = await pairs.by_code(conn, invite_code, lock=True)
        if pair is None:
            raise PairError("invite_not_found")
        user = await users.get(conn, user_id, lock=True)
        if user is None:
            raise LookupError(user_id)
        if user.pair_id == pair.id:
            return  # своя пара: ссылку открыли ещё раз
        if pair.closed_at is not None:
            raise PairError("pair_closed")
        if user.pair_id is not None:
            raise PairError("in_other_pair")
        members = await users.members(conn, pair.id)
        if len(members) >= PAIR_SIZE:
            raise PairError("pair_full")
        await users.set_pair(conn, user_id, pair.id)
        if len(members) + 1 < PAIR_SIZE:
            return
        await pairs.mark_complete(conn, pair.id)
        await pet.hatch(conn, pair.id)
        for member in members:
            await notify.enqueue(
                conn,
                member.id,
                notify.PARTNER_JOINED,
                {"name": user.name},
                key=f"partner_joined:{pair.id}:{member.id}",
            )


async def leave(conn: asyncpg.Connection, user_id: int) -> None:
    """Распускает пару человека. Не в паре — ничего не происходит."""
    async with conn.transaction():
        user = await users.get(conn, user_id)
        if user is None or user.pair_id is None:
            return
        pair = await pairs.get(conn, user.pair_id, lock=True)
        user = await users.get(conn, user_id, lock=True)
        if pair is None or user is None or user.pair_id != pair.id:
            return  # пока ждали блокировку, пару уже распустили
        await pairs.close(conn, pair.id)
        await users.release_pair(conn, pair.id)
