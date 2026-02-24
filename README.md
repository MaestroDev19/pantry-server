# Pantry Server

FastAPI + Supabase backend for the Pantry application, providing authenticated, household-scoped pantry item management with AI-powered features (embeddings and Gemini-based workflows).

## Table of Contents

- [Overview](#overview)
- [Current Status](#current-status)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Setup](#setup)
- [Running the Server](#running-the-server)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Documentation](#documentation)
- [Architecture](#architecture)
- [Environment Variables](#environment-variables)
- [API Documentation](#api-documentation)
- [Development Guidelines](#development-guidelines)

## Overview

Pantry Server is a modern, scalable backend API built with FastAPI that enables users to:

- **Manage Pantry Items**: Track food inventory with categories, quantities, units, and expiry dates
- **Recipe Management**: Create, search, and generate recipes using AI
- **Shopping Lists**: Generate and manage shopping lists based on pantry needs
- **Household Collaboration**: Share pantries and shopping lists with household members
- **User Preferences**: Configure alerts and reminders for pantry management

## Current Status

### ✅ Implemented

#### Core Infrastructure

- ✅ FastAPI application with lifespan management
- ✅ Configuration management with Pydantic Settings
- ✅ Structured logging system
- ✅ Global exception handling
- ✅ Health check endpoint (`GET /health`)

#### Authentication & Security

- ✅ Supabase authentication integration
- ✅ Bearer token validation
- ✅ User authentication and household dependencies (`get_current_user`, `get_current_user_id`, `get_current_household_id`)
- ✅ Row Level Security (RLS) support via anon key client

#### Pantry API

- ✅ Household-scoped pantry item CRUD via `/pantry` routes
- ✅ Single and bulk pantry item upsert with validation
- ✅ User-scoped and household-scoped pantry item listing
- ✅ Embedding generation and storage for pantry items

#### Household API

- ✅ Join household by invite code (`POST /households/join`) — migrates user's pantry items and switches membership
- ✅ Leave household (`POST /households/leave`) — creates a new personal household and moves items
- ✅ Convert personal to joinable (`POST /households/convert-to-joinable`) — make a personal household shareable

#### Data Models

- ✅ **Pantry Models**: Complete schema for pantry items with categories, units, expiry tracking
- ✅ **Recipe Models**: Full recipe structure with ingredients, instructions, dietary tags
- ✅ **Shopping List Models**: Shopping list items with purchase tracking
- ✅ **Household Models**: Household management and member models
- ✅ **User Models**: User preferences for alerts and reminders

#### Services

- ✅ Supabase client service (anon and service role) in `app/deps/`
- ✅ Gemini AI client with LRU caching in `app/deps/`
- ✅ Embeddings client for vector operations in `app/utils/`
- ✅ Supabase-backed vector store, retriever cache, and LangChain tools for pantry RAG flows in `app/ai/`
- ✅ Unit and integration test layout in `tests/` (unit + integration, pytest)

#### Utilities

- ✅ Authentication utilities
- ✅ Input validators and normalizers
- ✅ Response formatters
- ✅ Application constants

### 🚧 In Progress / Planned

- ⏳ **Additional Domain API Routes**: Recipes, shopping lists, and user preferences
- ⏳ **Recipe Generation**: AI-powered recipe generation from pantry items
- ⏳ **Shopping List Generation**: Automatic list creation based on pantry state
- ⏳ **Background Workers**: Embedding generation and batch processing
- ⏳ **CORS Configuration**: Cross-origin resource sharing setup

## Tech Stack

### Core Framework

- **FastAPI** - Modern, fast web framework for building APIs
- **Uvicorn** - ASGI server for production deployment
- **Pydantic** - Data validation using Python type annotations
- **pydantic-settings** - Settings management from environment variables

### Database & Authentication

- **Supabase** - PostgreSQL database with built-in authentication
- **python-jose** - JWT token handling
- **passlib** - Password hashing utilities

### AI & Machine Learning

- **LangChain** - Framework for building LLM applications
- **LangGraph** - State management for complex AI workflows
- **langchain-google-genai** - Google Gemini integration
- **Google Generative AI** - Gemini models for text and embeddings

### Utilities

- **httpx** - Async HTTP client
- **slowapi** - Rate limiting middleware
- **psutil** - System monitoring
- **python-multipart** - Form data handling
- **python-dateutil** - Date parsing utilities

## Prerequisites

- **Python 3.11+** (tested with Python 3.11+)
- **Supabase Account** - For database and authentication
- **Google Cloud Account** - For Gemini API access (optional, for AI features)
- **`.env` file** - Environment variables (see [Environment Variables](#environment-variables))

## Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
cd pantry/server
```

### 2. Create Virtual Environment

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS/Linux
python -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```bash
# Copy example (if available)
cp .env.example .env

# Or create manually
touch .env
```

See [Environment Variables](#environment-variables) for required configuration.

### 5. Verify Installation

```bash
# Check Python version
python --version  # Should be 3.11+

# Verify FastAPI installation
python -c "import fastapi; print(fastapi.__version__)"
```

## Running the Server

### Development Mode

Runs with auto-reload on file changes:

```bash
uvicorn app.main:app --reload
```

### Production Mode

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Using FastAPI CLI

```bash
fastapi dev app/main.py
```

### Access Points

- **API Base URL**: `http://127.0.0.1:8000`
- **Interactive API Docs (Swagger)**: `http://127.0.0.1:8000/docs`
- **Alternative API Docs (ReDoc)**: `http://127.0.0.1:8000/redoc`
- **OpenAPI JSON**: `http://127.0.0.1:8000/openapi.json`

## Project Structure

```
app/
├── __init__.py
├── main.py                    # FastAPI app factory, lifespan, middleware
│
├── core/                      # Core application configuration
│   ├── config.py             # AppSettings, environment configuration
│   ├── exceptions.py         # Exception handlers and custom errors
│   └── logging.py            # Logging configuration
│
├── models/                    # Pydantic schemas and domain models
│   ├── household.py          # Household and member models
│   ├── pantry.py             # Pantry item models and enums
│   ├── recipe.py             # Recipe models and AI request/response
│   ├── shopping_list.py      # Shopping list models
│   └── user.py               # User preferences models
│
├── routers/                   # API route definitions
│   ├── health_routes.py      # Health check endpoint
│   ├── household.py          # Household routes (join, leave, convert-to-joinable)
│   └── pantry.py             # Pantry item routes (household/user scoped)
│
├── services/                  # Business logic and external integrations
│   ├── auth.py               # Authentication and household resolution dependencies
│   ├── household_service.py   # Household service (join, leave, convert, create)
│   └── pantry_service.py     # Pantry domain service and embeddings integration
│
├── deps/                      # Dependency providers (FastAPI DI)
│   ├── supabase.py           # Supabase client dependencies (anon / service role)
│   └── gemini.py             # Gemini AI client (cached singleton)
│
├── utils/                     # Utility functions and helpers
│   ├── constants.py          # Application constants
│   ├── date_time_styling.py  # Date/datetime formatting
│   ├── embedding.py          # Embeddings client (cached singleton)
│   ├── formatters.py         # Response formatting utilities
│   └── validators.py         # Input validation helpers
│
└── ai/                        # AI and vector store + RAG integration
    ├── vector_store.py        # SupabaseVectorStore wrapper for pantry embeddings
    ├── retriever_cache.py     # In-memory retrieval cache keyed by household + query
    ├── retriver.py            # LangChain tool for retrieving pantry items from the vector store
    └── prompts.py             # Structured prompts for recipe generation from pantry + preferences

tests/                         # Unit and integration tests
├── conftest.py                # Shared fixtures (app, client, test_settings)
├── unit/                      # Unit tests (no HTTP, mocked I/O)
└── integration/               # API tests (TestClient)
```

Each major folder under `app/` and `tests/` has a README describing its role and contents (see [Documentation](#documentation)).

## Testing

Tests live in `tests/`: **unit** (no HTTP, mocked I/O) and **integration** (API tests with `TestClient`).

### Install dev dependencies

```bash
pip install -r requirements-dev.txt
# or
pip install -e ".[dev]"
```

### Run tests

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

See `tests/README.md` for fixtures and layout details.

## Documentation

Each major folder has a short README:

- **app/README.md** — Package overview and subpackages
- **app/core/**, **app/models/**, **app/routers/**, **app/services/**, **app/deps/**, **app/utils/**, **app/ai/** — Purpose and module list
- **tests/README.md** — How to run unit vs integration tests and use fixtures
- **tests/unit/README.md**, **tests/integration/README.md** — What each test directory contains

## Architecture

### Design Principles

- **Functional Programming**: Prefer pure functions over classes where possible
- **Dependency Injection**: Use FastAPI's dependency system for shared resources
- **Separation of Concerns**: Clear boundaries between routes, services, and utilities
- **Type Safety**: Comprehensive type hints throughout the codebase
- **Error Handling**: Early returns, guard clauses, and consistent error responses

### Key Patterns

#### Singleton Services

Client instances (Gemini, Embeddings, Supabase) use `@lru_cache` for singleton behavior:

```python
@lru_cache(maxsize=1)
def get_gemini_client() -> ChatGoogleGenerativeAI:
    """Cached singleton client instance"""
    return ChatGoogleGenerativeAI(...)
```

#### Model Hierarchy

Pydantic models follow a consistent pattern:

- `*Base` - Base model with common fields
- `*Create` - For creation requests
- `*Update` - For partial updates (all fields optional)
- `*Response` - For API responses

#### Dependency Injection

FastAPI dependencies for:

- Authentication and households: `get_current_user()`, `get_current_user_id()`, `get_current_household_id()`
- Database clients: `get_supabase_client()`, `get_supabase_service_role_client()` (service role used for household join/leave/convert to bypass RLS)
- AI clients: `get_gemini_client()`, `embeddings_client()`

## Environment Variables

### Required Variables

| Variable                    | Description                                      | Example                                   |
| --------------------------- | ------------------------------------------------ | ----------------------------------------- |
| `SUPABASE_URL`              | Supabase project URL                             | `https://xxxxx.supabase.co`               |
| `SUPABASE_ANON_KEY`         | Supabase anonymous/public key                    | `eyJ********************************9...` |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key (for admin operations) | `eyJ********************************9...` |

### Optional Variables

#### Application Configuration

| Variable    | Description                            | Default         |
| ----------- | -------------------------------------- | --------------- |
| `APP_ENV`   | Runtime environment (`development`, `production`, etc.) | `development`   |
| `APP_NAME`  | Application name                       | `pantry-server` |
| `PORT`      | Server port                            | `8000`          |
| `HOST`      | Server host                            | `0.0.0.0`       |
| `RELOAD`    | Enable auto-reload                     | `True`          |
| `LOG_LEVEL` | Base logging level (overridden by `APP_ENV` for prod) | `INFO`          |

#### CORS Configuration

| Variable       | Description                                           | Default                                                   |
| -------------- | ----------------------------------------------------- | --------------------------------------------------------- |
| `CORS_ORIGINS` | Allowed CORS origins (comma-separated or Python list) | `['http://localhost:3000', 'http://localhost:5173', '*']` |

#### Gemini AI Configuration

| Variable                                  | Description                 | Default                |
| ----------------------------------------- | --------------------------- | ---------------------- |
| `GOOGLE_GENERATIVE_AI_API_KEY`            | Google AI API key           | —                      |
| `GEMINI_MODEL`                            | Gemini model name           | `gemini-2.5-flash`     |
| `GEMINI_TEMPERATURE`                      | Model temperature (0.0–2.0, validated) | `0.0`                  |
| `GEMINI_MAX_TOKENS`                       | Maximum tokens per response | `1000`                 |
| `GEMINI_MAX_RETRIES`                      | Maximum retry attempts      | `2`                    |
| `GEMINI_EMBEDDINGS_MODEL`                 | Embeddings model name       | `gemini-embedding-001` |
| `GEMINI_EMBEDDINGS_OUTPUT_DIMENSIONALITY` | Embedding vector size       | `768`                  |

#### Rate Limiting

| Variable                | Description                                 | Default |
| ----------------------- | ------------------------------------------- | ------- |
| `RATE_LIMIT_ENABLED`    | Enable SlowAPI-based rate limiting          | `True`  |
| `RATE_LIMIT_PER_MINUTE` | Default requests per minute (global limiter) | `60`    |

#### Background Workers

| Variable                    | Description                     | Default |
| --------------------------- | ------------------------------- | ------- |
| `ENABLE_BACKGROUND_WORKERS` | Enable background processing    | `True`  |
| `EMBEDDING_BATCH_SIZE`      | Batch size for embeddings       | `50`    |
| `EMBEDDING_WORKER_INTERVAL` | Worker check interval (seconds) | `5`     |

## API Documentation

### Current Endpoints

#### Health Check

- **GET** `/health` - Returns application health status
  - Response: `{"status": "ok"}`

#### Root

- **GET** `/` - Simple status endpoint (excluded from OpenAPI)
  - Response: `{"status": "ok"}`

#### Households (authenticated)

- **POST** `/households/join` - Join a household by invite code. Body: `{"invite_code": "ABC123"}`. The user leaves their current household; their pantry items are moved to the new household.
- **POST** `/households/leave` - Leave the current household and switch to a new personal household. Pantry items are moved to the new personal household.
- **POST** `/households/convert-to-joinable` - Convert the current user's personal household to a joinable (shared) household. Optional body: `{"name": "Household Name"}`. Returns the household with `invite_code` for sharing.

#### Pantry

The pantry router is always included. Endpoints:

- **POST** `/pantry/add-item` - Add a single pantry item (legacy alias: `/pantry/add_item`)
- **POST** `/pantry/bulk-add` - Add multiple pantry items (legacy alias: `/pantry/bulk_add`)
- **GET** `/pantry/household-items` - List all pantry items in the current household (legacy alias: `/pantry/get_household_items`)
- **GET** `/pantry/my-items` - List pantry items owned by the current user in the household (legacy alias: `/pantry/get_my_items`)
- **PUT** `/pantry/update-item` - Update a pantry item (legacy alias: `/pantry/update_item`)
- **DELETE** `/pantry/delete-item` - Delete a pantry item (legacy alias: `/pantry/delete_item`)

### Planned Endpoints

Routes are defined in models but not yet implemented. Planned endpoints include:

#### Recipe Management

- `GET /api/recipes` - List recipes
- `POST /api/recipes` - Create recipe
- `GET /api/recipes/{recipe_id}` - Get recipe
- `POST /api/recipes/generate` - Generate recipe from pantry
- `POST /api/recipes/search` - Search recipes
- `POST /api/recipes/{recipe_id}/use-ingredients` - Mark ingredients as used

#### Shopping Lists

- `GET /api/shopping-lists` - List shopping lists
- `POST /api/shopping-lists` - Create shopping list
- `GET /api/shopping-lists/{list_id}` - Get shopping list
- `POST /api/shopping-lists/generate` - Generate from pantry
- `POST /api/shopping-lists/{list_id}/mark-purchased` - Mark items purchased

#### User Preferences

- `GET /api/user/preferences` - Get user preferences
- `PUT /api/user/preferences` - Update user preferences

## Development Guidelines

### Code Style

- **Type Hints**: All functions must have type hints
- **Docstrings**: Use Google-style docstrings for public functions
- **Naming**: Use descriptive names with auxiliary verbs (`is_active`, `has_permission`)
- **Early Returns**: Handle errors and edge cases at the beginning of functions
- **Guard Clauses**: Use guard clauses for preconditions

### Adding New Routes

1. Create route file in `app/routers/`
2. Define router with `APIRouter(prefix="/your-prefix", tags=["tag-name"])`
3. Add routes with proper type hints and response models
4. Include router in `app/main.py`:

```python
from app.routers import your_router

app.include_router(your_router)
```

### Adding New Models

1. Create model file in `app/models/` or add to existing file
2. Follow the pattern: `*Base`, `*Create`, `*Update`, `*Response`
3. Use Pydantic `Field` for validation and descriptions
4. Export models in `__all__`

### Adding New Services

1. Create service file in `app/services/`
2. Use `@lru_cache(maxsize=1)` for singleton clients
3. Keep I/O and external API calls in services
4. Use dependency injection for shared resources

### Testing

See [Testing](#testing) for install and run commands. Use `pytest`, `pytest tests/unit`, `pytest tests/integration`, or `pytest --cov=app`.

### Code Quality

```bash
# Format code
black app/

# Lint code
ruff check app/

# Type checking
mypy app/
```

## Contributing

1. Create a feature branch
2. Make your changes following the development guidelines
3. Ensure all tests pass
4. Update documentation as needed
5. Submit a pull request

## License

[Add your license here]

## Support

For issues and questions, please open an issue in the repository.

## Recent Updates

- Added migration `20260213000000_households_household_members_trigger.sql` to keep `households` and `household_members` in sync at the database level.
- When setting up a new environment, ensure all Supabase migrations in `server/supabase/migrations/` are applied (for example via the Supabase CLI or Studio) before running the API.
