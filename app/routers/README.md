# routers

FastAPI route modules. Each file defines an `APIRouter` and is included in `app/main.py`.

## Modules

- **health_routes.py** — `GET /health` (router tagged "health").
- **household.py** — Household routes: join, leave, create, convert-to-joinable (prefix `/households`).
- **pantry.py** — Pantry CRUD routes (prefix `/pantry`).

Export names in `__init__.py`: `health_router`, `household_router`, `pantry_router`.
