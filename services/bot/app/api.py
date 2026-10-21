"""Запросы к api по приватной сети. Пока один — подтверждение входа в PWA."""

from typing import Literal

import aiohttp


class Api:
    def __init__(self, base_url: str, secret: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._secret = secret
        self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))

    async def confirm_login(self, nonce: str, user_id: int, name: str) -> Literal["ok", "expired"]:
        async with self._session.post(
            f"{self._base_url}/api/internal/login/confirm",
            json={"nonce": nonce, "user_id": user_id, "name": name},
            headers={"X-Internal-Secret": self._secret},
        ) as response:
            response.raise_for_status()
            return (await response.json())["result"]

    async def close(self) -> None:
        await self._session.close()
