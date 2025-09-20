import logging
import os
from typing import Optional


DEFAULT_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
DEFAULT_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


class ContextFilter(logging.Filter):
    """Injects default context fields if missing to avoid KeyError in formatters."""

    def filter(self, record: logging.LogRecord) -> bool:  # type: ignore[override]
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        if not hasattr(record, "room"):
            record.room = "-"
        if not hasattr(record, "role"):
            record.role = "-"
        return True


def setup_logging(level: Optional[str] = None, fmt: Optional[str] = None) -> None:
    """Initialize root logger with a sane formatter and context filter."""
    resolved_level = getattr(logging, (level or DEFAULT_LEVEL), logging.INFO)
    formatter = logging.Formatter(fmt or DEFAULT_FORMAT)

    root = logging.getLogger()
    root.setLevel(resolved_level)

    # Clear existing handlers to avoid duplicate logs in reloads
    for h in list(root.handlers):
        root.removeHandler(h)

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    handler.addFilter(ContextFilter())
    root.addHandler(handler)
    root.addFilter(ContextFilter())


def get_logger(name: str) -> logging.Logger:
    """Get a module logger; ensure root is initialized."""
    if not logging.getLogger().handlers:
        setup_logging()
    return logging.getLogger(name)
