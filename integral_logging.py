"""Rotating file logging for Integral (issue #173)."""

from __future__ import annotations

import logging
import traceback
from logging.handlers import RotatingFileHandler

from paths import app_log_file

_LOGGER: logging.Logger | None = None


def reset_logger_cache() -> None:
    """Clear cached logger (tests patch app_log_file before first write)."""
    global _LOGGER
    logger = logging.getLogger("integral")
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        try:
            handler.close()
        except OSError:
            pass
    _LOGGER = None


def get_logger() -> logging.Logger:
    global _LOGGER
    if _LOGGER is not None:
        return _LOGGER
    path = app_log_file()
    logger = logging.getLogger("integral")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = RotatingFileHandler(
            path,
            maxBytes=512_000,
            backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        )
        logger.addHandler(handler)
    _LOGGER = logger
    return logger


def log_exception(error: BaseException, *, context: str = "") -> tuple[str, str]:
    """Write traceback to integral.log; return (log_path, traceback_text)."""
    tb_text = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    prefix = f"[{context}] " if context else ""
    get_logger().error("%s%s: %s\n%s", prefix, type(error).__name__, error, tb_text)
    return app_log_file(), tb_text
