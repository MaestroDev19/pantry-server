# pantry-server

FastAPI backend for the Pantry app. Provides REST API, Supabase integration, and optional AI (LangChain/Google Gemini) features.

## Tech stack

- **Framework:** FastAPI
- **Config & validation:** Pydantic, pydantic-settings
- **Database / auth:** Supabase
- **Security:** python-jose (JWT), passlib (bcrypt)
- **AI:** LangChain, LangGraph, langchain-google-genai
- **Other:** httpx, slowapi (rate limiting), psutil

## Prerequisites

- Python 3.11+
- `.env` with required variables (see [Environment](#environment))

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
```

Copy `.env.example` to `.env` (or create `.env`) and set values as needed.

## Run

**Development (reload on file change):**

```bash
uvicorn app.main:app --reload
```

**Production-style (no reload):**

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- **API base:** `http://127.0.0.1:8000`
- **Interactive docs (Swagger):** `http://127.0.0.1:8000/docs`
- **ReDoc:** `http://127.0.0.1:8000/redoc`

## Project structure

```
app/
├── main.py              # FastAPI app factory, lifespan, middleware, exception handlers
├── core/
│   ├── config.py        # AppSettings (env), get_settings
│   ├── errors.py        # Unhandled exception handler
│   ├── exceptions.py    # AppError subclasses, app_error_handler
│   ├── logging.py       # configure_logging
│   └── security.py      # Password hashing, JWT create/decode
├── models/              # Pydantic schemas / domain models
├── routers/             # Route modules (e.g. health_routes)
├── services/            # Business logic (e.g. gemini, supabase)
└── utils/               # Helpers (e.g. embedding)
```

- **Routers:** Define routes and response models; use `app.routers` and named exports.
- **Services:** Pure or async functions; keep I/O and external calls here.
- **Core:** Config, logging, security, and global exception handling.

## Environment

| Variable                       | Description                                            | Default       |
| ------------------------------ | ------------------------------------------------------ | ------------- |
| `ENVIRONMENT`                  | Runtime environment (e.g. `development`, `production`) | `development` |
| `PORT`                         | Server port                                            | `8000`        |
| `SUPABASE_URL`                 | Supabase project URL                                   | —             |
| `SUPABASE_ANON_KEY`            | Supabase anon/public key                               | —             |
| `GOOGLE_GENERATIVE_AI_API_KEY` | Google AI API key (for Gemini/LangChain)               | —             |

Optional (e.g. for JWT): `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_ACCESS_EXPIRE_MINUTES`.

## API overview

- `GET /` — Simple status (excluded from OpenAPI).
- `GET /health` — Health check; returns `{"status": "ok"}`.

Add new routes under `app/routers/` and include them in `app/main.py` with `app.include_router(...)`.
