from __future__ import annotations

import logging
import sys

PRODUCTION_ENV_VALUES = frozenset({"prod", "production"})


def configure_logging(*, app_env: str) -> None:
    log_level = (
        logging.INFO if app_env.lower() in PRODUCTION_ENV_VALUES else logging.DEBUG
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )

    root_logger.handlers.clear()
    root_logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Return a logger for the given module name. Use for info, success, and error logs."""
    return logging.getLogger(name)


__all__ = ["configure_logging", "get_logger"]
