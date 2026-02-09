# app

Main application package. Entry point is `main.py`, which defines the FastAPI app factory `create_app()` and the default `app` instance.

## Subpackages

- **core/** — Configuration, exception handlers, logging.
- **models/** — Pydantic request/response and domain models.
- **routers/** — API route modules; each exposes a `router` included in `main.py`.
- **services/** — Business logic and external I/O (Supabase, embeddings).
- **deps/** — FastAPI dependency providers (Supabase client, Gemini, etc.).
- **utils/** — Pure helpers (dates, validators, formatters, constants).
- **ai/** — AI and vector store integration.

Run the app with `uvicorn app.main:app` or `fastapi dev app/main.py`.
