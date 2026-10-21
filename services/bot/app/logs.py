"""Логи: обычные строки — в stdout, предупреждения и ошибки — в stderr.

Railway считает всё, что пришло в stderr, ошибкой, поэтому делим поток по уровню.
"""

import sys

from loguru import logger

WARNING = logger.level("WARNING").no


def setup(debug: bool) -> None:
    logger.remove()
    # Значения переменных в трейсбэках (diagnose) — только в DEBUG: там бывают имена и тексты сообщений.
    options = {"backtrace": debug, "diagnose": debug}
    logger.add(
        sys.stdout,
        level="DEBUG" if debug else "INFO",
        filter=lambda record: record["level"].no < WARNING,
        **options,
    )
    logger.add(sys.stderr, level="WARNING", **options)
