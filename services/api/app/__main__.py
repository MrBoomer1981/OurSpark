"""Точка входа на Railway: python -m app."""

import socket

import uvicorn
from loguru import logger

from app.main import app


def main() -> None:
    port: int = app.state.config.port
    # Один сокет на IPv6 и IPv4. uvicorn с host="::" слушал бы только IPv6 (asyncio ставит
    # IPV6_V6ONLY), а нужны оба: в старых окружениях Railway приватная сеть — только IPv6,
    # а локальные запросы идут на 127.0.0.1.
    sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
    sock.bind(("::", port))
    logger.info("api: порт {}", port)
    # Свои строки uvicorn пишет в stderr, и Railway показал бы их ошибками — оставляем только предупреждения.
    server = uvicorn.Server(uvicorn.Config(app, access_log=False, log_level="warning"))
    server.run(sockets=[sock])


if __name__ == "__main__":
    main()
