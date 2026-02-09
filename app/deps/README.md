# deps

FastAPI dependency providers for shared resources. Injected into routes and services.

## Modules

- **supabase.py** — `get_supabase_client()` (anon key), `get_supabase_service_role_client()` (service role).
- **gemini.py** — Gemini AI client (cached singleton) for chat and workflows.
