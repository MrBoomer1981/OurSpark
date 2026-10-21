"""Web push: уведомление во все рабочие подписки человека (VAPID).

Протухшая подписка (служба push ответила 404 или 410) выключается. Временная ошибка, если ни одна
подписка не сработала, — исключение: relay повторит отправку позже.
"""

import json
from typing import Any

import asyncpg
from loguru import logger
from pywebpush import WebPushException, webpush_async

from app.config import Config
from app.store import push

TTL_SECONDS = 24 * 3600  # служба push хранит недоставленное сутки


class Push:
    def __init__(self, config: Config) -> None:
        self._private_key = config.vapid_private_key.get_secret_value() if config.vapid_private_key else None
        self._subject = config.vapid_subject
        self.public_key = config.vapid_public_key
        self.enabled = bool(self._private_key and self._subject and self.public_key)

    async def send(self, conn: asyncpg.Connection, user_id: int, payload: dict[str, Any]) -> bool:
        """True — ушло хотя бы в одну подписку; False — рабочих подписок нет."""
        if not self.enabled:
            return False
        delivered = False
        transient: WebPushException | None = None
        for subscription in await push.active(conn, user_id):
            try:
                await webpush_async(
                    subscription_info={"endpoint": subscription.endpoint, "keys": subscription.keys},
                    data=json.dumps(payload, ensure_ascii=False),
                    vapid_private_key=self._private_key,
                    vapid_claims={"sub": self._subject},  # pywebpush дописывает в словарь aud и exp
                    ttl=TTL_SECONDS,
                    timeout=10,
                )
                delivered = True
            except WebPushException as error:
                if _status(error) in (404, 410):
                    await push.mark_failed(conn, subscription.endpoint)
                else:
                    transient = error
            except (ValueError, TypeError) as error:  # битые ключи подписки: повтор не поможет
                logger.warning("Push: подписка {} выключена: {!r}", subscription.endpoint[:60], error)
                await push.mark_failed(conn, subscription.endpoint)
        if not delivered and transient is not None:
            raise transient
        return delivered


def _status(error: WebPushException) -> int | None:
    response = error.response
    return getattr(response, "status", None) or getattr(response, "status_code", None)
