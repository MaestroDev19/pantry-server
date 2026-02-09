# Tests

Unit and integration tests for the Pantry server API.

## Layout

- **`unit/`** — Unit tests: core config, exceptions, models, and service logic with mocked I/O. No live HTTP or database.
- **`integration/`** — API tests using FastAPI `TestClient`: health, pantry, and household routes. Auth and Supabase can be mocked via `conftest.py`.

## Running tests

From the repository root (`server/`):

```bash
# All tests
pytest

# Unit only
pytest tests/unit

# Integration only
pytest tests/integration

# With coverage
pytest --cov=app
```

## Dependencies

Install dev dependencies first:

```bash
pip install -r requirements-dev.txt
# or
pip install -e ".[dev]"
```

## Fixtures

Shared fixtures in `conftest.py`:

- **`test_settings`** — Minimal settings (app_env, app_name) for the test app.
- **`app`** — FastAPI app created with `create_app(settings=test_settings)`.
- **`client`** — `TestClient(app)` for sync HTTP requests in integration tests.
