# services

Business logic and external integrations. Routers depend on services; services use `app.deps`, `app.models`, and `app.utils`.

## Modules

- **auth.py** — Auth dependencies: `get_current_user`, `get_current_user_id`, `get_current_household_id`.
- **household_service.py** — Household operations: create, join by invite, leave, convert personal to joinable.
- **pantry_service.py** — Pantry item CRUD and bulk operations, embeddings integration.
