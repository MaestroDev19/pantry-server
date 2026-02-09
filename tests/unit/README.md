# Unit tests

Tests that do not call the full HTTP stack or real external services. Use mocks (e.g. in `conftest.py`) for any I/O.

## Contents

- **test_core_config.py** — Config helpers: `str_to_bool`, `parse_int_or_none`, `parse_cors_origins`.
- **test_core_exceptions.py** — `AppError` and `app_error_handler` behavior.

Add further unit tests here for models (validation), services (with mocked Supabase/anyio), and utils.
