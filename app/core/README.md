# core

Core application configuration and cross-cutting concerns. Used by all other modules.

## Modules

- **config.py** — `AppSettings` (Pydantic), `get_settings()`, env parsing helpers.
- **exceptions.py** — `AppError`, `app_error_handler`, `setup_exception_handlers`, `create_unhandled_exception_handler`.
- **logging.py** — `configure_logging()`, `get_logger()`.
