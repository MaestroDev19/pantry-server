from __future__ import annotations

import logging
import sys


def configure_logging(*, app_env: str) -> None:
    log_level = logging.INFO if app_env.lower() in {"prod", "production"} else logging.DEBUG

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


__all__ = ["configure_logging"]
