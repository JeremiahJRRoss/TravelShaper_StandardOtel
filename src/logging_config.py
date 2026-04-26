"""Structured logging configuration for TravelShaper.

Emits JSON log records to /app/logs/travelshaper.log (tailed by the Observe
Agent's filelog receiver) and a human-readable copy to stderr for local dev.
The file handler is best-effort: if /app/logs is not writable (e.g. running
outside Docker without the volume mount), file logging is silently skipped.
"""

import logging
import os
import sys

from pythonjsonlogger import jsonlogger

LOG_FILE_PATH = os.getenv("TRAVELSHAPER_LOG_FILE", "/app/logs/travelshaper.log")

_configured = False


def setup_logging() -> None:
    """Install JSON file + stderr handlers on the root logger.

    Idempotent — safe to call multiple times.
    """
    global _configured
    if _configured:
        return

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    json_formatter = jsonlogger.JsonFormatter(
        "%(asctime)s %(name)s %(levelname)s %(message)s",
        rename_fields={"asctime": "timestamp", "levelname": "severity"},
    )

    try:
        os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)
        file_handler = logging.FileHandler(LOG_FILE_PATH)
        file_handler.setFormatter(json_formatter)
        root.addHandler(file_handler)
    except (OSError, PermissionError):
        pass

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    ))
    root.addHandler(stderr_handler)

    _configured = True
