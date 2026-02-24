from __future__ import annotations

import logging

from app.core.logging import PRODUCTION_ENV_VALUES, configure_logging


def test_configure_logging_uses_debug_level_for_non_production() -> None:
    configure_logging(app_env="development")
    root_logger = logging.getLogger()
    assert root_logger.level == logging.DEBUG


def test_configure_logging_uses_info_level_for_production() -> None:
    for env in PRODUCTION_ENV_VALUES:
        configure_logging(app_env=env)
        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO

