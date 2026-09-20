import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from app_paths import get_log_dir

_LOGGER_NAME = "EmployeeMS"


class _SensitiveFilter(logging.Filter):
    """Drop log records that accidentally contain password hashes or raw passwords."""

    _SENSITIVE_KEYS = ("password", "passwd", "secret", "token", "hash")

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage().lower()
        return not any(k in msg for k in self._SENSITIVE_KEYS)


def setup_logger() -> logging.Logger:
    """Configure and return the application logger."""
    logger = logging.getLogger(_LOGGER_NAME)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    # 1. Rotating File Handler
    try:
        log_file = os.path.join(get_log_dir(), "app.log")
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=2 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_fmt = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s (%(module)s:%(lineno)d): %(message)s"
        )
        file_handler.setFormatter(file_fmt)
        file_handler.setLevel(logging.INFO)
        file_handler.addFilter(_SensitiveFilter())
        logger.addHandler(file_handler)
    except Exception as exc:
        print("[logger] Warning: Could not setup file logger:", exc, file=sys.stderr)

    # 2. Console Handler (stdout/stderr)
    console_handler = logging.StreamHandler(sys.stderr)
    console_fmt = logging.Formatter("[%(levelname)s] %(message)s")
    console_handler.setFormatter(console_fmt)
    console_handler.setLevel(logging.WARNING)
    console_handler.addFilter(_SensitiveFilter())
    logger.addHandler(console_handler)

    return logger


logger = setup_logger()
