# Integration tests

API tests using FastAPI’s `TestClient`. Routes are exercised end-to-end; auth and Supabase are not wired to real backends in the default fixtures (missing auth yields 403).

## Contents

- **test_health.py** — `GET /health`, `GET /`.
- **test_pantry_api.py** — Pantry routes (auth-required; tests assert 403 without token).
- **test_households_api.py** — Household routes (auth-required; tests assert 403 without token).

To test with real or mocked auth, override `get_current_user_id` / `get_current_household_id` in the app dependency overrides in `conftest.py`.
