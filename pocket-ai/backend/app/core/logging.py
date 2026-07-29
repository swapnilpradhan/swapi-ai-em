"""Structured logging.

Transcript content, speaker names, and meeting titles are never logged at INFO or
above — titles routinely contain names and topics. Meeting ids are content hashes and
are safe. See docs/SECURITY_PRIVACY.md.
"""

from __future__ import annotations

import logging
import sys

import structlog

from .config import get_settings

# Field names that must never appear in a log event at INFO or above.
_SENSITIVE_KEYS = frozenset(
    {"transcript", "text", "quote", "title", "display_name", "audio_path", "prompt"}
)


def _redact_sensitive(_logger, method_name, event_dict):
    if method_name in ("debug",) and get_settings().is_development:
        return event_dict
    for key in _SENSITIVE_KEYS & event_dict.keys():
        event_dict[key] = "<redacted>"
    return event_dict


def configure_logging() -> None:
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            _redact_sensitive,
            structlog.dev.ConsoleRenderer()
            if settings.is_development
            else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
